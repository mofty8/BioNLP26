#!/usr/bin/env python3
"""Nested PMID-grouped 5-fold CV for z-score PR rescoring.

Outer loop: 5 folds for unbiased evaluation.
Inner loop: For each outer fold, use the 4 training folds to select best weights.
Report: Only the held-out outer fold performance (never seen during weight selection).
"""

import json, re, random, numpy as np, sys
from collections import defaultdict
from itertools import product

sys.path.insert(0, ".")
from phenodp_gemma3_pipeline.hpo_annotations import HPOAnnotationStore

# ── Load HPO annotations ─────────────────────────────────────────────
print("Loading HPO annotations...", flush=True)
ann_store = HPOAnnotationStore.from_hpoa_file(
    "/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/PehnoPacketPhenoDP/PhenoDP/data/hpo_latest/phenotype.hpoa"
)
disease_hpos = {}
for did, anns in ann_store._annotations.items():
    disease_hpos[did.upper()] = set(a.hpo_id for a in anns)

# ── Load candidate data ──────────────────────────────────────────────
print("Loading candidates...", flush=True)
path = "runs/phenodp_gemma3_6901_no_genes_twostage_20260319_054012_20260319_044040/candidate_sets/phenodp_candidates_top50.jsonl"
all_records = []
with open(path) as f:
    for line in f:
        rec = json.loads(line)
        pid = rec.get("patient_id", "")
        truth_ids = set(t.upper() for t in rec.get("truth_ids", []))
        pos_ids = set(rec.get("phenotype_ids", []))
        m = re.match(r"(PMID_\d+)", pid)
        pmid = m.group(1) if m else pid
        cands = []
        for c in rec.get("candidates", []):
            cid = c.get("disease_id", "").upper()
            dh = disease_hpos.get(cid, set())
            ov = len(pos_ids & dh)
            r = ov / len(pos_ids) if pos_ids else 0
            p = ov / len(dh) if dh else 0
            cands.append({"s": c["score"], "r": r, "p": p, "ok": cid in truth_ids})
        all_records.append({"pmid": pmid, "cands": cands})

print(f"Loaded {len(all_records)} cases, {len(set(r['pmid'] for r in all_records))} PMIDs", flush=True)


# ── Helpers ───────────────────────────────────────────────────────────
def zs(v):
    a = np.array(v, dtype=float)
    m, s = a.mean(), a.std()
    return (a - m) / s if s > 1e-9 else np.zeros_like(a)


def build_pmid_folds(records, k=5, seed=42):
    rng = random.Random(seed)
    pmid_to_indices = defaultdict(list)
    for i, rec in enumerate(records):
        pmid_to_indices[rec["pmid"]].append(i)
    pmids = sorted(pmid_to_indices.keys())
    rng.shuffle(pmids)
    folds = [[] for _ in range(k)]
    for i, pmid in enumerate(pmids):
        folds[i % k].extend(pmid_to_indices[pmid])
    return folds


def hit_at_1(cases, score_fn):
    hits = 0
    for cs in cases:
        cs50 = cs[:50]
        if not cs50:
            continue
        scored = [(score_fn(cs50, i), cs50[i]) for i in range(len(cs50))]
        scored.sort(key=lambda x: -x[0])
        if scored[0][1]["ok"]:
            hits += 1
    return hits / len(cases) * 100 if cases else 0


def hit_at_k_full(cases, score_fn, k_vals=(1, 3, 5, 10)):
    hits = {k: 0 for k in k_vals}
    for cs in cases:
        cs50 = cs[:50]
        if not cs50:
            continue
        scored = [(score_fn(cs50, i), cs50[i]) for i in range(len(cs50))]
        scored.sort(key=lambda x: -x[0])
        for rank, (_, c) in enumerate(scored):
            if c["ok"]:
                for k in k_vals:
                    if rank < k:
                        hits[k] += 1
                break
    n = len(cases)
    return {k: hits[k] / n * 100 for k in k_vals}


def make_zscore_fn(ws, wr, wp):
    def fn(c, i):
        return (ws * zs([x["s"] for x in c])[i]
                + wr * zs([x["r"] for x in c])[i]
                - wp * zs([x["p"] for x in c])[i])
    return fn


# ── Weight search space ──────────────────────────────────────────────
weight_grid = [
    (1.0, 0.3, 0.0),
    (1.0, 0.3, 0.15),
    (1.0, 0.5, 0.0),
    (1.0, 0.5, 0.15),
    (1.0, 0.5, 0.25),
    (1.0, 0.7, 0.2),
    (1.0, 0.7, 0.3),
    (1.0, 1.0, 0.3),
    (1.0, 1.0, 0.5),
    (0.7, 0.3, 0.0),
    (0.5, 0.5, 0.0),
    (0.5, 0.5, 0.25),
]

# ── Build outer folds ────────────────────────────────────────────────
K_OUTER = 5
outer_folds = build_pmid_folds(all_records, k=K_OUTER, seed=42)
print(f"Outer fold sizes: {[len(f) for f in outer_folds]}", flush=True)

# ── Nested CV ─────────────────────────────────────────────────────────
print(f"\n{'='*100}")
print("NESTED 5-FOLD CV: Inner loop selects weights, outer fold evaluates")
print(f"{'='*100}\n")

baseline_fn = lambda c, i: c[i]["s"]
outer_baseline_h1 = []
outer_best_h1 = []
outer_best_h3 = []
outer_best_h5 = []
outer_best_h10 = []
outer_selected_weights = []

for outer_fi in range(K_OUTER):
    test_indices = outer_folds[outer_fi]
    train_indices = []
    for fj in range(K_OUTER):
        if fj != outer_fi:
            train_indices.extend(outer_folds[fj])

    test_cases = [all_records[j]["cands"] for j in test_indices]
    train_cases = [all_records[j]["cands"] for j in train_indices]

    # ── Inner loop: find best weights on training data ────────────
    # Split training data into inner folds for validation
    # Use simple random split (not PMID-grouped for inner, to keep it simple
    # and because we're just picking weights, not fitting a model)
    train_records_inner = [all_records[j] for j in train_indices]
    inner_folds = build_pmid_folds(train_records_inner, k=4, seed=outer_fi * 100 + 7)

    best_inner_score = -1
    best_weights = (1.0, 1.0, 0.5)  # fallback

    for ws, wr, wp in weight_grid:
        fn = make_zscore_fn(ws, wr, wp)
        inner_scores = []
        for inner_fi in range(4):
            val_cases = [train_records_inner[j]["cands"] for j in inner_folds[inner_fi]]
            inner_scores.append(hit_at_1(val_cases, fn))
        mean_inner = np.mean(inner_scores)
        if mean_inner > best_inner_score:
            best_inner_score = mean_inner
            best_weights = (ws, wr, wp)

    # ── Evaluate on outer test fold with selected weights ─────────
    best_fn = make_zscore_fn(*best_weights)
    test_result = hit_at_k_full(test_cases, best_fn)
    baseline_result = hit_at_k_full(test_cases, baseline_fn)

    outer_baseline_h1.append(baseline_result[1])
    outer_best_h1.append(test_result[1])
    outer_best_h3.append(test_result[3])
    outer_best_h5.append(test_result[5])
    outer_best_h10.append(test_result[10])
    outer_selected_weights.append(best_weights)

    print(f"Outer fold {outer_fi}: selected weights = {best_weights} "
          f"(inner val H@1={best_inner_score:.2f}%)")
    print(f"  Baseline  H@1={baseline_result[1]:.2f}%  H@3={baseline_result[3]:.2f}%  "
          f"H@5={baseline_result[5]:.2f}%  H@10={baseline_result[10]:.2f}%")
    print(f"  Z-score   H@1={test_result[1]:.2f}%  H@3={test_result[3]:.2f}%  "
          f"H@5={test_result[5]:.2f}%  H@10={test_result[10]:.2f}%")
    print(f"  Delta     H@1={test_result[1] - baseline_result[1]:+.2f}%")
    print(flush=True)

# ── Summary ───────────────────────────────────────────────────────────
print(f"{'='*100}")
print("NESTED CV SUMMARY (unbiased estimates)")
print(f"{'='*100}")
print(f"Selected weights per fold: {outer_selected_weights}")
print()
print(f"  Baseline  mean H@1 = {np.mean(outer_baseline_h1):.2f}% (std={np.std(outer_baseline_h1):.2f})")
print(f"  Z-score   mean H@1 = {np.mean(outer_best_h1):.2f}% (std={np.std(outer_best_h1):.2f})")
print(f"  Z-score   mean H@3 = {np.mean(outer_best_h3):.2f}% (std={np.std(outer_best_h3):.2f})")
print(f"  Z-score   mean H@5 = {np.mean(outer_best_h5):.2f}% (std={np.std(outer_best_h5):.2f})")
print(f"  Z-score   mean H@10= {np.mean(outer_best_h10):.2f}% (std={np.std(outer_best_h10):.2f})")
print(f"  Delta     mean H@1 = {np.mean(outer_best_h1) - np.mean(outer_baseline_h1):+.2f}%")
print()

# Paired t-test on outer folds
from scipy import stats as scipy_stats
t_stat, p_val = scipy_stats.ttest_rel(outer_best_h1, outer_baseline_h1)
print(f"  Paired t-test: t={t_stat:.3f}, p={p_val:.4f}", end="")
if p_val < 0.001:
    print(" ***")
elif p_val < 0.01:
    print(" **")
elif p_val < 0.05:
    print(" *")
else:
    print(" (not significant)")

print("\nDone.", flush=True)
