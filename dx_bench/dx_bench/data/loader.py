"""Load benchmark cases: match prompt files to ground truth using benchmark IDs."""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Optional

from .schema import Case

logger = logging.getLogger(__name__)


def _normalize_id(text: str) -> str:
    """Strip underscores, dashes, spaces and lowercase for fuzzy filename matching."""
    return text.replace("_", "").replace("-", "").replace(" ", "").lower()


def _load_ground_truth(gt_path: Path) -> dict[str, tuple[str, str]]:
    """Load correct_results.tsv → {normalized_prompt_stem: (disease_label, disease_id)}."""
    gt = {}
    with open(gt_path, encoding="utf-8") as f:
        reader = csv.reader(f, delimiter="\t")
        for row in reader:
            if len(row) < 3:
                continue
            label, disease_id, prompt_filename = row[0], row[1], row[2]
            # Normalize the prompt filename stem for matching
            stem = prompt_filename.replace("_en-prompt.txt", "")
            key = _normalize_id(stem)
            gt[key] = (label.strip(), disease_id.strip())
    logger.info("Loaded %d ground truth entries from %s", len(gt), gt_path)
    return gt


def _load_benchmark_ids(ids_path: Path) -> list[str]:
    """Load benchmark_ids file (one case ID per line)."""
    ids = []
    with open(ids_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                ids.append(line)
    logger.info("Loaded %d benchmark IDs from %s", len(ids), ids_path)
    return ids


def _build_prompt_file_index(prompt_dir: Path) -> dict[str, Path]:
    """Index all prompt files by normalized stem for fast lookup."""
    index: dict[str, Path] = {}
    for p in prompt_dir.glob("*_en-prompt.txt"):
        stem = p.name.replace("_en-prompt.txt", "")
        key = _normalize_id(stem)
        index[key] = p
    logger.info("Indexed %d prompt files in %s", len(index), prompt_dir)
    return index


def _match_id_to_prompt(
    case_id: str,
    prompt_index: dict[str, Path],
) -> Optional[Path]:
    """Match a benchmark ID to a prompt file using normalized substring matching."""
    clean_id = _normalize_id(case_id)

    # Try exact normalized match first
    if clean_id in prompt_index:
        return prompt_index[clean_id]

    # Fallback: substring containment (handles minor naming variations)
    for key, path in prompt_index.items():
        if clean_id in key or key in clean_id:
            return path

    return None


def _match_id_to_gt(
    case_id: str,
    gt: dict[str, tuple[str, str]],
) -> Optional[tuple[str, str]]:
    """Match a benchmark ID to a ground truth entry."""
    clean_id = _normalize_id(case_id)

    if clean_id in gt:
        return gt[clean_id]

    for key, val in gt.items():
        if clean_id in key or key in clean_id:
            return val

    return None


def load_cases(
    prompt_dir: Path,
    ground_truth_file: Path,
    benchmark_ids_file: Path,
    limit: Optional[int] = None,
    offset: int = 0,
) -> list[Case]:
    """Load and validate all benchmark cases.

    Returns a sorted list of Case objects (sorted by case_id for determinism).
    """
    benchmark_ids = _load_benchmark_ids(benchmark_ids_file)
    gt = _load_ground_truth(ground_truth_file)
    prompt_index = _build_prompt_file_index(prompt_dir)

    cases: list[Case] = []
    n_missing_prompt = 0
    n_missing_gt = 0

    for case_id in sorted(benchmark_ids):
        prompt_path = _match_id_to_prompt(case_id, prompt_index)
        if prompt_path is None:
            n_missing_prompt += 1
            logger.warning("No prompt file found for benchmark ID: %s", case_id)
            continue

        gt_entry = _match_id_to_gt(case_id, gt)
        if gt_entry is None:
            n_missing_gt += 1
            logger.warning("No ground truth found for benchmark ID: %s", case_id)
            continue

        gold_label, gold_id = gt_entry
        prompt_text = prompt_path.read_text(encoding="utf-8")

        cases.append(
            Case(
                case_id=case_id,
                prompt_file=str(prompt_path),
                prompt_text=prompt_text,
                gold_disease_label=gold_label,
                gold_disease_id=gold_id,
            )
        )

    if n_missing_prompt > 0:
        logger.warning("Cases missing prompt files: %d", n_missing_prompt)
    if n_missing_gt > 0:
        logger.warning("Cases missing ground truth: %d", n_missing_gt)

    # Apply offset and limit
    cases = cases[offset:]
    if limit is not None:
        cases = cases[:limit]

    logger.info(
        "Loaded %d cases (offset=%d, limit=%s, skipped: %d no-prompt, %d no-gt)",
        len(cases),
        offset,
        limit,
        n_missing_prompt,
        n_missing_gt,
    )
    return cases
