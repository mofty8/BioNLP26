from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .hpo_annotations import HPOAnnotationStore
from .models import DiseaseCandidate, PatientCase
from .prompting import PromptOptions, build_prompt_text

try:
    from vllm import LLM, SamplingParams

    VLLM_AVAILABLE = True
except Exception:
    VLLM_AVAILABLE = False


_ENGINE_CACHE: Dict[Tuple[Any, ...], "LLM"] = {}


@dataclass
class LLMOptions:
    model: str
    tensor_parallel_size: int = 1
    gpu_memory_utilization: float = 0.85
    dtype: str = "bfloat16"
    temperature: float = 0.0
    top_p: float = 1.0
    max_tokens: int = 700
    trust_remote_code: bool = True
    max_model_len: Optional[int] = None  # None = let vLLM auto-detect; set explicitly to cap KV cache


def _engine_cache_key(opts: LLMOptions) -> Tuple[Any, ...]:
    return (
        opts.model,
        int(opts.tensor_parallel_size),
        float(opts.gpu_memory_utilization),
        str(opts.dtype),
        bool(opts.trust_remote_code),
        opts.max_model_len,
    )


def _get_or_create_llm(opts: LLMOptions) -> "LLM":
    if not VLLM_AVAILABLE:
        raise RuntimeError("vLLM is not available in the current environment.")
    key = _engine_cache_key(opts)
    llm = _ENGINE_CACHE.get(key)
    if llm is None:
        llm_kwargs: Dict[str, Any] = dict(
            model=opts.model,
            trust_remote_code=opts.trust_remote_code,
            dtype=opts.dtype,
            tensor_parallel_size=int(opts.tensor_parallel_size),
            gpu_memory_utilization=float(opts.gpu_memory_utilization),
            enable_prefix_caching=True,
            limit_mm_per_prompt={"image": 0},
            max_num_seqs=64,
        )
        if opts.max_model_len is not None:
            llm_kwargs["max_model_len"] = int(opts.max_model_len)
        llm = LLM(**llm_kwargs)
        _ENGINE_CACHE[key] = llm
    return llm


def _clean_json_text(text: str) -> str:
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
    cleaned = cleaned.replace("```json", "").replace("```", "").strip()
    return cleaned


def _extract_first_json(text: str) -> Any:
    cleaned = _clean_json_text(text)
    for opener, closer in (("{", "}"), ("[", "]")):
        start = cleaned.find(opener)
        end = cleaned.rfind(closer)
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(cleaned[start : end + 1])
            except Exception:
                continue
    return None


def parse_reranker_output(
    text: str,
    candidates: Sequence[DiseaseCandidate],
    output_top_k: int,
) -> Dict[str, Any]:
    id_to_candidate = {candidate.disease_id.upper(): candidate for candidate in candidates}
    name_to_candidate = {candidate.disease_name.lower(): candidate for candidate in candidates}
    payload = _extract_first_json(text)

    selected_candidate = {"id": "", "name": ""}
    ranking: List[Dict[str, Any]] = []
    parse_mode = "fallback"

    def resolve_candidate(item: Any) -> Tuple[str, str]:
        if isinstance(item, str):
            disease_id = str(item).strip().upper()
            candidate = id_to_candidate.get(disease_id)
            if candidate:
                return candidate.disease_id, candidate.disease_name
            candidate = name_to_candidate.get(str(item).strip().lower())
            if candidate:
                return "", candidate.disease_name
            return "", str(item).strip()
        if not isinstance(item, dict):
            return "", ""
        raw_id = str(item.get("id") or item.get("disease_id") or "").strip().upper()
        raw_name = str(item.get("name") or item.get("label") or item.get("disease_name") or "").strip()
        candidate = id_to_candidate.get(raw_id)
        if candidate:
            return candidate.disease_id, raw_name or candidate.disease_name
        if raw_name:
            candidate = name_to_candidate.get(raw_name.lower())
            if candidate:
                return "", raw_name
        return raw_id, raw_name

    if isinstance(payload, dict):
        parse_mode = "json_object"
        selected_candidate = {}
        resolved_id, resolved_name = resolve_candidate(payload.get("selected_candidate") or {})
        selected_candidate = {"id": resolved_id, "name": resolved_name}
        ranking_payload = payload.get("ranking") or []
        if isinstance(ranking_payload, list):
            for index, item in enumerate(ranking_payload[:output_top_k], start=1):
                resolved_id, resolved_name = resolve_candidate(item)
                ranking.append(
                    {"rank": index, "id": resolved_id, "name": resolved_name, "source": "model"}
                )
    elif isinstance(payload, list):
        parse_mode = "json_list"
        for index, item in enumerate(payload[:output_top_k], start=1):
            resolved_id, resolved_name = resolve_candidate(item)
            ranking.append({"rank": index, "id": resolved_id, "name": resolved_name, "source": "model"})

    if not ranking:
        matched_ids = []
        for match in re.findall(r"(OMIM:\d+|ORPHA:\d+)", text.upper()):
            if match in id_to_candidate and match not in matched_ids:
                matched_ids.append(match)
        for index, disease_id in enumerate(matched_ids[:output_top_k], start=1):
            candidate = id_to_candidate[disease_id]
            ranking.append(
                {"rank": index, "id": candidate.disease_id, "name": candidate.disease_name, "source": "regex"}
            )

    if not ranking:
        # Name-based fallback: match numbered lines (e.g. "1. Ehlers-Danlos syndrome") to candidates.
        seen_name_ids: List[str] = []
        for line in text.splitlines():
            m = re.match(r"^\s*\d+[\.\)]\s+(.+)", line)
            if not m:
                continue
            raw = m.group(1).strip()
            # strip trailing parenthetical "(OMIM:...)" or similar noise before name lookup
            name_only = re.sub(r"\s*[\(\[].*?[\)\]]", "", raw).strip().lower()
            candidate = name_to_candidate.get(name_only)
            if candidate and candidate.disease_id not in seen_name_ids:
                seen_name_ids.append(candidate.disease_id)
        for index, disease_id in enumerate(seen_name_ids[:output_top_k], start=1):
            candidate = id_to_candidate[disease_id]
            ranking.append(
                {"rank": index, "id": candidate.disease_id, "name": candidate.disease_name, "source": "name_match"}
            )

    if not selected_candidate.get("id") and ranking:
        selected_candidate = {"id": ranking[0].get("id", ""), "name": ranking[0].get("name", "")}

    seen_ids = {item["id"] for item in ranking if item.get("id")}
    for candidate in candidates:
        if len(ranking) >= output_top_k:
            break
        if candidate.disease_id in seen_ids:
            continue
        ranking.append(
            {
                "rank": len(ranking) + 1,
                "id": candidate.disease_id,
                "name": candidate.disease_name,
                "source": "retrieval_fallback",
            }
        )
        seen_ids.add(candidate.disease_id)

    return {
        "selected_candidate": selected_candidate,
        "ranking": ranking[:output_top_k],
        "parse_mode": parse_mode,
        "raw_output": text,
    }


class GemmaReranker:
    def __init__(
        self,
        llm_opts: LLMOptions,
        prompt_opts: PromptOptions,
        batch_size: int = 16,
        annotation_store: "HPOAnnotationStore | None" = None,
        hpo_names: "Dict[str, str] | None" = None,
    ):
        self.llm_opts = llm_opts
        self.prompt_opts = prompt_opts
        self.batch_size = int(batch_size)
        self.annotation_store = annotation_store
        self.hpo_names = hpo_names or {}
        self.llm = _get_or_create_llm(llm_opts)
        self.tokenizer = self.llm.get_tokenizer()
        self.sampling = SamplingParams(
            temperature=float(llm_opts.temperature),
            top_p=float(llm_opts.top_p),
            max_tokens=int(llm_opts.max_tokens),
        )

    def _render_prompt(self, text: str) -> str:
        try:
            messages = [{"role": "user", "content": text}]
            return self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        except Exception:
            return text

    def rerank_batch(
        self,
        cases: Sequence[PatientCase],
        candidates_list: Sequence[Sequence[DiseaseCandidate]],
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        plain_prompts = [
            build_prompt_text(
                case,
                list(candidates),
                self.prompt_opts,
                annotation_store=self.annotation_store,
                hpo_names=self.hpo_names,
            )
            for case, candidates in zip(cases, candidates_list)
        ]
        rendered_prompts = [self._render_prompt(prompt) for prompt in plain_prompts]
        generations = self.llm.generate(rendered_prompts, self.sampling)

        parsed_outputs: List[Dict[str, Any]] = []
        raw_outputs: List[str] = []
        for generation, candidates in zip(generations, candidates_list):
            raw_output = generation.outputs[0].text
            raw_outputs.append(raw_output)
            parsed_outputs.append(
                parse_reranker_output(raw_output, list(candidates), output_top_k=int(self.prompt_opts.output_top_k))
            )
        return parsed_outputs, plain_prompts
