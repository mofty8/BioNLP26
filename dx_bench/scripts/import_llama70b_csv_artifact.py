"""Import the explicit llama70B CSV artifact into a dx_bench-style run folder.

This importer:
1. loads the effective phenopacket subset used by dx_bench,
2. maps each dx_bench case to the corresponding legacy patient id,
3. replays the saved per-case response logs,
4. parses and evaluates them with the current dx_bench logic, and
5. writes a native-looking run directory under results/.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from dx_bench.config import RunConfig
from dx_bench.data.loader import load_cases
from dx_bench.data.schema import Case, CaseResult
from dx_bench.evaluation.metrics import compute_aggregate, evaluate_case
from dx_bench.io.writer import ResultWriter
from dx_bench.normalization.disease_matcher import DiseaseMatcher
from dx_bench.parsing.response_parser import parse_response


DEFAULT_SOURCE_CSV = Path(
    "/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/PhenoPacket_LLM/"
    "llama70B__20260102_113137.csv"
)
DEFAULT_LOGS_DIR = Path(
    "/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/PhenoPacket_LLM/"
    "llama70Blogs_20260102_113137"
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
    "llama70b-csv-import/phenopacket"
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


def _build_source_index(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {_fold_key(row["patient_id"]): row for row in rows}


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


def _select_source_row(
    case: Case,
    source_index: dict[str, dict[str, str]],
    original_patient_id: Optional[str],
) -> tuple[dict[str, str], str]:
    if original_patient_id:
        row = source_index.get(_fold_key(original_patient_id))
        if row is not None:
            return row, "original_id"

    row = source_index.get(_fold_key(case.case_id))
    if row is not None:
        return row, "case_id"

    raise KeyError(f"No source row found for {case.case_id}")


def _read_response_text(log_path: Path) -> str:
    text = log_path.read_text(encoding="utf-8", errors="replace")
    marker = "RESPONSE:\n"
    idx = text.find(marker)
    return text[idx + len(marker):].strip() if idx >= 0 else ""


def _canonicalize_response(raw_response: str) -> str:
    """Convert '1. Disease (OMIM:123456)' to parser-friendly OMIM-first lines."""
    lines: list[str] = []
    for line in raw_response.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        match = re.match(r"^(\d+)\s*[.)]\s*(.*?)\s*\((OMIM:\d+)\)\s*$", stripped)
        if match:
            rank, disease_name, omim_id = match.groups()
            lines.append(f"{rank}. {omim_id} - {disease_name.strip()}")
        else:
            lines.append(stripped)
    return "\n".join(lines)


def _source_log_path(logs_dir: Path, patient_id: str) -> Path:
    safe_id = "".join(ch for ch in patient_id if ch.isalnum() or ch in ("-", "_"))
    return logs_dir / f"{safe_id}.txt"


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
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
    with open(args.source_csv, encoding="utf-8") as f:
        source_rows = list(csv.DictReader(f))
    source_index = _build_source_index(source_rows)
    original_index = _build_original_index(args.original_phenopackets_dir)

    matcher = DiseaseMatcher(args.ground_truth_file)
    config = RunConfig(
        prompt_dir=args.prompt_dir,
        ground_truth_file=args.ground_truth_file,
        benchmark_ids_file=args.benchmark_ids_file,
        output_dir=args.output_root,
        backend="legacy_csv_import",
        model_name="legacy/llama70B",
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

    imported_results: list[CaseResult] = []
    filtered_rows: list[dict[str, object]] = []
    mapping_rows: list[dict[str, object]] = []

    for case in cases:
        original_patient_id = _lookup_original_patient_id(case, original_index)
        row, match_method = _select_source_row(case, source_index, original_patient_id)
        log_path = _source_log_path(args.logs_dir, row["patient_id"])
        raw_response = _read_response_text(log_path)
        canonical_response = _canonicalize_response(raw_response)
        diagnoses, parse_warnings = parse_response(canonical_response)

        for dx in diagnoses:
            omim_id, ref_name, score, _band = matcher.match(dx.disease_name)
            dx.resolved_id = omim_id
            dx.resolved_name = ref_name
            dx.fuzzy_score = score

            has_predicted = dx.predicted_id is not None
            has_resolved = dx.resolved_id is not None
            if has_predicted and has_resolved:
                dx.id_source = "both"
            elif has_predicted:
                dx.id_source = "predicted"
            elif has_resolved:
                dx.id_source = "resolved"
            else:
                dx.id_source = "none"

        (
            rank_by_id,
            rank_by_name,
            rank_by_id_or_name,
            rank_by_mondo,
            gold_mondo,
        ) = evaluate_case(case, diagnoses, matcher, None)

        timestamp = datetime.now(timezone.utc).isoformat()
        result = CaseResult(
            case_id=case.case_id,
            prompt_file=case.prompt_file,
            gold_disease_id=case.gold_disease_id,
            gold_disease_label=case.gold_disease_label,
            gold_mondo_id=gold_mondo,
            raw_response=raw_response,
            diagnoses=diagnoses,
            parse_warnings=parse_warnings,
            gold_rank_by_id=rank_by_id,
            gold_rank_by_name=rank_by_name,
            gold_rank_by_id_or_name=rank_by_id_or_name,
            gold_rank_by_mondo=rank_by_mondo,
            reciprocal_rank_id=(1.0 / rank_by_id) if rank_by_id else 0.0,
            reciprocal_rank_name=(1.0 / rank_by_name) if rank_by_name else 0.0,
            reciprocal_rank_id_or_name=(1.0 / rank_by_id_or_name) if rank_by_id_or_name else 0.0,
            reciprocal_rank_mondo=0.0,
            error="empty_parse" if not diagnoses else None,
            latency_s=0.0,
            timestamp=timestamp,
        )
        writer.write_result(result)
        imported_results.append(result)

        filtered_row = dict(row)
        filtered_row["dx_case_id"] = case.case_id
        filtered_row["dx_prompt_file"] = case.prompt_file
        filtered_row["match_method"] = match_method
        filtered_rows.append(filtered_row)

        mapping_rows.append(
            {
                "dx_case_id": case.case_id,
                "source_patient_id": row["patient_id"],
                "original_patient_id": original_patient_id,
                "match_method": match_method,
                "prompt_file": case.prompt_file,
                "source_log_file": str(log_path.name),
                "gold_disease_id": case.gold_disease_id,
                "gold_disease_label": case.gold_disease_label,
            }
        )

    metrics = compute_aggregate(imported_results)
    writer.write_metrics(metrics)
    writer.write_manifest(total_cases=len(imported_results), started_at=started_at)

    _write_csv(writer.run_dir / "source_results_filtered.csv", filtered_rows)
    _write_csv(writer.run_dir / "source_import_mapping.csv", mapping_rows)

    return writer.run_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-csv", type=Path, default=DEFAULT_SOURCE_CSV)
    parser.add_argument("--logs-dir", type=Path, default=DEFAULT_LOGS_DIR)
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
