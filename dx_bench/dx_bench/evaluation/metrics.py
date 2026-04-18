"""Evaluation: per-case scoring and aggregate metrics."""

from __future__ import annotations

import logging
import re
from typing import Optional

from dx_bench.data.schema import AggregateMetrics, Case, CaseResult, Diagnosis
from dx_bench.normalization.disease_matcher import DiseaseMatcher
from dx_bench.normalization.mondo_resolver import MondoResolver

logger = logging.getLogger(__name__)


def _normalize_omim(omim_id: str) -> str:
    """Normalize OMIM ID: strip leading zeros, uppercase prefix."""
    if not omim_id:
        return ""
    omim_id = omim_id.strip()
    if ":" in omim_id:
        prefix, num = omim_id.split(":", 1)
        return f"{prefix.upper()}:{num.lstrip('0') or '0'}"
    return omim_id


def _id_matches(predicted: Optional[str], gold: str) -> bool:
    """Check if predicted OMIM ID matches gold."""
    if not predicted:
        return False
    return _normalize_omim(predicted) == _normalize_omim(gold)


def _normalize_name(name: str) -> str:
    """Normalize disease names for exact string comparison."""
    if not name:
        return ""
    return re.sub(r"\s+", " ", name.strip().lower())


def _name_matches(
    diagnosis: Diagnosis,
    gold_label: str,
    matcher: DiseaseMatcher,
) -> bool:
    """Check if disease name matches gold via normalized exact equality."""
    del matcher  # Matching is evaluated on normalized names, not fuzzy score.

    gold_norm = _normalize_name(gold_label)
    if not gold_norm:
        return False

    if diagnosis.resolved_name and _normalize_name(diagnosis.resolved_name) == gold_norm:
        return True

    return _normalize_name(diagnosis.disease_name) == gold_norm


def evaluate_case(
    case: Case,
    diagnoses: list[Diagnosis],
    matcher: DiseaseMatcher,
    mondo: Optional[MondoResolver],
) -> tuple[
    Optional[int],  # gold_rank_by_id
    Optional[int],  # gold_rank_by_name
    Optional[int],  # gold_rank_by_id_or_name
    Optional[int],  # gold_rank_by_mondo
    Optional[str],  # gold_mondo_id
]:
    """Find the rank of the gold diagnosis under each criterion."""
    gold_id = case.gold_disease_id
    gold_label = case.gold_disease_label

    # Resolve gold Mondo ID
    gold_mondo: Optional[str] = None
    if mondo:
        gold_mondo = mondo.omim_to_mondo(gold_id)

    rank_by_id: Optional[int] = None
    rank_by_name: Optional[int] = None
    rank_by_id_or_name: Optional[int] = None
    rank_by_mondo: Optional[int] = None

    for dx in diagnoses:
        # Check ID match (predicted_id from LLM or resolved_id from fuzzy)
        id_match = _id_matches(dx.predicted_id, gold_id) or _id_matches(
            dx.resolved_id, gold_id
        )

        # Check name match
        name_match = _name_matches(dx, gold_label, matcher)

        # Check Mondo match
        mondo_match = False
        if mondo and gold_mondo and dx.mondo_id:
            mondo_match = mondo.is_match(dx.mondo_id, gold_mondo)

        if id_match and rank_by_id is None:
            rank_by_id = dx.rank
        if name_match and rank_by_name is None:
            rank_by_name = dx.rank
        if (id_match or name_match) and rank_by_id_or_name is None:
            rank_by_id_or_name = dx.rank
        if mondo_match and rank_by_mondo is None:
            rank_by_mondo = dx.rank

    return rank_by_id, rank_by_name, rank_by_id_or_name, rank_by_mondo, gold_mondo


def compute_aggregate(results: list[CaseResult]) -> AggregateMetrics:
    """Compute aggregate metrics across all case results."""
    n = len(results)
    if n == 0:
        return AggregateMetrics()

    n_errors = sum(1 for r in results if r.error is not None)

    def _recall_at_k(ranks: list[Optional[int]], k: int) -> float:
        return sum(1 for r in ranks if r is not None and r <= k) / n

    def _mrr(ranks: list[Optional[int]]) -> float:
        return sum(1.0 / r for r in ranks if r is not None) / n

    def _found_rate(ranks: list[Optional[int]]) -> float:
        return sum(1 for r in ranks if r is not None) / n

    def _mean_rank(ranks: list[Optional[int]]) -> float:
        found = [r for r in ranks if r is not None]
        return sum(found) / len(found) if found else 0.0

    id_ranks = [r.gold_rank_by_id for r in results]
    name_ranks = [r.gold_rank_by_name for r in results]
    ior_ranks = [r.gold_rank_by_id_or_name for r in results]
    mondo_ranks = [r.gold_rank_by_mondo for r in results]

    # Fuzzy match band counts
    n_auto = 0
    n_review = 0
    n_rejected = 0
    for r in results:
        for dx in r.diagnoses:
            if dx.fuzzy_score is not None:
                if dx.fuzzy_score >= 100:
                    n_auto += 1
                elif dx.fuzzy_score >= 85:
                    n_review += 1
                else:
                    n_rejected += 1

    return AggregateMetrics(
        n_cases=n,
        n_errors=n_errors,
        error_rate=n_errors / n,
        mrr_id=_mrr(id_ranks),
        mrr_name=_mrr(name_ranks),
        mrr_id_or_name=_mrr(ior_ranks),
        mrr_mondo=_mrr(mondo_ranks),
        recall_at_1_id=_recall_at_k(id_ranks, 1),
        recall_at_3_id=_recall_at_k(id_ranks, 3),
        recall_at_5_id=_recall_at_k(id_ranks, 5),
        recall_at_10_id=_recall_at_k(id_ranks, 10),
        recall_at_1_name=_recall_at_k(name_ranks, 1),
        recall_at_3_name=_recall_at_k(name_ranks, 3),
        recall_at_5_name=_recall_at_k(name_ranks, 5),
        recall_at_10_name=_recall_at_k(name_ranks, 10),
        recall_at_1_id_or_name=_recall_at_k(ior_ranks, 1),
        recall_at_3_id_or_name=_recall_at_k(ior_ranks, 3),
        recall_at_5_id_or_name=_recall_at_k(ior_ranks, 5),
        recall_at_10_id_or_name=_recall_at_k(ior_ranks, 10),
        recall_at_1_mondo=_recall_at_k(mondo_ranks, 1),
        recall_at_3_mondo=_recall_at_k(mondo_ranks, 3),
        recall_at_5_mondo=_recall_at_k(mondo_ranks, 5),
        recall_at_10_mondo=_recall_at_k(mondo_ranks, 10),
        found_rate_id=_found_rate(id_ranks),
        found_rate_name=_found_rate(name_ranks),
        found_rate_id_or_name=_found_rate(ior_ranks),
        found_rate_mondo=_found_rate(mondo_ranks),
        mean_rank_id=_mean_rank(id_ranks),
        mean_rank_name=_mean_rank(name_ranks),
        mean_rank_id_or_name=_mean_rank(ior_ranks),
        mean_rank_mondo=_mean_rank(mondo_ranks),
        n_fuzzy_auto_correct=n_auto,
        n_fuzzy_review=n_review,
        n_fuzzy_rejected=n_rejected,
    )
