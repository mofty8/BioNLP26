#!/usr/bin/env python3
"""
Policy-adjusted evaluation for all dx_bench results.jsonl runs.

Applies the three-tier benchmark policy (strict_merge / family_partial_credit /
do_not_merge) from the clinically_similar_disease_analysis_20260409 results to
every completed dx_bench run and outputs a comparison table alongside the
original strict (exact-match) metrics.

Usage:
    python policy_eval_dxbench.py
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

DXBENCH_BASE = Path(__file__).parent
RESULTS_DIR = DXBENCH_BASE / "results"

POLICY_DIR = (
    Path("/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket")
    / "clinically_similar_disease_analysis_20260409"
    / "results"
)
POLICY_CSV = POLICY_DIR / "benchmark_policy_recommendations.csv"
FAMILIES_CSV = POLICY_DIR / "candidate_disease_families.csv"

OUTPUT_JSON = RESULTS_DIR / "policy_eval_dxbench.json"
OUTPUT_MD = RESULTS_DIR / "policy_eval_dxbench.md"

# ---------------------------------------------------------------------------
# Run registry: (model_label, dataset) -> results.jsonl path
# gemma-3-27b phenopacket is excluded: no results.jsonl available.
# ---------------------------------------------------------------------------

RUNS: List[Tuple[str, str, Path]] = [
    # (model_label, dataset, results_jsonl)

    # ── PhenoPacket ──────────────────────────────────────────────────────────
    (
        "llama-3.3-70b",
        "phenopacket",
        RESULTS_DIR / "llama-3.3-70b-instruct_http/phenopacket/Llama-3.3-70B-Instruct_20260412_121006_b035f758/results.jsonl",
    ),
    (
        "llama70b-legacy",
        "phenopacket",
        RESULTS_DIR / "llama70b-csv-import/phenopacket/llama70B_20260402_171920_29f3bdfd/results.jsonl",
    ),
    (
        "gemma-4-31b",
        "phenopacket",
        RESULTS_DIR / "gemma-4-31b-it_http/phenopacket/gemma-4-31B-it_20260411_170827_3b3a9b82/results.jsonl",
    ),
    (
        "med42-70b",
        "phenopacket",
        RESULTS_DIR / "llama3-med42-70b_http/phenopacket/Llama3-Med42-70B_20260404_020229_f0f8d928/results.jsonl",
    ),
    (
        "qwen2.5-32b",
        "phenopacket",
        RESULTS_DIR / "qwen2.5-32b-instruct_http/phenopacket/Qwen2.5-32B-Instruct_20260402_175138_d9bcd712/results.jsonl",
    ),
    (
        "medgemma-27b",
        "phenopacket",
        RESULTS_DIR / "medgemma-27b-it_http/phenopacket/medgemma-27b-it_20260408_181533_c3f9a40e/results.jsonl",
    ),
    (
        "med42-8b",
        "phenopacket",
        RESULTS_DIR / "llama3-med42-8b_http/phenopacket/Llama3-Med42-8B_20260403_101811_75511eab/results.jsonl",
    ),

    # ── RareBench / HMS ──────────────────────────────────────────────────────
    (
        "llama-3.3-70b",
        "HMS",
        RESULTS_DIR / "llama-3.3-70b-instruct_http/rarebench/HMS/Llama-3.3-70B-Instruct_20260411_233758_72a48380/results.jsonl",
    ),
    (
        "med42-70b",
        "HMS",
        RESULTS_DIR / "llama3-med42-70b_http/rarebench/HMS/Llama3-Med42-70B_20260404_074200_20b68b58/results.jsonl",
    ),
    (
        "gemma-3-27b",
        "HMS",
        RESULTS_DIR / "rarebench/HMS/gemma-3-27b-it_20260401_211659_07b889bb/results.jsonl",
    ),
    (
        "gemma-4-31b",
        "HMS",
        RESULTS_DIR / "gemma-4-31b-it_http/rarebench/HMS/gemma-4-31B-it_20260411_174619_48528e04/results.jsonl",
    ),
    (
        "medgemma-27b",
        "HMS",
        RESULTS_DIR / "medgemma-27b-it_http/rarebench/HMS/medgemma-27b-it_20260408_190455_2f25e179/results.jsonl",
    ),
    (
        "qwen2.5-32b",
        "HMS",
        RESULTS_DIR / "qwen2.5-32b-instruct_http/rarebench/HMS/Qwen2.5-32B-Instruct_20260402_200314_6ed61b29/results.jsonl",
    ),
    (
        "med42-8b",
        "HMS",
        RESULTS_DIR / "llama3-med42-8b_http/rarebench/HMS/Llama3-Med42-8B_20260403_105101_a26f9223/results.jsonl",
    ),

    # ── RareBench / LIRICAL ───────────────────────────────────────────────────
    (
        "llama-3.3-70b",
        "LIRICAL",
        RESULTS_DIR / "llama-3.3-70b-instruct_http/rarebench/LIRICAL/Llama-3.3-70B-Instruct_20260411_233953_f4cf36a1/results.jsonl",
    ),
    (
        "med42-70b",
        "LIRICAL",
        RESULTS_DIR / "llama3-med42-70b_http/rarebench/LIRICAL/Llama3-Med42-70B_20260404_074348_65999459/results.jsonl",
    ),
    (
        "gemma-3-27b",
        "LIRICAL",
        RESULTS_DIR / "rarebench/LIRICAL/gemma-3-27b-it_20260401_234212_8d28b67d/results.jsonl",
    ),
    (
        "gemma-4-31b",
        "LIRICAL",
        RESULTS_DIR / "gemma-4-31b-it_http/rarebench/LIRICAL/gemma-4-31B-it_20260411_174656_acece184/results.jsonl",
    ),
    (
        "medgemma-27b",
        "LIRICAL",
        RESULTS_DIR / "medgemma-27b-it_http/rarebench/LIRICAL/medgemma-27b-it_20260408_190558_262424e5/results.jsonl",
    ),
    (
        "qwen2.5-32b",
        "LIRICAL",
        RESULTS_DIR / "qwen2.5-32b-instruct_http/rarebench/LIRICAL/Qwen2.5-32B-Instruct_20260402_200519_38f400c4/results.jsonl",
    ),
    (
        "med42-8b",
        "LIRICAL",
        RESULTS_DIR / "llama3-med42-8b_http/rarebench/LIRICAL/Llama3-Med42-8B_20260403_105126_d8cd53b7/results.jsonl",
    ),

    # ── RareBench / MME ───────────────────────────────────────────────────────
    (
        "llama-3.3-70b",
        "MME",
        RESULTS_DIR / "llama-3.3-70b-instruct_http/rarebench/MME/Llama-3.3-70B-Instruct_20260411_234814_0a960edd/results.jsonl",
    ),
    (
        "med42-70b",
        "MME",
        RESULTS_DIR / "llama3-med42-70b_http/rarebench/MME/Llama3-Med42-70B_20260404_075403_4ed9ca37/results.jsonl",
    ),
    (
        "gemma-3-27b",
        "MME",
        RESULTS_DIR / "rarebench/MME/gemma-3-27b-it_20260401_234115_d03d1c74/results.jsonl",
    ),
    (
        "gemma-4-31b",
        "MME",
        RESULTS_DIR / "gemma-4-31b-it_http/rarebench/MME/gemma-4-31B-it_20260411_174849_cd1ee2ec/results.jsonl",
    ),
    (
        "medgemma-27b",
        "MME",
        RESULTS_DIR / "medgemma-27b-it_http/rarebench/MME/medgemma-27b-it_20260408_190838_0abc2dcf/results.jsonl",
    ),
    (
        "qwen2.5-32b",
        "MME",
        RESULTS_DIR / "qwen2.5-32b-instruct_http/rarebench/MME/Qwen2.5-32B-Instruct_20260402_201244_c0d68d7d/results.jsonl",
    ),
    (
        "med42-8b",
        "MME",
        RESULTS_DIR / "llama3-med42-8b_http/rarebench/MME/Llama3-Med42-8B_20260403_105310_203d8897/results.jsonl",
    ),

    # ── RareBench / RAMEDIS ───────────────────────────────────────────────────
    (
        "llama-3.3-70b",
        "RAMEDIS",
        RESULTS_DIR / "llama-3.3-70b-instruct_http/rarebench/RAMEDIS/Llama-3.3-70B-Instruct_20260411_234927_97669834/results.jsonl",
    ),
    (
        "med42-70b",
        "RAMEDIS",
        RESULTS_DIR / "llama3-med42-70b_http/rarebench/RAMEDIS/Llama3-Med42-70B_20260404_075457_fc915180/results.jsonl",
    ),
    (
        "gemma-3-27b",
        "RAMEDIS",
        RESULTS_DIR / "rarebench/RAMEDIS/gemma-3-27b-it_20260401_234825_a2cf7f4c/results.jsonl",
    ),
    (
        "gemma-4-31b",
        "RAMEDIS",
        RESULTS_DIR / "gemma-4-31b-it_http/rarebench/RAMEDIS/gemma-4-31B-it_20260411_174917_1b9fad0f/results.jsonl",
    ),
    (
        "medgemma-27b",
        "RAMEDIS",
        RESULTS_DIR / "medgemma-27b-it_http/rarebench/RAMEDIS/medgemma-27b-it_20260408_190909_c562d4cd/results.jsonl",
    ),
    (
        "qwen2.5-32b",
        "RAMEDIS",
        RESULTS_DIR / "qwen2.5-32b-instruct_http/rarebench/RAMEDIS/Qwen2.5-32B-Instruct_20260402_201351_b937159a/results.jsonl",
    ),
    (
        "med42-8b",
        "RAMEDIS",
        RESULTS_DIR / "llama3-med42-8b_http/rarebench/RAMEDIS/Llama3-Med42-8B_20260403_105321_6455f175/results.jsonl",
    ),
]


# ---------------------------------------------------------------------------
# ID normalisation (mirrors metrics.py and policy_adjusted_evaluation.py)
# ---------------------------------------------------------------------------

def _normalize_id(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    m = re.match(r"^([A-Za-z]+):0*(\d+)$", raw)
    if m:
        return f"{m.group(1).upper()}:{m.group(2)}"
    if raw.isdigit():
        return str(int(raw))
    return raw.upper()


# ---------------------------------------------------------------------------
# Load policy index
# ---------------------------------------------------------------------------

def load_policy(
    policy_csv: Path, families_csv: Path
) -> Tuple[Dict[str, Tuple[str, float]], Dict[str, str], Dict[str, Tuple[str, float]]]:
    """
    Returns:
        omim_policy:    omim_id -> (policy, partial_credit_weight)
        omim_to_family: omim_id -> family_name
        family_policy:  family_name -> (policy, partial_credit_weight)
    """
    family_policy: Dict[str, Tuple[str, float]] = {}
    with policy_csv.open() as fh:
        for row in csv.DictReader(fh):
            fname = row["family"].strip()
            policy = row["benchmark_policy"].strip()
            weight_str = row["partial_credit_weight"].strip()
            weight = float(weight_str) if weight_str else 0.0
            family_policy[fname] = (policy, weight)

    omim_to_family: Dict[str, str] = {}
    with families_csv.open() as fh:
        for row in csv.DictReader(fh):
            fname = row["family"].strip()
            for raw_id in row["disease_ids_found"].strip().split("|"):
                nid = _normalize_id(raw_id.strip())
                if nid:
                    omim_to_family[nid] = fname

    omim_policy: Dict[str, Tuple[str, float]] = {}
    for nid, fname in omim_to_family.items():
        if fname in family_policy:
            omim_policy[nid] = family_policy[fname]

    return omim_policy, omim_to_family, family_policy


# ---------------------------------------------------------------------------
# Policy score for a single (pred, truth) pair
# ---------------------------------------------------------------------------

def _policy_score(
    pred_id: str,
    truth_id: str,
    omim_policy: Dict[str, Tuple[str, float]],
    omim_to_family: Dict[str, str],
) -> float:
    pred_norm = _normalize_id(pred_id)
    truth_norm = _normalize_id(truth_id)
    if not pred_norm or not truth_norm:
        return 0.0
    if pred_norm == truth_norm:
        return 1.0
    truth_family = omim_to_family.get(truth_norm)
    pred_family = omim_to_family.get(pred_norm)
    if truth_family is None or pred_family is None or truth_family != pred_family:
        return 0.0
    policy_entry = omim_policy.get(truth_norm)
    if policy_entry is None:
        return 0.0
    pol, weight = policy_entry
    if pol == "strict_merge":
        return 1.0
    if pol == "family_partial_credit":
        return weight
    return 0.0  # do_not_merge


# ---------------------------------------------------------------------------
# Evaluate a single results.jsonl file
# ---------------------------------------------------------------------------

KS = (1, 3, 5, 10)


def evaluate_jsonl(
    jsonl_path: Path,
    omim_policy: Dict[str, Tuple[str, float]],
    omim_to_family: Dict[str, str],
) -> Dict:
    """
    Returns aggregate dict with both strict and policy metrics.

    ID resolution mirrors metrics.py:
      - Use predicted_id if present; also consider resolved_id as fallback.
      - Best policy score across predicted_id and resolved_id is taken.
    """
    case_rows: List[Dict] = []

    with jsonl_path.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            case = json.loads(line)

            gold_id = case.get("gold_disease_id", "")
            gold_norm = _normalize_id(gold_id)
            diagnoses = case.get("diagnoses", [])

            # Build ranked list of (rank, best_policy_score, is_exact)
            scores_at_rank: List[float] = []
            exact_at_rank: List[bool] = []

            for dx in sorted(diagnoses, key=lambda d: d.get("rank", 999)):
                # Candidate IDs to consider (mirrors metrics.py id_match logic)
                candidate_ids = []
                if dx.get("predicted_id"):
                    candidate_ids.append(dx["predicted_id"])
                if dx.get("resolved_id"):
                    candidate_ids.append(dx["resolved_id"])

                # Best policy score across all candidate IDs for this diagnosis
                best_pol = max(
                    (_policy_score(cid, gold_id, omim_policy, omim_to_family) for cid in candidate_ids),
                    default=0.0,
                )
                scores_at_rank.append(best_pol)

                # Strict exact match
                is_exact = any(_normalize_id(cid) == gold_norm for cid in candidate_ids if cid)
                exact_at_rank.append(is_exact)

            # Compute per-case metrics
            row: Dict = {"case_id": case.get("case_id", ""), "gold_id": gold_id}

            # Policy MRR: first rank with score > 0
            policy_mrr = 0.0
            for i, s in enumerate(scores_at_rank):
                if s > 0.0:
                    policy_mrr = 1.0 / (i + 1)
                    break
            row["policy_mrr"] = policy_mrr

            # Strict MRR
            strict_mrr = 0.0
            for i, ex in enumerate(exact_at_rank):
                if ex:
                    strict_mrr = 1.0 / (i + 1)
                    break
            row["strict_mrr"] = strict_mrr

            for k in KS:
                top_k_pol = scores_at_rank[:k]
                top_k_ex = exact_at_rank[:k]
                row[f"policy_hit@{k}"] = 1.0 if any(s > 0.0 for s in top_k_pol) else 0.0
                row[f"policy_score@{k}"] = max(top_k_pol, default=0.0)
                row[f"strict_hit@{k}"] = 1.0 if any(top_k_ex) else 0.0

            case_rows.append(row)

    if not case_rows:
        return {}

    n = len(case_rows)
    summary: Dict = {"n": n}
    metric_keys = [k for k in case_rows[0] if k not in ("case_id", "gold_id")]
    for k in metric_keys:
        summary[k] = sum(r[k] for r in case_rows) / n

    return summary


# ---------------------------------------------------------------------------
# Printing helpers
# ---------------------------------------------------------------------------

def _pct(v: float) -> str:
    return f"{v * 100:.1f}%"


def _fmt(v) -> str:
    if isinstance(v, float):
        return f"{v:.4f}"
    return str(v)


def print_table(results: Dict[Tuple[str, str], Dict]) -> None:
    datasets = ["phenopacket", "HMS", "LIRICAL", "MME", "RAMEDIS"]
    models = [
        "llama70b-legacy", "llama-3.3-70b", "med42-70b",
        "gemma-4-31b", "gemma-3-27b", "qwen2.5-32b",
        "medgemma-27b", "med42-8b",
    ]

    for ds in datasets:
        print(f"\n{'='*80}")
        print(f" Dataset: {ds}")
        print(f"{'='*80}")
        header = f"{'Model':<20} {'N':>5}  {'Strict':^35}  {'Policy (family-aware)':^35}"
        sub    = f"{'':20} {'':5}  {'R@1':>6} {'R@3':>6} {'R@5':>6} {'R@10':>6} {'MRR':>6}  {'R@1':>6} {'R@3':>6} {'R@5':>6} {'R@10':>6} {'MRR':>6}"
        print(header)
        print(sub)
        print("-" * 85)
        for model in models:
            key = (model, ds)
            if key not in results:
                continue
            s = results[key]
            n = s.get("n", 0)
            sr1  = s.get("strict_hit@1", 0)
            sr3  = s.get("strict_hit@3", 0)
            sr5  = s.get("strict_hit@5", 0)
            sr10 = s.get("strict_hit@10", 0)
            smrr = s.get("strict_mrr", 0)
            pr1  = s.get("policy_hit@1", 0)
            pr3  = s.get("policy_hit@3", 0)
            pr5  = s.get("policy_hit@5", 0)
            pr10 = s.get("policy_hit@10", 0)
            pmrr = s.get("policy_mrr", 0)
            print(
                f"{model:<20} {n:>5}  "
                f"{sr1:>6.3f} {sr3:>6.3f} {sr5:>6.3f} {sr10:>6.3f} {smrr:>6.3f}  "
                f"{pr1:>6.3f} {pr3:>6.3f} {pr5:>6.3f} {pr10:>6.3f} {pmrr:>6.3f}"
            )


def print_delta_table(results: Dict[Tuple[str, str], Dict]) -> None:
    """Show gain from policy vs strict at R@1 and MRR."""
    datasets = ["phenopacket", "HMS", "LIRICAL", "MME", "RAMEDIS"]
    models = [
        "llama70b-legacy", "llama-3.3-70b", "med42-70b",
        "gemma-4-31b", "gemma-3-27b", "qwen2.5-32b",
        "medgemma-27b", "med42-8b",
    ]
    print(f"\n{'='*80}")
    print(" Policy gain (policy_hit - strict_hit) at R@1 and MRR")
    print(f"{'='*80}")
    header = f"{'Model':<20} {'Dataset':<12} {'ΔR@1':>8} {'ΔMRR':>8} {'ΔR@10':>8}"
    print(header)
    print("-" * 60)
    for ds in datasets:
        for model in models:
            key = (model, ds)
            if key not in results:
                continue
            s = results[key]
            dr1  = s.get("policy_hit@1", 0) - s.get("strict_hit@1", 0)
            dmrr = s.get("policy_mrr", 0)   - s.get("strict_mrr", 0)
            dr10 = s.get("policy_hit@10", 0) - s.get("strict_hit@10", 0)
            if dr1 > 0.001 or dmrr > 0.001:
                print(f"{model:<20} {ds:<12} {dr1:>+8.3f} {dmrr:>+8.3f} {dr10:>+8.3f}")


# ---------------------------------------------------------------------------
# Markdown report
# ---------------------------------------------------------------------------

def write_markdown(results: Dict[Tuple[str, str], Dict], out_path: Path) -> None:
    datasets = ["phenopacket", "HMS", "LIRICAL", "MME", "RAMEDIS"]
    models = [
        "llama70b-legacy", "llama-3.3-70b", "med42-70b",
        "gemma-4-31b", "gemma-3-27b", "qwen2.5-32b",
        "medgemma-27b", "med42-8b",
    ]

    lines = [
        "# Policy-Adjusted dx_bench Evaluation",
        "",
        "Applies the 3-tier benchmark policy (strict_merge / family_partial_credit / do_not_merge)",
        "from `clinically_similar_disease_analysis_20260409` to all completed dx_bench runs.",
        "",
        "**Strict**: exact OMIM ID match only (same as existing metrics.json).",
        "**Policy hit**: same-family predictions count as hits for `strict_merge` families",
        "and `family_partial_credit` families (any partial credit > 0).",
        "**Policy score@k**: average of the maximum policy score earned in top-k",
        "(1.0 = exact or strict_merge; partial_credit_weight for partial families; 0.0 otherwise).",
        "",
        "Note: gemma-3-27b phenopacket excluded (no results.jsonl). "
        "llama-3.3-70b phenopacket excluded (run in progress).",
        "",
    ]

    for ds in datasets:
        lines += [
            f"## {ds}",
            "",
            "| Model | N | Strict R@1 | Strict R@5 | Strict R@10 | Strict MRR | Policy R@1 | Policy R@5 | Policy R@10 | Policy MRR | ΔR@1 | ΔMRR |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
        for model in models:
            key = (model, ds)
            if key not in results:
                continue
            s = results[key]
            n    = s.get("n", 0)
            sr1  = s.get("strict_hit@1", 0)
            sr5  = s.get("strict_hit@5", 0)
            sr10 = s.get("strict_hit@10", 0)
            smrr = s.get("strict_mrr", 0)
            pr1  = s.get("policy_hit@1", 0)
            pr5  = s.get("policy_hit@5", 0)
            pr10 = s.get("policy_hit@10", 0)
            pmrr = s.get("policy_mrr", 0)
            dr1  = pr1 - sr1
            dmrr = pmrr - smrr
            lines.append(
                f"| {model} | {n} "
                f"| {sr1:.3f} | {sr5:.3f} | {sr10:.3f} | {smrr:.3f} "
                f"| {pr1:.3f} | {pr5:.3f} | {pr10:.3f} | {pmrr:.3f} "
                f"| {dr1:+.3f} | {dmrr:+.3f} |"
            )
        lines.append("")

    out_path.write_text("\n".join(lines) + "\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("Loading policy index …")
    omim_policy, omim_to_family, family_policy = load_policy(POLICY_CSV, FAMILIES_CSV)
    print(f"  OMIM IDs with policy: {len(omim_policy)}")
    print(f"  OMIM IDs mapped to families: {len(omim_to_family)}")

    policy_counts = {}
    for pol, _ in family_policy.values():
        policy_counts[pol] = policy_counts.get(pol, 0) + 1
    print(f"  Family policy breakdown: {policy_counts}")

    results: Dict[Tuple[str, str], Dict] = {}
    for model_label, dataset, jsonl_path in RUNS:
        if not jsonl_path.exists():
            print(f"  [SKIP] {model_label} / {dataset}: {jsonl_path.name} not found")
            continue
        print(f"  Evaluating {model_label} / {dataset} …", end=" ", flush=True)
        summary = evaluate_jsonl(jsonl_path, omim_policy, omim_to_family)
        results[(model_label, dataset)] = summary
        print(f"n={summary.get('n', '?')}  strict_R@1={summary.get('strict_hit@1', 0):.3f}  policy_R@1={summary.get('policy_hit@1', 0):.3f}")

    print_table(results)
    print_delta_table(results)

    # Save JSON
    json_out = {f"{m}|{d}": v for (m, d), v in results.items()}
    OUTPUT_JSON.write_text(json.dumps(json_out, indent=2))
    print(f"\nJSON saved → {OUTPUT_JSON}")

    write_markdown(results, OUTPUT_MD)
    print(f"Markdown saved → {OUTPUT_MD}")


if __name__ == "__main__":
    main()
