#!/usr/bin/env python3
"""Full PhenoDP retrieve + API rerank pipeline for RareBench (HMS, MME, RAMEDIS, LIRICAL).

RareBench has a different format from phenopackets:
  - Only positive HPO IDs (no labels, no negatives, no genes, no demographics)
  - Disease IDs only (no labels)
HPO labels and disease names are resolved from pyhpo / PhenoDP at load time.
"""
from __future__ import annotations

import argparse
import concurrent.futures as _cf
import json
import shutil
from dataclasses import replace
from pathlib import Path
from typing import Any, Dict, List

from tqdm.auto import tqdm

from phenodp_gemma3_pipeline.io_utils import write_csv, write_jsonl, write_markdown_examples
from phenodp_gemma3_pipeline.metrics import CRITERIA, KS, evaluate_ranked_items, summarize_evaluations
from phenodp_gemma3_pipeline.models import DiseaseCandidate, PatientCase, Truth
from phenodp_gemma3_pipeline.phenodp_retriever import PhenoDPOptions, PhenoDPRetriever
from phenodp_gemma3_pipeline.prompting import PromptOptions, build_prompt_text
from phenodp_gemma3_pipeline.rerankers import parse_reranker_output
from phenodp_gemma3_pipeline.api_reranker import APIReranker
from phenodp_gemma3_pipeline.utils import (
    capture_environment, configure_logging, ensure_dir, make_run_dir, seed_everything, write_json,
)

RAREBENCH_DATA_DIR = "/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/datasets/RareBench_min/data"
PHENODP_REPO_ROOT  = "/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/PehnoPacketPhenoDP/PhenoDP"
OUTPUT_ROOT        = "/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/phenodp_gemma3_candidate_ranking/runs"

SUBSETS = ["HMS", "MME", "RAMEDIS", "LIRICAL"]


# ── HPO / disease label helpers ───────────────────────────────────────────────

def _load_hpo_names() -> Dict[str, str]:
    try:
        from pyhpo import Ontology
        Ontology()
        return {term.id: term.name for term in Ontology}
    except Exception as exc:
        print(f"[WARN] pyhpo unavailable — HPO labels will be empty: {exc}")
        return {}


# ── Data loading ──────────────────────────────────────────────────────────────

def load_rarebench(
    data_dir: str,
    subsets: List[str],
    hpo_names: Dict[str, str],
) -> List[Dict[str, Any]]:
    """Load RareBench JSONL files and convert to pipeline row format."""
    rows: List[Dict[str, Any]] = []
    for subset in subsets:
        path = Path(data_dir) / f"{subset}.jsonl"
        if not path.exists():
            print(f"[WARN] {path} not found, skipping.")
            continue
        cases = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        for idx, case in enumerate(cases, start=1):
            patient_id = f"{subset}_{idx:04d}"
            hpo_ids: List[str] = [h for h in (case.get("Phenotype") or []) if h.startswith("HP:")]
            hpo_labels: List[str] = [hpo_names.get(h, h) for h in hpo_ids]
            disease_ids: List[str] = [str(d).upper() for d in (case.get("RareDisease") or []) if d]

            patient_case = PatientCase(
                patient_id=patient_id,
                description=None,
                phenotype_ids=hpo_ids,
                phenotype_labels=hpo_labels,
                neg_phenotype_ids=[],
                neg_phenotype_labels=[],
                genes=[],
                sex=None,
                age=None,
            )
            truth = Truth(
                disease_ids=disease_ids,
                disease_labels=[""] * len(disease_ids),  # filled later if disease names available
            )
            rows.append({"case": patient_case, "truth": truth, "subset": subset})
    return rows


# ── Metric helpers ────────────────────────────────────────────────────────────

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


def _safe_id(value: str) -> str:
    return "".join(c for c in value if c.isalnum() or c in ("-", "_"))


# ── Main ──────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="RareBench full PhenoDP retrieve + API rerank pipeline.")
    parser.add_argument("--run-name", default="phenodp_medllama70b_rarebench_v7")
    parser.add_argument("--data-dir", default=RAREBENCH_DATA_DIR)
    parser.add_argument("--subsets", default="HMS,MME,RAMEDIS,LIRICAL")
    parser.add_argument("--output-root", default=OUTPUT_ROOT)
    parser.add_argument("--phenodp-repo-root", default=PHENODP_REPO_ROOT)
    parser.add_argument("--api-base", default="http://127.0.0.1:8000/v1")
    parser.add_argument("--api-key", default="local-token")
    parser.add_argument("--api-model", default="m42-health/Llama3-Med42-70B")
    parser.add_argument("--max-tokens", type=int, default=200)
    parser.add_argument("--retrieve-k", type=int, default=50)
    parser.add_argument("--rerank-cutoffs", default="3,5,10")
    parser.add_argument("--max-api-workers", type=int, default=16)
    parser.add_argument("--prompt-version", default="v7", choices=["v3", "v4", "v5", "v6", "v7", "pp2prompt", "pp2prompt_v2"])
    parser.add_argument("--pp2prompt-dir", default=None,
                        help="Flat directory of *_en-prompt.txt files (required for pp2prompt / pp2prompt_v2).")
    parser.add_argument("--method-prefix", default="reranker_medllama70b")
    parser.add_argument("--qualitative-examples", type=int, default=5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--phenodp-device", default="cpu")
    parser.add_argument("--use-completions", action="store_true",
                        help="Use /v1/completions instead of /v1/chat/completions. "
                             "Applies the chat template client-side via the HuggingFace tokenizer. "
                             "Recommended for models like MedGemma that have issues with the chat API.")
    parser.add_argument("--tokenizer", default=None,
                        help="HuggingFace tokenizer name for client-side chat template rendering "
                             "(only used with --use-completions). Defaults to --api-model.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    seed_everything(args.seed)

    run_dir = Path(make_run_dir(args.output_root, args.run_name))
    logger = configure_logging(run_dir / "run.log", verbose=False)
    write_json(run_dir / "run_config.json", vars(args))
    write_json(run_dir / "environment.json", capture_environment())

    subsets = [s.strip() for s in args.subsets.split(",") if s.strip()]
    cutoffs = sorted({int(v) for v in args.rerank_cutoffs.split(",") if v.strip()})

    # Load HPO names
    logger.info("Loading HPO names from pyhpo...")
    hpo_names = _load_hpo_names()
    logger.info("Loaded %d HPO names", len(hpo_names))

    # Load RareBench dataset
    logger.info("Loading RareBench subsets: %s", subsets)
    dataset = load_rarebench(args.data_dir, subsets, hpo_names)
    logger.info("Total cases: %d", len(dataset))

    # Write benchmark IDs
    benchmark_ids = [row["case"].patient_id for row in dataset]
    (run_dir / "benchmark_ids.txt").write_text("\n".join(benchmark_ids) + "\n", encoding="utf-8")

    # ── Retrieval ─────────────────────────────────────────────────────────────
    logger.info("Loading PhenoDP retriever...")
    retriever = PhenoDPRetriever(PhenoDPOptions(
        phenodp_repo_root=args.phenodp_repo_root,
        phenodp_data_dir=str(Path(args.phenodp_repo_root) / "data"),
        phenodp_hpo_dir=str(Path(args.phenodp_repo_root) / "data" / "hpo_latest"),
        ic_type="omim",
        device=args.phenodp_device,
        candidate_pool_size=max(200, args.retrieve_k),
    ))

    candidate_sets_dir = Path(ensure_dir(run_dir / "candidate_sets"))
    candidates_path = candidate_sets_dir / f"phenodp_candidates_top{args.retrieve_k}.jsonl"

    logger.info("Running PhenoDP retrieval (top-%d)...", args.retrieve_k)
    retrieval_candidates: List[List[DiseaseCandidate]] = []
    for row in tqdm(dataset, desc="Retrieval", unit="case"):
        case: PatientCase = row["case"]
        retrieval_candidates.append(retriever.retrieve(case.phenotype_ids, top_k=args.retrieve_k))

    # Save candidates
    candidate_records = []
    for row, candidates in zip(dataset, retrieval_candidates):
        case: PatientCase = row["case"]
        truth: Truth = row["truth"]
        candidate_records.append({
            "patient_id": case.patient_id,
            "truth_ids": truth.disease_ids,
            "candidates": [c.to_json() for c in candidates],
        })
    write_jsonl(str(candidates_path), candidate_records)

    # Retrieval metrics
    retrieval_case_metrics = []
    retrieval_results = []
    for row, candidates in zip(dataset, retrieval_candidates):
        case: PatientCase = row["case"]
        truth: Truth = row["truth"]
        ranked = [{"id": c.disease_id, "name": c.disease_name} for c in candidates]
        metrics = evaluate_ranked_items(ranked, truth.disease_ids, truth.disease_labels)
        retrieval_case_metrics.append(metrics)
        result_row: Dict[str, Any] = {
            "patient_id": case.patient_id,
            "subset": row["subset"],
            "truth_ids": "|".join(truth.disease_ids),
            **_flatten_case_metrics(metrics),
        }
        retrieval_results.append(result_row)

    retrieval_method = f"retriever_phenodp_top{args.retrieve_k}"
    methods_root = Path(ensure_dir(run_dir / "methods"))
    retrieval_dir = Path(ensure_dir(methods_root / retrieval_method))
    shutil.copyfile(candidates_path, retrieval_dir / "candidates.jsonl")
    write_csv(str(retrieval_dir / "results.csv"), retrieval_results)
    retrieval_summary = {
        "stage": "retriever", "method": retrieval_method, "status": "completed",
        "n_cases": len(retrieval_case_metrics),
        "criteria": summarize_evaluations(retrieval_case_metrics),
    }
    write_json(retrieval_dir / "summary.json", retrieval_summary)
    logger.info("Retrieval done. hit@1=%.4f hit@10=%.4f",
                retrieval_summary["criteria"]["id_correct"]["hit@1"],
                retrieval_summary["criteria"]["id_correct"]["hit@10"])

    # ── Reranking ─────────────────────────────────────────────────────────────
    benchmark_rows: List[Dict[str, Any]] = [_flatten_summary_row(retrieval_summary)]

    prompt_opts = PromptOptions(
        include_genes=False,
        include_negative_phenotypes=False,  # RareBench has no negatives
        include_demographics=False,         # RareBench has no demographics
        prompt_version=args.prompt_version,
        pp2prompt_dir=args.pp2prompt_dir,
    )

    reranker = APIReranker(
        api_base=args.api_base,
        model=args.api_model,
        api_key=args.api_key,
        prompt_opts=prompt_opts,
        max_tokens=args.max_tokens,
        batch_size=args.max_api_workers,
        max_workers=args.max_api_workers,
        use_completions=args.use_completions,
        tokenizer_name=args.tokenizer,
    )

    for cutoff in cutoffs:
        method_name = f"{args.method_prefix}_top{cutoff}"
        method_dir = Path(ensure_dir(methods_root / method_name))
        logs_dir = Path(ensure_dir(method_dir / "logs"))
        shutil.copyfile(candidates_path, method_dir / "candidates.jsonl")

        cut_prompt_opts = replace(prompt_opts, output_top_k=cutoff, candidate_count_in_prompt=cutoff)

        # Resume: skip already-logged cases
        already_done = {f.stem for f in logs_dir.iterdir() if f.suffix == ".txt"}
        rerank_results: List[Dict[str, Any]] = []
        rerank_case_metrics: List[Dict[str, Dict[str, float]]] = []
        examples: List[Dict[str, Any]] = []

        pending = [
            (row, cands)
            for row, cands in zip(dataset, retrieval_candidates)
            if _safe_id(row["case"].patient_id) not in already_done
        ]
        logger.info("top%d: %d cases to process (%d already done)", cutoff, len(pending), len(already_done))

        pending_prompts = [
            build_prompt_text(row["case"], cands[:cutoff], cut_prompt_opts)
            for row, cands in pending
        ]

        raw_outputs: List[str] = [""] * len(pending_prompts)
        with _cf.ThreadPoolExecutor(max_workers=args.max_api_workers) as pool:
            future_to_idx = {
                pool.submit(reranker._call_api, prompt): idx
                for idx, prompt in enumerate(pending_prompts)
            }
            for future in tqdm(_cf.as_completed(future_to_idx), total=len(future_to_idx), desc=f"Rerank top{cutoff}", unit="case"):
                idx = future_to_idx[future]
                try:
                    raw_outputs[idx] = future.result()
                except Exception as exc:
                    raw_outputs[idx] = f"API_ERROR: {exc}"

        for (row, candidates_full), prompt_text, raw_output in zip(pending, pending_prompts, raw_outputs):
            candidates = candidates_full[:cutoff]
            case: PatientCase = row["case"]
            truth: Truth = row["truth"]
            parsed = parse_reranker_output(raw_output, candidates, output_top_k=cutoff)
            ranking = parsed.get("ranking") or []
            metrics = evaluate_ranked_items(ranking, truth.disease_ids, truth.disease_labels)
            rerank_case_metrics.append(metrics)

            (logs_dir / f"{_safe_id(case.patient_id)}.txt").write_text(
                f"PROMPT:\n{prompt_text}\n\nRAW OUTPUT:\n{raw_output}\n", encoding="utf-8"
            )

            selected = parsed.get("selected_candidate") or {}
            result_row: Dict[str, Any] = {
                "patient_id": case.patient_id,
                "subset": row["subset"],
                "truth_ids": "|".join(truth.disease_ids),
                "candidate_cutoff": cutoff,
                "parse_mode": parsed.get("parse_mode", ""),
                "selected_candidate_id": str(selected.get("id") or ""),
                "ranked_ids": "|".join(str(item.get("id") or "") for item in ranking),
                **_flatten_case_metrics(metrics),
            }
            for pred_i in range(cutoff):
                if pred_i < len(ranking):
                    result_row[f"pred{pred_i+1}_id"] = str(ranking[pred_i].get("id") or "")
                    result_row[f"pred{pred_i+1}_name"] = str(ranking[pred_i].get("name") or "")
                else:
                    result_row[f"pred{pred_i+1}_id"] = ""
                    result_row[f"pred{pred_i+1}_name"] = ""
            rerank_results.append(result_row)

            if len(examples) < args.qualitative_examples:
                examples.append({
                    "patient_id": case.patient_id,
                    "subset": row["subset"],
                    "truth_ids": "|".join(truth.disease_ids),
                    "prompt": prompt_text,
                    "raw_output": raw_output,
                    "parsed_output": {"selected_candidate": selected, "ranking": ranking},
                })

        rerank_summary = {
            "stage": "reranker", "method": method_name, "status": "completed",
            "n_cases": len(rerank_case_metrics),
            "criteria": summarize_evaluations(rerank_case_metrics),
            "candidate_cutoff": cutoff,
            "model": args.api_model,
        }
        write_csv(str(method_dir / "results.csv"), rerank_results)
        write_json(method_dir / "summary.json", rerank_summary)
        write_markdown_examples(str(method_dir / "qualitative_examples.md"), examples)
        benchmark_rows.append(_flatten_summary_row(rerank_summary))

        logger.info("top%d done. hit@1=%.4f MRR=%.4f",
                    cutoff,
                    rerank_summary["criteria"]["id_correct"]["hit@1"],
                    rerank_summary["criteria"]["id_correct"]["mrr"])

    write_csv(str(run_dir / "benchmark_summary.csv"), benchmark_rows)
    write_json(run_dir / "benchmark_summary.json", {"rows": benchmark_rows})
    logger.info("Run complete: %s", run_dir)


if __name__ == "__main__":
    main()
