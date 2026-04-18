#!/usr/bin/env python3
"""Ablation study: isolate the contribution of z-score normalization vs. recall/precision signals.

Tests:
  A) Baseline: raw PhenoDP score, no modification
  B) Z-score only: z-score(PhenoDP_score) — no R/P, just normalization
  C) Z-score + Recall only: z(S) + 1.0*z(R)
  D) Z-score + Precision penalty only: z(S) - 0.5*z(P)
  E) Full: z(S) + 1.0*z(R) - 0.5*z(P)

All evaluated with PMID-grouped 5-fold CV (outer folds only, no weight tuning needed).
"""

import json, re, random, numpy as np, sys
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

print(f"Loaded {len(all_records)} cases", flush=True)


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


def eval_method(cases, score_fn, k_vals=(1, 3, 5, 10)):
    hits = {k: 0 for k in k_vals}
    for cs in cases:
        if not cs:
            continue
        scored = [(score_fn(cs, i), cs[i]) for i in range(len(cs))]
        scored.sort(key=lambda x: -x[0])
        for rank, (_, c) in enumerate(scored):
            if c["ok"]:
                for k in k_vals:
                    if rank < k:
                        hits[k] += 1
                break
    n = len(cases)
    return {k: hits[k] / n * 100 for k in k_vals}


# ── Define ablation methods ──────────────────────────────────────────
def baseline(c, i):
    """A) Raw PhenoDP score"""
    return c[i]["s"]

def zscore_only(c, i):
    """B) Z-score normalization of PhenoDP score only"""
    return zs([x["s"] for x in c])[i]

def zscore_plus_recall(c, i):
    """C) Z-score score + recall"""
    return zs([x["s"] for x in c])[i] + 1.0 * zs([x["r"] for x in c])[i]

def zscore_minus_precision(c, i):
    """D) Z-score score - precision penalty"""
    return zs([x["s"] for x in c])[i] - 0.5 * zs([x["p"] for x in c])[i]

def zscore_full(c, i):
    """E) Full: z(S) + 1.0*z(R) - 0.5*z(P)"""
    return (zs([x["s"] for x in c])[i]
            + 1.0 * zs([x["r"] for x in c])[i]
            - 0.5 * zs([x["p"] for x in c])[i])


methods = [
    ("A) Baseline (raw score)", baseline),
    ("B) Z-score(S) only", zscore_only),
    ("C) Z(S) + 1.0*Z(R)", zscore_plus_recall),
    ("D) Z(S) - 0.5*Z(P)", zscore_minus_precision),
    ("E) Z(S) + 1.0*Z(R) - 0.5*Z(P)  [full]", zscore_full),
]

# ── Run PMID-grouped 5-fold CV ───────────────────────────────────────
folds = build_pmid_folds(all_records, k=5, seed=42)
print(f"Fold sizes: {[len(f) for f in folds]}\n", flush=True)

print(f"{'Method':<45} {'H@1':>7} {'H@3':>7} {'H@5':>7} {'H@10':>7}")
print("=" * 80)

from scipy import stats as scipy_stats

for name, fn in methods:
    fold_h1 = []
    fold_h3 = []
    fold_h5 = []
    fold_h10 = []
    for fi in range(5):
        test_cases = [all_records[j]["cands"] for j in folds[fi]]
        result = eval_method(test_cases, fn)
        fold_h1.append(result[1])
        fold_h3.append(result[3])
        fold_h5.append(result[5])
        fold_h10.append(result[10])

    mean_h1 = np.mean(fold_h1)
    mean_h3 = np.mean(fold_h3)
    mean_h5 = np.mean(fold_h5)
    mean_h10 = np.mean(fold_h10)
    print(f"{name:<45} {mean_h1:>6.2f}% {mean_h3:>6.2f}% {mean_h5:>6.2f}% {mean_h10:>6.2f}%")

    # Store baseline for comparison
    if "Baseline" in name:
        baseline_h1 = fold_h1

# Print deltas vs baseline
print("\n" + "=" * 80)
print("Deltas vs baseline (H@1) with paired t-test:\n")

for name, fn in methods:
    if "Baseline" in name:
        continue
    fold_h1 = []
    for fi in range(5):
        test_cases = [all_records[j]["cands"] for j in folds[fi]]
        result = eval_method(test_cases, fn)
        fold_h1.append(result[1])
    delta = np.mean(fold_h1) - np.mean(baseline_h1)
    t_stat, p_val = scipy_stats.ttest_rel(fold_h1, baseline_h1)
    sig = "***" if p_val < 0.001 else "**" if p_val < 0.01 else "*" if p_val < 0.05 else "ns"
    print(f"  {name:<45} Δ={delta:+.2f}%  p={p_val:.4f} {sig}")

print("\nDone.", flush=True)
