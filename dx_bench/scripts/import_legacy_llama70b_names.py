"""Import legacy Llama 70B phenopacket results into a dx_bench-style run folder.

This script:
1. loads the exact phenopacket subset used by dx_bench,
2. aligns each dx_bench case to a row in the legacy CSV,
3. converts the ranked predictions into CaseResult JSONL records,
4. recomputes aggregate metrics with the current dx_bench evaluator, and
5. writes a dx_bench-style run directory under results/.
"""

from __future__ import annotations

import argparse
import csv
import difflib
import json
import math
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd

from dx_bench.config import RunConfig
from dx_bench.data.loader import load_cases
from dx_bench.data.schema import Case, CaseResult, Diagnosis
from dx_bench.evaluation.metrics import compute_aggregate, evaluate_case
from dx_bench.io.writer import ResultWriter
from dx_bench.normalization.disease_matcher import DiseaseMatcher


DEFAULT_LEGACY_CSV = Path(
    "/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/approach_result_mapping/"
    "05_legacy_llama70b_names/results/results_agent_llama_names.csv"
)
DEFAULT_PROMPT_DIR = Path(
    "/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/PP2Prompt/prompts/en"
)
DEFAULT_GT = Path(
    "/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/PP2Prompt/prompts/correct_results.tsv"
)
DEFAULT_BENCHMARK_IDS = Path(
    "/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/phenodp_gemma3_candidate_ranking/"
    "benchmark_ids_6901_phenodp_compatible_min3hpo.txt"
)
DEFAULT_ORIGINAL_PHENOPACKETS_DIR = Path(
    "/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/PP2Prompt/prompts/original_phenopackets"
)
DEFAULT_OUTPUT_ROOT = Path(
    "/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/dx_bench/results/"
    "legacy-llama70b-names_import/phenopacket"
)


TRANSLATION_TABLE = str.maketrans(
    {
        "Ł": "L",
        "ł": "l",
        "Ø": "O",
        "ø": "o",
        "Đ": "D",
        "đ": "d",
        "Þ": "Th",
        "þ": "th",
        "Ⅴ": "V",
        "Ⅳ": "IV",
        "Ⅲ": "III",
        "Ⅱ": "II",
        "Ⅰ": "I",
        "Ι": "I",
        "ι": "i",
    }
)


def _fold_key(text: str) -> str:
    text = str(text).translate(TRANSLATION_TABLE)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.encode("ascii", "ignore").decode("ascii")
    return "".join(ch.lower() for ch in text if ch.isalnum())


def _split_pipe(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, float) and math.isnan(value):
        return []
    return [part.strip() for part in str(value).split("|") if part.strip()]


def _build_legacy_index(df: pd.DataFrame) -> dict[str, list[int]]:
    index: dict[str, list[int]] = {}
    for idx, patient_id in enumerate(df["patient_id"].astype(str)):
        index.setdefault(_fold_key(patient_id), []).append(idx)
    return index


def _build_original_index(original_dir: Path) -> dict[str, Path]:
    index: dict[str, Path] = {}
    for path in original_dir.glob("*.json"):
        index[_fold_key(path.stem)] = path
    return index


def _lookup_original_patient_id(case: Case, original_index: dict[str, Path]) -> Optional[str]:
    prompt_stem = Path(case.prompt_file).name.replace("_en-prompt.txt", "")
    key = _fold_key(prompt_stem)

    path = original_index.get(key)
    if path is None:
        for idx_key, idx_path in original_index.items():
            if key in idx_key or idx_key in key:
                path = idx_path
                break
    if path is None:
        return None

    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    patient_id = data.get("id")
    return str(patient_id) if patient_id else None


def _select_legacy_row(
    case: Case,
    legacy_df: pd.DataFrame,
    key_to_rows: dict[str, list[int]],
    original_patient_id: Optional[str],
) -> tuple[pd.Series, str]:
    if original_patient_id:
        original_rows = key_to_rows.get(_fold_key(original_patient_id), [])
        if len(original_rows) == 1:
            return legacy_df.iloc[original_rows[0]], "original_id"
        if len(original_rows) > 1:
            raise ValueError(f"Ambiguous original-id legacy match for {case.case_id}")

    key = _fold_key(case.case_id)
    exact_rows = key_to_rows.get(key, [])
    if len(exact_rows) == 1:
        return legacy_df.iloc[exact_rows[0]], "exact"
    if len(exact_rows) > 1:
        raise ValueError(f"Ambiguous exact legacy match for {case.case_id}")

    prefix = case.case_id.split("_", 2)[:2]
    prefix_str = "_".join(prefix)
    candidates: list[tuple[float, int]] = []
    for idx, patient_id in enumerate(legacy_df["patient_id"].astype(str)):
        if not patient_id.startswith(prefix_str):
            continue
        score = difflib.SequenceMatcher(None, key, _fold_key(patient_id)).ratio()
        candidates.append((score, idx))

    if not candidates:
        raise ValueError(f"No legacy candidate found for {case.case_id}")

    candidates.sort(reverse=True)
    best_score, best_idx = candidates[0]
    second_score = candidates[1][0] if len(candidates) > 1 else 0.0

    if best_score < 0.97 or (len(candidates) > 1 and best_score - second_score < 0.01):
        preview = [(round(score, 4), legacy_df.iloc[idx]["patient_id"]) for score, idx in candidates[:5]]
        raise ValueError(
            f"Unsafe fuzzy match for {case.case_id}: best={best_score:.4f}, "
            f"second={second_score:.4f}, candidates={preview}"
        )

    return legacy_df.iloc[best_idx], "fuzzy"


def _build_diagnoses(row: pd.Series) -> tuple[list[Diagnosis], str]:
    pred_ids = _split_pipe(row.get("agent_prediction_ids"))
    pred_labels = _split_pipe(row.get("agent_prediction_labels"))
    n = max(len(pred_ids), len(pred_labels))
    diagnoses: list[Diagnosis] = []

    top1_fuzzy = row.get("fuzzy_score_top1")
    top1_fuzzy = None if pd.isna(top1_fuzzy) else float(top1_fuzzy)

    raw_lines: list[str] = []
    for i in range(n):
        predicted_id = pred_ids[i] if i < len(pred_ids) else None
        disease_name = pred_labels[i] if i < len(pred_labels) else ""
        if predicted_id and disease_name:
            raw_text = f"{i + 1}. {predicted_id} - {disease_name}"
        elif predicted_id:
            raw_text = f"{i + 1}. {predicted_id}"
        else:
            raw_text = f"{i + 1}. {disease_name}"
        raw_lines.append(raw_text)
        diagnoses.append(
            Diagnosis(
                rank=i + 1,
                raw_text=raw_text,
                disease_name=disease_name,
                predicted_id=predicted_id,
                fuzzy_score=top1_fuzzy if i == 0 else None,
                id_source="predicted" if predicted_id else "none",
            )
        )

    raw_response = "\n".join(raw_lines)
    if raw_response:
        raw_response += "\n"
    return diagnoses, raw_response


def _write_filtered_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def run_import(args: argparse.Namespace) -> Path:
    cases = load_cases(
        prompt_dir=args.prompt_dir,
        ground_truth_file=args.ground_truth_file,
        benchmark_ids_file=args.benchmark_ids_file,
    )
    legacy_df = pd.read_csv(args.legacy_csv)
    key_to_rows = _build_legacy_index(legacy_df)
    original_index = _build_original_index(args.original_phenopackets_dir)

    matcher = DiseaseMatcher(args.ground_truth_file)

    config = RunConfig(
        prompt_dir=args.prompt_dir,
        ground_truth_file=args.ground_truth_file,
        benchmark_ids_file=args.benchmark_ids_file,
        output_dir=args.output_root,
        backend="legacy_import",
        model_name="meta-llama/Llama-3.3-70B-Instruct",
        max_tokens=0,
        temperature=0.0,
        top_p=1.0,
        seed=0,
        max_diagnoses=10,
        batch_size=0,
        use_mondo=False,
        resume=False,
    )
    writer = ResultWriter(config)
    started_at = datetime.now(timezone.utc).isoformat()
    timestamp = datetime.now(timezone.utc).isoformat()

    imported_results: list[CaseResult] = []
    filtered_rows: list[dict[str, object]] = []
    mapping_rows: list[dict[str, object]] = []

    for case in cases:
        original_patient_id = _lookup_original_patient_id(case, original_index)
        row, match_method = _select_legacy_row(
            case,
            legacy_df,
            key_to_rows,
            original_patient_id,
        )
        diagnoses, raw_response = _build_diagnoses(row)
        (
            rank_by_id,
            rank_by_name,
            rank_by_id_or_name,
            rank_by_mondo,
            gold_mondo,
        ) = evaluate_case(case, diagnoses, matcher, None)

        result = CaseResult(
            case_id=case.case_id,
            prompt_file=case.prompt_file,
            gold_disease_id=case.gold_disease_id,
            gold_disease_label=case.gold_disease_label,
            gold_mondo_id=gold_mondo,
            raw_response=raw_response,
            diagnoses=diagnoses,
            gold_rank_by_id=rank_by_id,
            gold_rank_by_name=rank_by_name,
            gold_rank_by_id_or_name=rank_by_id_or_name,
            gold_rank_by_mondo=rank_by_mondo,
            reciprocal_rank_id=(1.0 / rank_by_id) if rank_by_id else 0.0,
            reciprocal_rank_name=(1.0 / rank_by_name) if rank_by_name else 0.0,
            reciprocal_rank_id_or_name=(1.0 / rank_by_id_or_name) if rank_by_id_or_name else 0.0,
            reciprocal_rank_mondo=0.0,
            error=None,
            latency_s=0.0,
            timestamp=timestamp,
        )
        writer.write_result(result)
        imported_results.append(result)

        filtered_row = row.to_dict()
        filtered_row["dx_case_id"] = case.case_id
        filtered_row["dx_prompt_file"] = case.prompt_file
        filtered_row["match_method"] = match_method
        filtered_rows.append(filtered_row)

        mapping_rows.append(
            {
                "dx_case_id": case.case_id,
                "legacy_patient_id": row["patient_id"],
                "original_patient_id": original_patient_id,
                "match_method": match_method,
                "prompt_file": case.prompt_file,
                "gold_disease_id": case.gold_disease_id,
                "gold_disease_label": case.gold_disease_label,
            }
        )

    metrics = compute_aggregate(imported_results)
    writer.write_metrics(metrics)
    writer.write_manifest(total_cases=len(cases), started_at=started_at)

    filtered_csv_path = writer.run_dir / "legacy_results_filtered.csv"
    mapping_csv_path = writer.run_dir / "legacy_import_mapping.csv"
    _write_filtered_csv(filtered_csv_path, filtered_rows)
    _write_filtered_csv(mapping_csv_path, mapping_rows)

    return writer.run_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--legacy-csv", type=Path, default=DEFAULT_LEGACY_CSV)
    parser.add_argument("--prompt-dir", type=Path, default=DEFAULT_PROMPT_DIR)
    parser.add_argument("--ground-truth-file", type=Path, default=DEFAULT_GT)
    parser.add_argument("--benchmark-ids-file", type=Path, default=DEFAULT_BENCHMARK_IDS)
    parser.add_argument(
        "--original-phenopackets-dir",
        type=Path,
        default=DEFAULT_ORIGINAL_PHENOPACKETS_DIR,
    )
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    return parser.parse_args()


if __name__ == "__main__":
    run_dir = run_import(parse_args())
    print(run_dir)
