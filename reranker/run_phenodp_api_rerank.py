#!/usr/bin/env python3
"""Rerank-only pipeline using a vLLM API server (OpenAI-compatible).

Reads retrieval candidates from an existing run dir (--resume-run-dir),
runs an API-based LLM reranker, and writes results to a NEW run dir.
Does not load any model in-process — the model must already be served.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from tqdm.auto import tqdm

from phenodp_gemma3_pipeline.data_loader import load_phenopackets
from phenodp_gemma3_pipeline.io_utils import read_jsonl, write_csv, write_jsonl, write_markdown_examples
from phenodp_gemma3_pipeline.metrics import CRITERIA, KS, evaluate_ranked_items, summarize_evaluations
from phenodp_gemma3_pipeline.models import DiseaseCandidate, PatientCase, Truth
from phenodp_gemma3_pipeline.prompting import PromptOptions, build_prompt_text
from phenodp_gemma3_pipeline.rerankers import parse_reranker_output
from phenodp_gemma3_pipeline.api_reranker import APIReranker
from phenodp_gemma3_pipeline.utils import (
    capture_environment, configure_logging, ensure_dir, make_run_dir, read_lines, seed_everything, write_json,
)


DEFAULT_DATA_DIR = "/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/PP_LLM/phenopackets_extracted/0.1.25"
DEFAULT_OUTPUT_ROOT = "/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/phenodp_gemma3_candidate_ranking/runs"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PhenoDP rerank-only via vLLM API server.")
    parser.add_argument("--run-name", required=True)
    parser.add_argument("--resume-run-dir", required=True, help="Existing run dir with candidate_sets/ to reuse.")
    parser.add_argument("--data-dir", default=DEFAULT_DATA_DIR)
    parser.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--benchmark-ids-path", default="")
    parser.add_argument("--api-base", default="http://127.0.0.1:8000/v1")
    parser.add_argument("--api-key", default="local-token")
    parser.add_argument("--api-model", required=True, help="Model name as served by the API (must match server).")
    parser.add_argument("--max-tokens", type=int, default=200)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--top-p", type=float, default=1.0)
    parser.add_argument("--retrieve-k", type=int, default=50)
    parser.add_argument("--rerank-cutoffs", default="3,5,10")
    parser.add_argument("--llm-batch-size", type=int, default=8)
    parser.add_argument("--max-api-workers", type=int, default=16)
    parser.add_argument("--prompt-version", default="v6", choices=["v3", "v4", "v5", "v6", "v7", "pp2prompt", "pp2prompt_v2"])
    parser.add_argument("--pp2prompt-dir", default=None,
                        help="Directory of pre-generated PP2Prompt .txt files (required for --prompt-version pp2prompt).")
    parser.add_argument("--max-phenotypes-in-prompt", type=int, default=30)
    parser.add_argument("--max-negative-phenotypes-in-prompt", type=int, default=20)
    parser.add_argument("--max-genes-in-prompt", type=int, default=20)
    parser.add_argument("--prompt-no-genes", action="store_true")
    parser.add_argument("--prompt-include-negative-phenotypes", action="store_true")
    parser.add_argument("--prompt-include-demographics", action="store_true")
    parser.add_argument("--qualitative-examples", type=int, default=5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--min-phenotypes", type=int, default=1)
    parser.add_argument("--include-excluded-phenotypes", action="store_true")
    parser.add_argument("--method-prefix", default="reranker_medllama70b", help="Prefix for method dir names.")
    parser.add_argument("--use-completions", action="store_true",
                        help="Use /v1/completions instead of /v1/chat/completions. "
                             "Applies the chat template client-side via the HuggingFace tokenizer. "
                             "Recommended for models like MedGemma that have issues with the chat API.")
    parser.add_argument("--tokenizer", default=None,
                        help="HuggingFace tokenizer name for client-side chat template rendering "
                             "(only used with --use-completions). Defaults to --api-model.")
    return parser.parse_args()


def _safe_id(value: str) -> str:
    return "".join(c for c in value if c.isalnum() or c in ("-", "_"))


def _flatten_case_metrics(metrics: Dict[str, Dict[str, float]]) -> Dict[str, Any]:
    flat: Dict[str, Any] = {}
    for criterion in CRITERIA:
        m = metrics.get(criterion, {})
        flat[f"{criterion}_rank"] = int(m.get("rank", 0.0) or 0.0)
        flat[f"{criterion}_found"] = int(m.get("found", 0.0) or 0.0)
        flat[f"{criterion}_mrr"] = float(m.get("mrr", 0.0))
        for k in KS:
            flat[f"{criterion}_hit_{k}"] = float(m.get(f"hit@{k}", 0.0))
    return flat


def _flatten_summary_row(summary: Dict[str, Any]) -> Dict[str, Any]:
    row = {
        "stage": summary["stage"],
        "method": summary["method"],
        "status": summary["status"],
        "n_cases": int(summary["n_cases"]),
    }
    for criterion in CRITERIA:
        cs = summary["criteria"].get(criterion, {})
        row[f"{criterion}_mrr"] = float(cs.get("mrr", 0.0))
        row[f"{criterion}_found"] = float(cs.get("found", 0.0))
        for k in KS:
            row[f"{criterion}_hit_{k}"] = float(cs.get(f"hit@{k}", 0.0))
    return row


def _load_retrieval_candidates(
    candidates_path: Path,
    dataset: List[Dict[str, Any]],
) -> List[List[DiseaseCandidate]]:
    records = read_jsonl(str(candidates_path))
    by_id = {str(r.get("patient_id") or ""): r for r in records if r.get("patient_id")}
    result = []
    missing = []
    for row in dataset:
        pid = row["case"].patient_id
        rec = by_id.get(pid)
        if rec is None:
            missing.append(pid)
            result.append([])
        else:
            result.append([DiseaseCandidate.from_json(c) for c in (rec.get("candidates") or [])])
    if missing:
        raise FileNotFoundError(f"Missing candidates for {len(missing)} cases: {missing[:5]}")
    return result


def main() -> None:
    args = parse_args()
    seed_everything(args.seed)

    resume_dir = Path(args.resume_run_dir)
    if not resume_dir.is_absolute():
        resume_dir = Path(DEFAULT_OUTPUT_ROOT).parent / resume_dir

    # Create new run dir (never overwrites existing)
    output_root = Path(args.output_root)
    run_dir = Path(make_run_dir(str(output_root), args.run_name))
    logger = configure_logging(run_dir / "run.log", verbose=True)

    run_config = {
        "run_name": args.run_name,
        "resume_run_dir": str(resume_dir),
        "api_base": args.api_base,
        "api_model": args.api_model,
        "max_tokens": args.max_tokens,
        "temperature": args.temperature,
        "top_p": args.top_p,
        "retrieve_k": args.retrieve_k,
        "rerank_cutoffs": [int(v) for v in args.rerank_cutoffs.split(",") if v.strip()],
        "llm_batch_size": args.llm_batch_size,
        "max_api_workers": args.max_api_workers,
        "prompt_version": args.prompt_version,
        "method_prefix": args.method_prefix,
        "use_completions": args.use_completions,
        "tokenizer": args.tokenizer,
        "seed": args.seed,
    }
    write_json(run_dir / "run_config_rerank.json", run_config)
    write_json(run_dir / "environment_rerank.json", capture_environment())

    # Load dataset
    dataset = load_phenopackets(
        args.data_dir,
        logger=logger,
        include_excluded_phenotypes=args.include_excluded_phenotypes,
        min_phenotypes=args.min_phenotypes,
    )

    # Resolve benchmark IDs
    if args.benchmark_ids_path:
        benchmark_ids = sorted(read_lines(args.benchmark_ids_path))
    else:
        # Fall back to the benchmark_ids from the resumed run dir
        fallback = resume_dir / "benchmark_ids.txt"
        if fallback.exists():
            benchmark_ids = sorted(read_lines(str(fallback)))
            logger.info("Using benchmark IDs from resume dir: %s", fallback)
        else:
            benchmark_ids = sorted(row["case"].patient_id for row in dataset)

    benchmark_id_set = set(benchmark_ids)
    dataset = [row for row in dataset if row["case"].patient_id in benchmark_id_set]
    dataset.sort(key=lambda row: row["case"].patient_id)
    (run_dir / "benchmark_ids.txt").write_text("\n".join(benchmark_ids) + "\n", encoding="utf-8")
    logger.info("Benchmark cases: %d", len(dataset))

    # Load retrieval candidates from the resumed run
    candidates_path = resume_dir / "candidate_sets" / f"phenodp_candidates_top{args.retrieve_k}.jsonl"
    logger.info("Loading retrieval candidates from %s", candidates_path)
    retrieval_candidates = _load_retrieval_candidates(candidates_path, dataset)

    # Copy candidate_sets to new run dir
    candidate_sets_dir = Path(ensure_dir(run_dir / "candidate_sets"))
    shutil.copyfile(candidates_path, candidate_sets_dir / candidates_path.name)

    methods_root = Path(ensure_dir(run_dir / "methods"))

    prompt_opts = PromptOptions(
        max_phenotypes=args.max_phenotypes_in_prompt,
        max_negative_phenotypes=args.max_negative_phenotypes_in_prompt,
        max_genes=args.max_genes_in_prompt,
        include_genes=not args.prompt_no_genes,
        include_negative_phenotypes=args.prompt_include_negative_phenotypes,
        include_demographics=args.prompt_include_demographics,
        prompt_version=args.prompt_version,
        pp2prompt_dir=args.pp2prompt_dir,
    )

    cutoffs = sorted({int(v) for v in args.rerank_cutoffs.split(",") if v.strip()})
    benchmark_rows: List[Dict[str, Any]] = []

    for cutoff in cutoffs:
        method_name = f"{args.method_prefix}_top{cutoff}"
        method_dir = Path(ensure_dir(methods_root / method_name))
        logs_dir = Path(ensure_dir(method_dir / "logs"))
        shutil.copyfile(candidates_path, method_dir / "candidates.jsonl")

        from dataclasses import replace
        cut_prompt_opts = replace(
            prompt_opts,
            output_top_k=int(cutoff),
            candidate_count_in_prompt=int(cutoff),
        )

        reranker = APIReranker(
            api_base=args.api_base,
            model=args.api_model,
            api_key=args.api_key,
            prompt_opts=cut_prompt_opts,
            max_tokens=args.max_tokens,
            temperature=args.temperature,
            top_p=args.top_p,
            batch_size=args.llm_batch_size,
            max_workers=args.max_api_workers,
            use_completions=args.use_completions,
            tokenizer_name=args.tokenizer,
        )

        rerank_results: List[Dict[str, Any]] = []
        rerank_case_metrics: List[Dict[str, Dict[str, float]]] = []
        examples: List[Dict[str, Any]] = []

        # Resume: skip cases already logged
        already_done: set = {f.stem for f in logs_dir.iterdir() if f.suffix == ".txt"}
        if already_done:
            logger.info("Resuming top%d: %d cases already done, loading from logs", cutoff, len(already_done))
            for row, candidates_full in zip(dataset, retrieval_candidates):
                case: PatientCase = row["case"]
                truth: Truth = row["truth"]
                if _safe_id(case.patient_id) not in already_done:
                    continue
                candidates = candidates_full[:cutoff]
                log_txt = (logs_dir / f"{_safe_id(case.patient_id)}.txt").read_text(encoding="utf-8")
                raw_out = log_txt.split("RAW OUTPUT:", 1)[1].strip() if "RAW OUTPUT:" in log_txt else ""
                match = re.search(r'\{[\s\S]*?"ranking"\s*:\s*\[[\s\S]*?\]\s*\}', raw_out)
                parsed = json.loads(match.group()) if match else {}
                ranking = parsed.get("ranking") or []
                selected_candidate = parsed.get("selected_candidate") or {}
                metrics = evaluate_ranked_items(ranking, truth.disease_ids, truth.disease_labels)
                rerank_case_metrics.append(metrics)
                result_row: Dict[str, Any] = {
                    "patient_id": case.patient_id,
                    "truth_ids": "|".join(truth.disease_ids),
                    "truth_labels": "|".join(truth.disease_labels),
                    "candidate_cutoff": int(cutoff),
                    "parse_mode": parsed.get("parse_mode", "resumed"),
                    "selected_candidate_id": str(selected_candidate.get("id") or ""),
                    "selected_candidate_name": str(selected_candidate.get("name") or ""),
                    "retrieved_ids": "|".join(c.disease_id for c in candidates),
                    "retrieved_names": "|".join(c.disease_name for c in candidates),
                    "ranked_ids": "|".join(str(item.get("id") or "") for item in ranking),
                    "ranked_names": "|".join(str(item.get("name") or "") for item in ranking),
                    **_flatten_case_metrics(metrics),
                }
                for pred_i in range(int(cutoff)):
                    if pred_i < len(ranking):
                        item = ranking[pred_i]
                        result_row[f"pred{pred_i + 1}_id"] = str(item.get("id") or "")
                        result_row[f"pred{pred_i + 1}_name"] = str(item.get("name") or "")
                        result_row[f"pred{pred_i + 1}_source"] = str(item.get("source") or "")
                    else:
                        result_row[f"pred{pred_i + 1}_id"] = ""
                        result_row[f"pred{pred_i + 1}_name"] = ""
                        result_row[f"pred{pred_i + 1}_source"] = ""
                rerank_results.append(result_row)

        pending_pairs = [
            (row, cands)
            for row, cands in zip(dataset, retrieval_candidates)
            if _safe_id(row["case"].patient_id) not in already_done
        ]
        logger.info("top%d: %d cases to process", cutoff, len(pending_pairs))

        # Build all prompts upfront
        pending_prompts = [
            build_prompt_text(row["case"], cands[:cutoff], cut_prompt_opts)
            for row, cands in pending_pairs
        ]

        # Submit all cases at once to a persistent pool — no batch gaps, server queue always full
        raw_outputs: List[str] = [""] * len(pending_prompts)
        import concurrent.futures as _cf
        with _cf.ThreadPoolExecutor(max_workers=args.max_api_workers) as pool:
            future_to_idx = {
                pool.submit(reranker._call_api, prompt): idx
                for idx, prompt in enumerate(pending_prompts)
            }
            for future in tqdm(_cf.as_completed(future_to_idx), total=len(future_to_idx), desc=f"Rerank/top{cutoff}"):
                idx = future_to_idx[future]
                try:
                    raw_outputs[idx] = future.result()
                except Exception as exc:
                    raw_outputs[idx] = f"API_ERROR: {exc}"

        for (row, candidates_full), prompt_text, raw_output in zip(pending_pairs, pending_prompts, raw_outputs):
            candidates = candidates_full[:cutoff]
            case: PatientCase = row["case"]
            truth: Truth = row["truth"]
            parsed_output = parse_reranker_output(raw_output, candidates, output_top_k=cutoff)
            ranking = parsed_output.get("ranking") or []
            metrics = evaluate_ranked_items(ranking, truth.disease_ids, truth.disease_labels)
            rerank_case_metrics.append(metrics)

            safe_id = _safe_id(case.patient_id)
            (logs_dir / f"{safe_id}.txt").write_text(
                f"PROMPT:\n{prompt_text}\n\nRAW OUTPUT:\n{raw_output}\n",
                encoding="utf-8",
            )

            selected_candidate = parsed_output.get("selected_candidate") or {}
            result_row = {
                "patient_id": case.patient_id,
                "truth_ids": "|".join(truth.disease_ids),
                "truth_labels": "|".join(truth.disease_labels),
                "candidate_cutoff": int(cutoff),
                "parse_mode": parsed_output.get("parse_mode", ""),
                "selected_candidate_id": str(selected_candidate.get("id") or ""),
                "selected_candidate_name": str(selected_candidate.get("name") or ""),
                "retrieved_ids": "|".join(c.disease_id for c in candidates),
                "retrieved_names": "|".join(c.disease_name for c in candidates),
                "ranked_ids": "|".join(str(item.get("id") or "") for item in ranking),
                "ranked_names": "|".join(str(item.get("name") or "") for item in ranking),
                **_flatten_case_metrics(metrics),
            }
            for pred_i in range(int(cutoff)):
                if pred_i < len(ranking):
                    item = ranking[pred_i]
                    result_row[f"pred{pred_i + 1}_id"] = str(item.get("id") or "")
                    result_row[f"pred{pred_i + 1}_name"] = str(item.get("name") or "")
                    result_row[f"pred{pred_i + 1}_source"] = str(item.get("source") or "")
                else:
                    result_row[f"pred{pred_i + 1}_id"] = ""
                    result_row[f"pred{pred_i + 1}_name"] = ""
                    result_row[f"pred{pred_i + 1}_source"] = ""
            rerank_results.append(result_row)

            if len(examples) < args.qualitative_examples:
                examples.append({
                    "patient_id": case.patient_id,
                    "truth_ids": "|".join(truth.disease_ids),
                    "prompt": prompt_text,
                    "raw_output": raw_output,
                    "parsed_output": {
                        "selected_candidate": selected_candidate,
                        "ranking": ranking,
                        "parse_mode": parsed_output.get("parse_mode", ""),
                    },
                })

        rerank_summary = {
            "stage": "reranker",
            "method": method_name,
            "status": "completed",
            "n_cases": len(rerank_case_metrics),
            "criteria": summarize_evaluations(rerank_case_metrics),
            "candidate_cutoff": int(cutoff),
            "model": args.api_model,
            "notes": {
                "name_match_rule": "normalized exact match or rapidfuzz token_set_ratio >= 95",
            },
        }

        write_csv(str(method_dir / "results.csv"), rerank_results)
        write_json(method_dir / "summary.json", rerank_summary)
        write_markdown_examples(str(method_dir / "qualitative_examples.md"), examples)
        benchmark_rows.append(_flatten_summary_row(rerank_summary))

    write_csv(str(run_dir / "benchmark_summary.csv"), benchmark_rows)
    write_json(run_dir / "benchmark_summary.json", {"rows": benchmark_rows})
    logger.info("Run complete. Results in: %s", run_dir)


if __name__ == "__main__":
    main()
