#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import importlib.util
from collections import Counter
from pathlib import Path
from typing import Dict, List


def load_metrics_module(project_root: Path):
    metrics_path = project_root / "phenodp_gemma3_pipeline" / "metrics.py"
    spec = importlib.util.spec_from_file_location("metrics_local", metrics_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze fuzzy name similarity for benchmark predictions.")
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--results-csv", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--fuzzy-threshold", type=float, default=75.0)
    return parser.parse_args()


def best_truth_match(metrics, predicted_name: str, truth_labels: List[str]) -> Dict[str, object]:
    predicted_norm = metrics.normalize_name(predicted_name)
    best_score = 0.0
    best_truth = ""
    for truth_label in truth_labels:
        truth_norm = metrics.normalize_name(truth_label)
        score = float(metrics.fuzzy_score(predicted_norm, truth_norm))
        if score > best_score:
            best_score = score
            best_truth = truth_label
    return {
        "predicted_name_normalized": predicted_norm,
        "best_truth_label": best_truth,
        "best_truth_label_normalized": metrics.normalize_name(best_truth),
        "best_fuzzy_score": best_score,
        "name_match_95": bool(metrics.name_matches(predicted_name, truth_labels, fuzzy_threshold=95.0)),
    }


def write_csv(path: Path, rows: List[Dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> None:
    args = parse_args()
    project_root = Path(args.project_root)
    results_csv = Path(args.results_csv)
    output_dir = Path(args.output_dir)
    metrics = load_metrics_module(project_root)

    rows = list(csv.DictReader(results_csv.open(encoding="utf-8")))

    scored_rows: List[Dict[str, object]] = []
    wrong_id_pair_counts: Counter = Counter()

    for row in rows:
        truth_ids = [value for value in row["truth_ids"].split("|") if value]
        truth_labels = [value for value in row["truth_labels"].split("|") if value]
        selected_candidate_id = str(row.get("selected_candidate_id") or "")
        selected_candidate_name = str(row.get("selected_candidate_name") or "")
        matched = best_truth_match(metrics, selected_candidate_name, truth_labels)

        normalized_truth_ids = {
            metrics.normalize_id(value) for value in truth_ids if metrics.normalize_id(value)
        }
        normalized_selected_id = metrics.normalize_id(selected_candidate_id)
        id_match = bool(normalized_selected_id and normalized_selected_id in normalized_truth_ids)
        fuzzy_ge_threshold = matched["best_fuzzy_score"] >= float(args.fuzzy_threshold)

        scored_row = {
            "patient_id": row["patient_id"],
            "truth_ids": row["truth_ids"],
            "truth_labels": row["truth_labels"],
            "selected_candidate_id": selected_candidate_id,
            "selected_candidate_name": selected_candidate_name,
            "selected_candidate_name_normalized": matched["predicted_name_normalized"],
            "best_truth_label": matched["best_truth_label"],
            "best_truth_label_normalized": matched["best_truth_label_normalized"],
            "best_fuzzy_score": round(float(matched["best_fuzzy_score"]), 2),
            "id_match": int(id_match),
            "name_match_95": int(bool(matched["name_match_95"])),
            "fuzzy_ge_threshold": int(bool(fuzzy_ge_threshold)),
            "parse_mode": row.get("parse_mode", ""),
            "pred1_id": row.get("pred1_id", ""),
            "pred1_name": row.get("pred1_name", ""),
            "pred2_id": row.get("pred2_id", ""),
            "pred2_name": row.get("pred2_name", ""),
            "pred3_id": row.get("pred3_id", ""),
            "pred3_name": row.get("pred3_name", ""),
        }
        scored_rows.append(scored_row)

        if fuzzy_ge_threshold and not id_match:
            wrong_id_pair_counts[
                (
                    selected_candidate_name,
                    str(matched["best_truth_label"]),
                    round(float(matched["best_fuzzy_score"]), 1),
                )
            ] += 1

    ge_threshold_rows = [
        row for row in scored_rows if float(row["best_fuzzy_score"]) >= float(args.fuzzy_threshold)
    ]
    ge_threshold_wrong_id_rows = [row for row in ge_threshold_rows if not int(row["id_match"])]

    grouped_rows: List[Dict[str, object]] = []
    for (predicted_name, truth_label, best_fuzzy_score), count in wrong_id_pair_counts.most_common():
        grouped_rows.append(
            {
                "predicted_name": predicted_name,
                "best_truth_label": truth_label,
                "best_fuzzy_score": best_fuzzy_score,
                "n_cases": count,
            }
        )

    write_csv(output_dir / "selected_prediction_fuzzy_scores.csv", scored_rows)
    write_csv(output_dir / f"selected_prediction_fuzzy_ge{int(args.fuzzy_threshold)}.csv", ge_threshold_rows)
    write_csv(
        output_dir / f"selected_prediction_fuzzy_ge{int(args.fuzzy_threshold)}_id_wrong.csv",
        ge_threshold_wrong_id_rows,
    )
    write_csv(
        output_dir / f"selected_prediction_fuzzy_ge{int(args.fuzzy_threshold)}_id_wrong_pairs.csv",
        grouped_rows,
    )

    summary = {
        "n_cases": len(scored_rows),
        f"n_fuzzy_ge_{int(args.fuzzy_threshold)}": len(ge_threshold_rows),
        f"n_fuzzy_ge_{int(args.fuzzy_threshold)}_id_wrong": len(ge_threshold_wrong_id_rows),
        f"n_fuzzy_ge_{int(args.fuzzy_threshold)}_id_correct": len(ge_threshold_rows) - len(ge_threshold_wrong_id_rows),
        "n_unique_wrong_id_pairs": len(grouped_rows),
    }
    (output_dir / "summary.txt").write_text(
        "\n".join(f"{key}={value}" for key, value in summary.items()) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
