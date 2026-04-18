"""Disease name → OMIM ID normalization via exact + fuzzy matching."""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Optional

from rapidfuzz import fuzz

logger = logging.getLogger(__name__)


class DiseaseMatcher:
    """Two-tier disease name matcher: exact then fuzzy.

    Threshold bands:
        score == 100 → auto-correct
        85 <= score < 100 → flagged for review
        score < 85 → rejected (unresolved)
    """

    def __init__(
        self,
        ground_truth_file: Path,
        auto_threshold: int = 100,
        review_threshold: int = 85,
    ) -> None:
        self._auto_threshold = auto_threshold
        self._review_threshold = review_threshold
        # {lowercase_name: (original_name, OMIM_ID)}
        self._exact_lookup: dict[str, tuple[str, str]] = {}
        # For fuzzy: list of (name, OMIM_ID)
        self._all_diseases: list[tuple[str, str]] = []
        # Cache fuzzy results: {input_name_lower: (omim_id, ref_name, score)}
        self._fuzzy_cache: dict[str, tuple[Optional[str], Optional[str], float]] = {}

        self._load_ground_truth(ground_truth_file)

    def _load_ground_truth(self, gt_path: Path) -> None:
        """Build lookup from correct_results.tsv."""
        seen: set[str] = set()
        with open(gt_path, encoding="utf-8") as f:
            reader = csv.reader(f, delimiter="\t")
            for row in reader:
                if len(row) < 3:
                    continue
                label, disease_id = row[0].strip(), row[1].strip()
                key = label.lower()
                if key not in seen:
                    self._exact_lookup[key] = (label, disease_id)
                    self._all_diseases.append((label, disease_id))
                    seen.add(key)

        logger.info(
            "DiseaseMatcher loaded %d unique diseases from %s",
            len(self._all_diseases),
            gt_path,
        )

    def match(
        self, disease_name: str
    ) -> tuple[Optional[str], Optional[str], float, str]:
        """Match a disease name to an OMIM ID.

        Returns:
            (omim_id, reference_name, fuzzy_score, band)
            band is one of: "exact", "auto", "review", "rejected"
        """
        name_lower = disease_name.strip().lower()

        # Exact match (score = 100, band = "exact")
        if name_lower in self._exact_lookup:
            ref_name, omim_id = self._exact_lookup[name_lower]
            return omim_id, ref_name, 100.0, "exact"

        # Check cache
        if name_lower in self._fuzzy_cache:
            omim_id, ref_name, score = self._fuzzy_cache[name_lower]
            band = self._score_to_band(score)
            return omim_id, ref_name, score, band

        # Fuzzy match
        best_score = 0.0
        best_match: Optional[tuple[str, str]] = None

        for ref_name, omim_id in self._all_diseases:
            score = fuzz.token_set_ratio(name_lower, ref_name.lower())
            if score > best_score:
                best_score = score
                best_match = (ref_name, omim_id)

        if best_match is not None and best_score >= self._review_threshold:
            ref_name, omim_id = best_match
            self._fuzzy_cache[name_lower] = (omim_id, ref_name, best_score)
            band = self._score_to_band(best_score)
            return omim_id, ref_name, best_score, band

        # Below review threshold → rejected
        self._fuzzy_cache[name_lower] = (None, None, best_score)
        return None, None, best_score, "rejected"

    def _score_to_band(self, score: float) -> str:
        if score >= self._auto_threshold:
            return "auto"
        elif score >= self._review_threshold:
            return "review"
        return "rejected"

    def match_omim_id(self, predicted_id: str) -> bool:
        """Check if a predicted OMIM ID exists in our ground truth set."""
        for _, omim_id in self._all_diseases:
            if predicted_id.strip() == omim_id:
                return True
        return False
