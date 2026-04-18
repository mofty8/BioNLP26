#!/usr/bin/env python3
"""Pool size ablation: test different pool sizes for z-score PR rescoring.

For each pool size K:
  1. PhenoDP retrieves top-K candidates (from the existing top-50 or top-200)
  2. Z-score rescore within those K candidates
  3. Take top-50 (or all K if K < 50)
  4. Evaluate Hit@1, @3, @5, @10

Tests both:
  - Rescoring within different subsets of the existing top-50
  - Using the full 200-pool run for K > 50
"""

import json, numpy as np, sys, re, random
from collections import defaultdict

sys.path.insert(0, ".")
from phenodp_gemma3_pipeline.hpo_annotations import HPOAnnotationStore

# ── Load data ─────────────────────────────────────────────────────────
print("Loading HPO annotations...", flush=True)
ann_store = HPOAnnotationStore.from_hpoa_file(
    "/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/PehnoPacketPhenoDP/PhenoDP/data/hpo_latest/phenotype.hpoa"
)
disease_hpos = {}
for did, anns in ann_store._annotations.items():
    disease_hpos[did.upper()] = set(a.hpo_id for a in anns)


def zs(v):
    a = np.array(v, dtype=float)
    m, s = a.mean(), a.std()
    return (a - m) / s if s > 1e-9 else np.zeros_like(a)


def load_candidates(path):
    records = []
    with open(path) as f:
        for line in f:
            rec = json.loads(line)
            records.append(rec)
    return records


def build_pmid_folds(records, k=5, seed=42):
    rng = random.Random(seed)
    pmid_to_indices = defaultdict(list)
    for i, rec in enumerate(records):
        pid = rec.get("patient_id", "")
        m = re.match(r"(PMID_\d+)", pid)
        pmid = m.group(1) if m else pid
        pmid_to_indices[pmid].append(i)
    pmids = sorted(pmid_to_indices.keys())
    rng.shuffle(pmids)
    folds = [[] for _ in range(k)]
    for i, pmid in enumerate(pmids):
        folds[i % k].extend(pmid_to_indices[pmid])
    return folds


def evaluate_pool_size(records, pool_size, rescore=True):
    """Evaluate rescoring within top-pool_size candidates."""
    h1 = h3 = h5 = h10 = found = total = 0
    for rec in records:
        total += 1
        truth = set(t.upper() for t in rec["truth_ids"])
        pos_ids = set(rec["phenotype_ids"])
        cands = rec["candidates"][:pool_size]  # take top-K from PhenoDP ranking

        if not cands:
            continue

        if rescore:
            scores, recalls, precs = [], [], []
            for c in cands:
                dh = disease_hpos.get(c["disease_id"].upper(), set())
                ov = len(pos_ids & dh)
                scores.append(c["score"] if "raw_total_similarity" not in c.get("metadata", {})
                              else c["metadata"]["raw_total_similarity"])
                recalls.append(ov / len(pos_ids) if pos_ids else 0)
                precs.append(ov / len(dh) if dh else 0)

            zs_s = zs(scores)
            zs_r = zs(recalls)
            zs_p = zs(precs)
            adjusted = zs_s + 1.0 * zs_r - 0.5 * zs_p
            ranked = sorted(zip(adjusted, range(len(cands))), reverse=True)
        else:
            ranked = [(0, i) for i in range(len(cands))]

        for rank, (_, idx) in enumerate(ranked):
            if cands[idx]["disease_id"].upper() in truth:
                if rank < 1: h1 += 1
                if rank < 3: h3 += 1
                if rank < 5: h5 += 1
                if rank < 10: h10 += 1
                found += 1
                break

    n = total
    return {
        "h1": h1 / n * 100, "h3": h3 / n * 100,
        "h5": h5 / n * 100, "h10": h10 / n * 100,
        "found": found / n * 100, "n": n
    }


# ── Load both candidate sets ─────────────────────────────────────────
print("Loading top-50 candidates (baseline run)...", flush=True)
top50_path = "runs/phenodp_gemma3_6901_no_genes_twostage_20260319_054012_20260319_044040/candidate_sets/phenodp_candidates_top50.jsonl"
records_50 = load_candidates(top50_path)

print("Loading top-200 candidates (z-score run)...", flush=True)
top200_path = "runs/phenodp_gemma3_zscore_pr_rescoring_20260324_042728/candidate_sets/phenodp_candidates_top50.jsonl"
records_200_raw = load_candidates(top200_path)

# Match the 6901 cases
pids_50 = {r["patient_id"] for r in records_50}
records_200 = [r for r in records_200_raw if r["patient_id"] in pids_50]
print(f"Matched {len(records_200)} cases from 200-pool run", flush=True)

# ── Part 1: Vary pool size within existing top-50 ────────────────────
print(f"\n{'='*100}")
print("PART 1: Rescore within top-K of PhenoDP's original top-50 ranking")
print(f"{'='*100}\n")

pool_sizes = [10, 15, 20, 25, 30, 35, 40, 45, 50]
print(f"{'Pool K':<10} {'H@1':>8} {'H@3':>8} {'H@5':>8} {'H@10':>8} {'Found':>8}")
print("-" * 60)

# Baseline (no rescoring)
bl = evaluate_pool_size(records_50, 50, rescore=False)
print(f"{'BL (50)' :<10} {bl['h1']:>7.2f}% {bl['h3']:>7.2f}% {bl['h5']:>7.2f}% {bl['h10']:>7.2f}% {bl['found']:>7.2f}%")
print("-" * 60)

for K in pool_sizes:
    r = evaluate_pool_size(records_50, K, rescore=True)
    delta = r["h1"] - bl["h1"]
    print(f"{'K=' + str(K):<10} {r['h1']:>7.2f}% {r['h3']:>7.2f}% {r['h5']:>7.2f}% {r['h10']:>7.2f}% {r['found']:>7.2f}%  (Δ={delta:+.2f}%)")

# ── Part 2: Use the 200-pool run for larger K values ─────────────────
# The 200-pool run has candidates retrieved with pool_size=200
# We need the raw PhenoDP scores (before z-score) to simulate different pool sizes
# The metadata has raw_total_similarity

print(f"\n{'='*100}")
print("PART 2: Rescore within top-K of PhenoDP's 200-pool (candidates re-sorted by raw score)")
print(f"{'='*100}\n")

# Re-sort candidates by raw PhenoDP score first
for rec in records_200:
    rec["candidates"].sort(
        key=lambda c: c.get("metadata", {}).get("raw_total_similarity", c["score"]),
        reverse=True
    )

pool_sizes_large = [50, 75, 100, 125, 150, 175, 200]
print(f"{'Pool K':<10} {'H@1':>8} {'H@3':>8} {'H@5':>8} {'H@10':>8} {'Found':>8}")
print("-" * 60)

# Baseline on 200-pool (no rescoring, just raw PhenoDP top-50)
bl2 = evaluate_pool_size(records_200, 50, rescore=False)
print(f"{'BL (50)' :<10} {bl2['h1']:>7.2f}% {bl2['h3']:>7.2f}% {bl2['h5']:>7.2f}% {bl2['h10']:>7.2f}% {bl2['found']:>7.2f}%")
print("-" * 60)

for K in pool_sizes_large:
    r = evaluate_pool_size(records_200, K, rescore=True)
    delta = r["h1"] - bl2["h1"]
    print(f"{'K=' + str(K):<10} {r['h1']:>7.2f}% {r['h3']:>7.2f}% {r['h5']:>7.2f}% {r['h10']:>7.2f}% {r['found']:>7.2f}%  (Δ={delta:+.2f}%)")


# ── Part 3: PMID-grouped CV on the best pool sizes ──────────────────
print(f"\n{'='*100}")
print("PART 3: PMID-grouped 5-fold CV for key pool sizes")
print(f"{'='*100}\n")

from scipy import stats as scipy_stats

folds = build_pmid_folds(records_50, k=5, seed=42)

key_sizes = [20, 30, 40, 50]
print(f"{'Pool K':<10} {'Mean H@1':>10} {'Std':>7} {'Δ vs BL':>9} {'p-value':>10} {'Sig':>5}")
print("-" * 60)

# Baseline CV
bl_fold_h1 = []
for fi in range(5):
    fold_recs = [records_50[j] for j in folds[fi]]
    r = evaluate_pool_size(fold_recs, 50, rescore=False)
    bl_fold_h1.append(r["h1"])
print(f"{'BL (50)':<10} {np.mean(bl_fold_h1):>9.2f}% {np.std(bl_fold_h1):>6.2f}%")
print("-" * 60)

for K in key_sizes:
    fold_h1 = []
    for fi in range(5):
        fold_recs = [records_50[j] for j in folds[fi]]
        r = evaluate_pool_size(fold_recs, K, rescore=True)
        fold_h1.append(r["h1"])
    mean_h1 = np.mean(fold_h1)
    std_h1 = np.std(fold_h1)
    delta = mean_h1 - np.mean(bl_fold_h1)
    t_stat, p_val = scipy_stats.ttest_rel(fold_h1, bl_fold_h1)
    sig = "***" if p_val < 0.001 else "**" if p_val < 0.01 else "*" if p_val < 0.05 else "ns"
    print(f"{'K=' + str(K):<10} {mean_h1:>9.2f}% {std_h1:>6.2f}% {delta:>+8.2f}% {p_val:>10.4f} {sig:>5}")

print("\nDone.", flush=True)
