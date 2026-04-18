from __future__ import annotations

import json
import sqlite3
from pathlib import Path


def _load_label_map(mondo_db: Path) -> dict[str, str]:
    conn = sqlite3.connect(str(mondo_db))
    cur = conn.cursor()
    cur.execute(
        """
        SELECT s.value, l.value
        FROM statements AS s
        JOIN rdfs_label_statement AS l
          ON s.subject = l.subject
        WHERE s.predicate IN (
            'skos:broadMatch',
            'skos:narrowMatch',
            'skos:closeMatch',
            'skos:exactMatch',
            'skos:relatedMatch',
            'oio:hasDbXref',
            'owl:sameAs'
        )
          AND s.subject LIKE 'MONDO:%'
        """
    )
    label_map: dict[str, str] = {}
    for disease_id, label in cur.fetchall():
        if disease_id and label and disease_id not in label_map:
            label_map[disease_id] = label
    conn.close()
    return label_map


def _primary_omim(rare_disease_ids: list[str]) -> str | None:
    for disease_id in rare_disease_ids:
        if disease_id.startswith("OMIM:"):
            return disease_id
    return None


def prepare_dataset(
    dataset_dir: Path,
    label_map: dict[str, str],
) -> tuple[int, int, int]:
    cases_path = dataset_dir / "cases.jsonl"
    benchmark_ids_path = dataset_dir / "benchmark_ids.txt"
    correct_results_path = dataset_dir / "correct_results.tsv"

    kept = 0
    skipped_no_omim = 0
    skipped_no_label = 0

    benchmark_ids: list[str] = []
    correct_results: list[str] = []

    with cases_path.open(encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            case_id = row["case_id"]
            prompt_file = row["prompt_file"]

            omim_id = _primary_omim(row.get("rare_disease_ids", []))
            if not omim_id:
                skipped_no_omim += 1
                continue

            label = label_map.get(omim_id)
            if not label:
                skipped_no_label += 1
                continue

            benchmark_ids.append(case_id)
            correct_results.append(f"{label}\t{omim_id}\t{prompt_file}")
            kept += 1

    benchmark_ids_path.write_text("\n".join(benchmark_ids) + "\n", encoding="utf-8")
    correct_results_path.write_text(
        "\n".join(correct_results) + "\n", encoding="utf-8"
    )

    return kept, skipped_no_omim, skipped_no_label


def main() -> None:
    root = Path(__file__).resolve().parent
    rarebench_root = root.parent / "PP2Prompt" / "prompts" / "rarebench"
    mondo_db = root.parent / "mondo.db"

    label_map = _load_label_map(mondo_db)

    for dataset in ["HMS", "LIRICAL", "MME", "RAMEDIS"]:
        kept, skipped_no_omim, skipped_no_label = prepare_dataset(
            rarebench_root / dataset,
            label_map,
        )
        print(
            f"{dataset}: kept={kept} skipped_no_omim={skipped_no_omim} "
            f"skipped_no_label={skipped_no_label}"
        )


if __name__ == "__main__":
    main()
