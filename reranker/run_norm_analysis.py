#!/usr/bin/env python3
import json, numpy as np, sys
sys.path.insert(0, ".")
from phenodp_gemma3_pipeline.hpo_annotations import HPOAnnotationStore

ann_store = HPOAnnotationStore.from_hpoa_file(
    "/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/PehnoPacketPhenoDP/PhenoDP/data/hpo_latest/phenotype.hpoa"
)
disease_hpos = {}
for did, anns in ann_store._annotations.items():
    disease_hpos[did.upper()] = set(a.hpo_id for a in anns)

all_cases = []
path = "runs/phenodp_gemma3_6901_no_genes_twostage_20260319_054012_20260319_044040/candidate_sets/phenodp_candidates_top50.jsonl"
with open(path) as f:
    for line in f:
        rec = json.loads(line)
        truth_ids = set(t.upper() for t in rec.get("truth_ids", []))
        pos_ids = set(rec.get("phenotype_ids", []))
        cands = []
        for c in rec.get("candidates", []):
            cid = c.get("disease_id", "").upper()
            dh = disease_hpos.get(cid, set())
            ov = len(pos_ids & dh)
            r = ov / len(pos_ids) if pos_ids else 0
            p = ov / len(dh) if dh else 0
            cands.append({"s": c["score"], "r": r, "p": p, "ok": cid in truth_ids})
        all_cases.append(cands)

print(f"Loaded {len(all_cases)} cases", flush=True)


def zs(v):
    a = np.array(v, dtype=float)
    m, s = a.mean(), a.std()
    return (a - m) / s if s > 1e-9 else np.zeros_like(a)


def mm(v):
    a = np.array(v, dtype=float)
    lo, hi = a.min(), a.max()
    return (a - lo) / (hi - lo) if (hi - lo) > 1e-9 else np.zeros_like(a)


def ev(fn):
    h1 = h3 = h5 = h10 = 0
    for cs in all_cases:
        cs50 = cs[:50]
        if not cs50:
            continue
        sc = [(fn(cs50, i), cs50[i]) for i in range(len(cs50))]
        sc.sort(key=lambda x: -x[0])
        for i, (_, c) in enumerate(sc):
            if c["ok"]:
                if i == 0: h1 += 1
                if i < 3: h3 += 1
                if i < 5: h5 += 1
                if i < 10: h10 += 1
                break
    n = len(all_cases)
    return h1 / n * 100, h3 / n * 100, h5 / n * 100, h10 / n * 100


def fmt(label, result):
    print(f"{label:<55} | {result[0]:6.2f}% | {result[1]:6.2f}% | {result[2]:6.2f}% | {result[3]:6.2f}%", flush=True)


print(f"{'Method':<55} | Hit@1   | Hit@3   | Hit@5   | Hit@10")
print("-" * 100)
fmt("Baseline", ev(lambda c, i: c[i]["s"]))
fmt("Raw: S + 0.30*R - 0.15*P", ev(lambda c, i: c[i]["s"] + 0.30 * c[i]["r"] - 0.15 * c[i]["p"]))
print()

print("=== Z-score normalization ===")
configs = [(1,.3,0),(1,.3,.15),(1,.5,.15),(1,.5,.25),(1,.7,.2),(1,.7,.3),(1,1,.3),(1,1,.5),(.7,.3,0),(.5,.5,0),(.5,.5,.25)]
for ws, wr, wp in configs:
    def fn(c, i, _s=ws, _r=wr, _p=wp):
        return (_s * zs([x["s"] for x in c])[i]
                + _r * zs([x["r"] for x in c])[i]
                - _p * zs([x["p"] for x in c])[i])
    fmt(f"z: {ws}*S + {wr}*R - {wp}*P", ev(fn))

print()
print("=== Min-max normalization ===")
for ws, wr, wp in configs:
    def fn(c, i, _s=ws, _r=wr, _p=wp):
        return (_s * mm([x["s"] for x in c])[i]
                + _r * mm([x["r"] for x in c])[i]
                - _p * mm([x["p"] for x in c])[i])
    fmt(f"mm: {ws}*S + {wr}*R - {wp}*P", ev(fn))

print()
print("=== Rank-based ===")
def rankify(values, higher_better=True):
    a = np.array(values, dtype=float)
    if higher_better:
        a = -a
    return (a.argsort().argsort() + 1).astype(float)

for ws, wr, wp in [(1,.3,0),(1,.3,.15),(1,.5,.15),(1,.7,.2),(1,1,.3),(.5,.5,0),(.5,.5,.25)]:
    def fn(c, i, _s=ws, _r=wr, _p=wp):
        rs = rankify([x["s"] for x in c])
        rr = rankify([x["r"] for x in c])
        rp = rankify([x["p"] for x in c], False)
        return -(_s * rs[i] + _r * rr[i] + _p * rp[i])
    fmt(f"rank: {ws}*S + {wr}*R + {wp}*P", ev(fn))

print("\nDone.", flush=True)
