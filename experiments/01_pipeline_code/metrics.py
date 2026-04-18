from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional, Sequence

try:
    from rapidfuzz import fuzz  # type: ignore

    def fuzzy_score(left: str, right: str) -> float:
        return float(fuzz.token_set_ratio(left or "", right or ""))

except Exception:  # pragma: no cover
    import difflib

    def fuzzy_score(left: str, right: str) -> float:
        return 100.0 * difflib.SequenceMatcher(None, (left or "").lower(), (right or "").lower()).ratio()


CRITERIA = ("id_correct", "id_and_name_correct", "id_or_name_correct")
KS = (1, 3, 5, 10)


def normalize_id(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    match = re.match(r"^([A-Za-z]+):0*(\d+)$", raw)
    if match:
        return f"{match.group(1).upper()}:{match.group(2)}"
    if raw.isdigit():
        return str(int(raw))
    return raw.upper()


def normalize_name(value: str) -> str:
    text = str(value or "").lower().strip()
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def name_matches(predicted_name: str, truth_names: Sequence[str], fuzzy_threshold: float = 95.0) -> bool:
    normalized_predicted = normalize_name(predicted_name)
    if not normalized_predicted:
        return False
    normalized_truths = [normalize_name(name) for name in truth_names if normalize_name(name)]
    if not normalized_truths:
        return False
    if normalized_predicted in normalized_truths:
        return True
    best = max(fuzzy_score(normalized_predicted, truth_name) for truth_name in normalized_truths)
    return best >= float(fuzzy_threshold)


def criterion_flags(
    ranked_items: Sequence[Dict[str, Any]],
    truth_ids: Sequence[str],
    truth_names: Sequence[str],
    fuzzy_threshold: float = 95.0,
) -> Dict[str, List[bool]]:
    normalized_truth_ids = {normalize_id(value) for value in truth_ids if normalize_id(value)}
    flags = {criterion: [] for criterion in CRITERIA}
    for item in ranked_items:
        predicted_id = normalize_id(str(item.get("id") or item.get("disease_id") or ""))
        predicted_name = str(item.get("name") or item.get("label") or item.get("disease_name") or item.get("disease_label") or "")
        id_match = bool(predicted_id and predicted_id in normalized_truth_ids)
        name_match = name_matches(predicted_name, truth_names, fuzzy_threshold=fuzzy_threshold)
        flags["id_correct"].append(id_match)
        flags["id_and_name_correct"].append(id_match and (name_match or not truth_names))
        flags["id_or_name_correct"].append(id_match or name_match)
    return flags


def best_rank(flags: Sequence[bool]) -> Optional[int]:
    for index, is_correct in enumerate(flags):
        if is_correct:
            return index + 1
    return None


def hit_at(rank: Optional[int], k: int) -> float:
    if rank is None:
        return 0.0
    return 1.0 if rank <= int(k) else 0.0


def mrr(rank: Optional[int]) -> float:
    if rank is None or rank <= 0:
        return 0.0
    return 1.0 / float(rank)


def evaluate_ranked_items(
    ranked_items: Sequence[Dict[str, Any]],
    truth_ids: Sequence[str],
    truth_names: Sequence[str],
    ks: Iterable[int] = KS,
    fuzzy_threshold: float = 95.0,
) -> Dict[str, Dict[str, float]]:
    flags_by_criterion = criterion_flags(ranked_items, truth_ids, truth_names, fuzzy_threshold=fuzzy_threshold)
    metrics: Dict[str, Dict[str, float]] = {}
    for criterion, flags in flags_by_criterion.items():
        rank = best_rank(flags)
        criterion_metrics = {f"hit@{int(k)}": hit_at(rank, int(k)) for k in ks}
        criterion_metrics["mrr"] = mrr(rank)
        criterion_metrics["rank"] = float(rank) if rank is not None else 0.0
        criterion_metrics["found"] = 1.0 if rank is not None else 0.0
        metrics[criterion] = criterion_metrics
    return metrics


def summarize_evaluations(rows: Sequence[Dict[str, Dict[str, float]]], ks: Iterable[int] = KS) -> Dict[str, Dict[str, float]]:
    summary: Dict[str, Dict[str, float]] = {}
    row_count = len(rows)
    for criterion in CRITERIA:
        criterion_summary: Dict[str, float] = {}
        for key in [*(f"hit@{int(k)}" for k in ks), "mrr", "found"]:
            criterion_summary[key] = (
                sum(float(row.get(criterion, {}).get(key, 0.0)) for row in rows) / float(row_count)
                if row_count
                else 0.0
            )
        criterion_summary["n"] = float(row_count)
        summary[criterion] = criterion_summary
    return summary
