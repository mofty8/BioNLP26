"""API-based reranker that calls a vLLM OpenAI-compatible server instead of loading the model in-process.

Supports two modes:
- **chat** (default): uses ``/v1/chat/completions`` — works for models whose chat
  template is correctly handled server-side by vLLM.
- **completions**: uses ``/v1/completions`` — applies the chat template *client-side*
  via the HuggingFace tokenizer, then sends the rendered text to the raw completions
  endpoint.  This is the recommended mode for models like MedGemma that have issues
  with the OpenAI chat-completions endpoint on vLLM.
"""
from __future__ import annotations

import concurrent.futures
import logging
from typing import Any, Dict, List, Optional, Sequence, Tuple

from openai import OpenAI

from .models import DiseaseCandidate, PatientCase
from .prompting import PromptOptions, build_prompt_text
from .rerankers import parse_reranker_output

logger = logging.getLogger(__name__)


def _load_tokenizer(model_name: str):
    """Load a HuggingFace tokenizer for client-side chat-template rendering."""
    from transformers import AutoTokenizer
    return AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)


class APIReranker:
    """Reranker that calls a running vLLM API server (OpenAI-compatible).

    Parameters
    ----------
    use_completions : bool
        When *True*, uses ``/v1/completions`` instead of ``/v1/chat/completions``.
        The chat template is applied client-side via the HuggingFace tokenizer so
        the server only sees a plain text prompt.  This avoids chat-template /
        OpenAI-compat issues for models like MedGemma.
    tokenizer_name : str | None
        HuggingFace model name used to load the tokenizer for client-side chat-
        template rendering.  Only used when *use_completions=True*.  Defaults to
        *model* if not provided.
    """

    def __init__(
        self,
        api_base: str,
        model: str,
        api_key: str,
        prompt_opts: PromptOptions,
        max_tokens: int = 400,
        temperature: float = 0.0,
        top_p: float = 1.0,
        batch_size: int = 8,
        max_workers: int = 8,
        annotation_store=None,
        hpo_names: Optional[Dict[str, str]] = None,
        use_completions: bool = False,
        tokenizer_name: Optional[str] = None,
    ):
        self.client = OpenAI(base_url=api_base, api_key=api_key)
        self.model = model
        self.prompt_opts = prompt_opts
        self.max_tokens = int(max_tokens)
        self.temperature = float(temperature)
        self.top_p = float(top_p)
        self.batch_size = int(batch_size)
        self.max_workers = int(max_workers)
        self.annotation_store = annotation_store
        self.hpo_names = hpo_names or {}
        self.use_completions = use_completions
        self._tokenizer = None
        self._tokenizer_name = tokenizer_name or model

        if self.use_completions:
            logger.info(
                "Completions mode enabled — loading tokenizer '%s' for client-side chat template",
                self._tokenizer_name,
            )
            self._tokenizer = _load_tokenizer(self._tokenizer_name)

    def _render_chat_template(self, text: str) -> str:
        """Apply the model's chat template to a plain-text user message."""
        messages = [{"role": "user", "content": text}]
        return self._tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )

    def _call_api(self, prompt_text: str) -> str:
        if self.use_completions:
            rendered = self._render_chat_template(prompt_text)
            response = self.client.completions.create(
                model=self.model,
                prompt=rendered,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                top_p=self.top_p,
            )
            return response.choices[0].text or ""
        else:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt_text}],
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                top_p=self.top_p,
            )
            return response.choices[0].message.content or ""

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

        raw_outputs: List[str] = [""] * len(plain_prompts)
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_index = {
                executor.submit(self._call_api, prompt): idx
                for idx, prompt in enumerate(plain_prompts)
            }
            for future in concurrent.futures.as_completed(future_to_index):
                idx = future_to_index[future]
                try:
                    raw_outputs[idx] = future.result()
                except Exception as exc:
                    raw_outputs[idx] = f"API_ERROR: {exc}"

        parsed_outputs: List[Dict[str, Any]] = []
        for raw_output, candidates in zip(raw_outputs, candidates_list):
            parsed_outputs.append(
                parse_reranker_output(raw_output, list(candidates), output_top_k=int(self.prompt_opts.output_top_k))
            )

        return parsed_outputs, plain_prompts
