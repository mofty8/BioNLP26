#!/usr/bin/env python3
"""PMID-grouped 5-fold CV for z-score normalized PR rescoring."""

import json, re, random, numpy as np, sys
from collections import defaultdict
from scipy import stats as scipy_stats

sys.path.insert(0, ".")
from phenodp_gemma3_pipeline.hpo_annotations import HPOAnnotationStore

# ── Load HPO annotations ─────────────────────────────────────────────
ann_store = HPOAnnotationStore.from_hpoa_file(
    "/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/PehnoPacketPhenoDP/PhenoDP/data/hpo_latest/phenotype.hpoa"
)
disease_hpos = {}
for did, anns in ann_store._annotations.items():
    disease_hpos[did.upper()] = set(a.hpo_id for a in anns)

# ── Load candidate data ──────────────────────────────────────────────
path = "runs/phenodp_gemma3_6901_no_genes_twostage_20260319_054012_20260319_044040/candidate_sets/phenodp_candidates_top50.jsonl"
all_records = []
with open(path) as f:
    for line in f:
        rec = json.loads(line)
        pid = rec.get("patient_id", "")
        truth_ids = set(t.upper() for t in rec.get("truth_ids", []))
        pos_ids = set(rec.get("phenotype_ids", []))
        # Extract PMID
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

print(f"Loaded {len(all_records)} cases from {len(set(r['pmid'] for r in all_records))} PMIDs", flush=True)


# ── PMID-grouped fold builder ────────────────────────────────────────
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


# ── Scoring helpers ───────────────────────────────────────────────────
def zs(v):
    a = np.array(v, dtype=float)
    m, s = a.mean(), a.std()
    return (a - m) / s if s > 1e-9 else np.zeros_like(a)


def hit_at_k(cases, score_fn, k_vals=(1, 3, 5, 10)):
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


# ── Build folds ──────────────────────────────────────────────────────
folds = build_pmid_folds(all_records, k=5, seed=42)
print(f"Fold sizes: {[len(f) for f in folds]}", flush=True)

# Check PMID leakage
for fi in range(5):
    test_pmids = set(all_records[j]["pmid"] for j in folds[fi])
    train_pmids = set()
    for fj in range(5):
        if fj != fi:
            train_pmids.update(all_records[j]["pmid"] for j in folds[fj])
    overlap = test_pmids & train_pmids
    if overlap:
        print(f"WARNING: PMID leakage in fold {fi}: {len(overlap)} PMIDs", flush=True)
print("No PMID leakage detected.", flush=True)

# ── Configs to test ──────────────────────────────────────────────────
configs = [
    ("Baseline (score only)", lambda c, i: c[i]["s"], False),
    ("Raw: S + 0.30*R - 0.15*P", lambda c, i: c[i]["s"] + 0.30 * c[i]["r"] - 0.15 * c[i]["p"], False),
]

zscore_configs = [
    (1, 1, 0.5),
    (0.5, 0.5, 0.25),
    (1, 0.5, 0.25),
    (1, 0.7, 0.3),
    (1, 0.3, 0.15),
    (0.7, 0.3, 0),
    (1, 0.5, 0),
]

for ws, wr, wp in zscore_configs:
    def make_fn(ws=ws, wr=wr, wp=wp):
        def fn(c, i):
            return (ws * zs([x["s"] for x in c])[i]
                    + wr * zs([x["r"] for x in c])[i]
                    - wp * zs([x["p"] for x in c])[i])
        return fn
    configs.append((f"z: {ws}*S + {wr}*R - {wp}*P", make_fn(), True))

# ── Run 5-fold CV ────────────────────────────────────────────────────
print(f"\n{'Method':<45} | {'Mean H@1':>8} | {'Std':>6} | {'Fold H@1s':>40} | {'p-val':>8}")
print("-" * 120)

baseline_fold_h1 = None

for label, score_fn, is_zscore in configs:
    fold_h1 = []
    fold_h3 = []
    for fi in range(5):
        test_indices = folds[fi]
        test_cases = [all_records[j]["cands"] for j in test_indices]
        result = hit_at_k(test_cases, score_fn)
        fold_h1.append(result[1])
        fold_h3.append(result[3])

    mean_h1 = np.mean(fold_h1)
    std_h1 = np.std(fold_h1)
    fold_str = ", ".join(f"{h:.1f}" for h in fold_h1)

    if label == "Baseline (score only)":
        baseline_fold_h1 = fold_h1
        print(f"{label:<45} | {mean_h1:7.2f}% | {std_h1:5.2f} | [{fold_str:>40}] |      ---")
    else:
        # Paired t-test vs baseline
        if baseline_fold_h1 is not None:
            t_stat, p_val = scipy_stats.ttest_rel(fold_h1, baseline_fold_h1)
            sig = "***" if p_val < 0.001 else "**" if p_val < 0.01 else "*" if p_val < 0.05 else ""
            print(f"{label:<45} | {mean_h1:7.2f}% | {std_h1:5.2f} | [{fold_str:>40}] | {p_val:.4f} {sig}")
        else:
            print(f"{label:<45} | {mean_h1:7.2f}% | {std_h1:5.2f} | [{fold_str:>40}] |      ---")

# ── Detailed per-fold comparison for top configs ─────────────────────
print("\n=== Detailed comparison: Baseline vs Best Z-score (1*S + 1*R - 0.5*P) ===")
print(f"{'Fold':<6} | {'Baseline H@1':>12} | {'Z-score H@1':>12} | {'Delta':>8} | {'Baseline H@3':>12} | {'Z-score H@3':>12}")
print("-" * 80)

baseline_fn = lambda c, i: c[i]["s"]
best_z_fn = lambda c, i: (1.0 * zs([x["s"] for x in c])[i]
                           + 1.0 * zs([x["r"] for x in c])[i]
                           - 0.5 * zs([x["p"] for x in c])[i])

for fi in range(5):
    test_cases = [all_records[j]["cands"] for j in folds[fi]]
    bl = hit_at_k(test_cases, baseline_fn)
    zr = hit_at_k(test_cases, best_z_fn)
    delta = zr[1] - bl[1]
    print(f"  {fi:<4} | {bl[1]:11.2f}% | {zr[1]:11.2f}% | {delta:+7.2f}% | {bl[3]:11.2f}% | {zr[3]:11.2f}%")

print("\nDone.", flush=True)
