#!/usr/bin/env python3
"""Inspect promotions/demotions of MedLlama70B pp2prompt_v2 vs retriever and v7."""
from __future__ import annotations
import json, csv
from collections import Counter, defaultdict
from pathlib import Path

RUNS = Path("/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/phenodp_gemma3_candidate_ranking/runs")

CANDS = RUNS / "phenodp_gemma3_v7_full_rerank_20260407_192822/candidate_sets/phenodp_candidates_top50.jsonl"
V7_CSV  = RUNS / "phenodp_medllama70b_v7_full_rerank_20260405_104044/methods/reranker_medllama70b_top10/results.csv"
PP2_CSV = RUNS / "phenodp_medllama70b_pp2prompt_v2_full_rerank_20260408_180417/methods/reranker_medllama70b_top10/results.csv"

# ── 1. Load retriever top-10 and compute ret_hit1 ──────────────────────────
ret = {}
for line in open(CANDS):
    rec = json.loads(line)
    pid = rec["patient_id"]
    truth = set(rec["truth_ids"])
    cands = rec["candidates"][:10]
    ids = []
    for c in cands:
        if isinstance(c, dict):
            ids.append(c.get("disease_id", ""))
        else:
            ids.append(str(c))
    ret_rank = next((i + 1 for i, cid in enumerate(ids) if cid in truth), 0)
    ret[pid] = {
        "truth": truth,
        "top10_ids": ids,
        "ret_rank": ret_rank,
        "ret_hit1": int(ret_rank == 1),
    }

# ── 2. Load CSV results ────────────────────────────────────────────────────
def load_csv(path):
    out = {}
    with open(path) as f:
        for row in csv.DictReader(f):
            pid = row["patient_id"]
            out[pid] = {
                "hit1":  float(row.get("id_correct_hit_1", 0) or 0),
                "hit3":  float(row.get("id_correct_hit_3", 0) or 0),
                "hit10": float(row.get("id_correct_hit_10", 0) or 0),
                "pred1": row.get("pred1_id", ""),
                "pred1_name": row.get("pred1_name", ""),
                "ranked_ids": row.get("ranked_ids", "").split("|"),
            }
    return out

v7  = load_csv(V7_CSV)
pp2 = load_csv(PP2_CSV)

# ── 3. Restrict to fair set: truth in top-10 retriever ────────────────────
common = set(ret) & set(v7) & set(pp2)
fair = {pid for pid in common if ret[pid]["ret_rank"] > 0}
print(f"Total common cases: {len(common)}")
print(f"Fair set (truth in ret top-10): {len(fair)}\n")

# ── 4. Categorise ──────────────────────────────────────────────────────────
ret_hit1_only   = []   # ret=1, v7=0, pp2=0
v7_demotes      = []   # ret=1, v7=0
pp2_demotes     = []   # ret=1, pp2=0
v7_promotes     = []   # ret!=1, v7=1
pp2_promotes    = []   # ret!=1, pp2=1

for pid in fair:
    rh = ret[pid]["ret_hit1"]
    vh = int(v7[pid]["hit1"])
    ph = int(pp2[pid]["hit1"])

    if rh == 1 and vh == 0:
        v7_demotes.append(pid)
    if rh == 1 and ph == 0:
        pp2_demotes.append(pid)
    if rh == 0 and vh == 1:
        v7_promotes.append(pid)
    if rh == 0 and ph == 1:
        pp2_promotes.append(pid)

pp2_only_demotes  = set(pp2_demotes) - set(v7_demotes)
v7_only_demotes   = set(v7_demotes)  - set(pp2_demotes)
both_demote       = set(pp2_demotes) & set(v7_demotes)
pp2_only_promotes = set(pp2_promotes) - set(v7_promotes)
v7_only_promotes  = set(v7_promotes)  - set(pp2_promotes)
both_promote      = set(pp2_promotes) & set(v7_promotes)

print("=== Demotions (ret hit@1=1, model hit@1=0) ===")
print(f"  v7  demotions : {len(v7_demotes)}")
print(f"  pp2 demotions : {len(pp2_demotes)}")
print(f"    pp2-only    : {len(pp2_only_demotes)}")
print(f"    v7-only     : {len(v7_only_demotes)}")
print(f"    both        : {len(both_demote)}")

print("\n=== Promotions (ret hit@1=0, model hit@1=1) ===")
print(f"  v7  promotions : {len(v7_promotes)}")
print(f"  pp2 promotions : {len(pp2_promotes)}")
print(f"    pp2-only     : {len(pp2_only_promotes)}")
print(f"    v7-only      : {len(v7_only_promotes)}")
print(f"    both         : {len(both_promote)}")

# ── 5. What does pp2 switch TO when it demotes (pp2-only)? ────────────────
switch_to_name = Counter()
truth_demoted  = Counter()   # which truth disease families get demoted most

for pid in pp2_only_demotes:
    pred1_name = pp2[pid]["pred1_name"]
    switch_to_name[pred1_name] += 1
    # truth label
    for tid in ret[pid]["truth"]:
        truth_demoted[tid] += 1

print("\n=== Top-20 diseases pp2 incorrectly promotes to (pp2-only demotions) ===")
for name, cnt in switch_to_name.most_common(20):
    print(f"  {cnt:4d}  {name}")

print("\n=== Top-20 truth diseases most demoted by pp2 (pp2-only) ===")
for tid, cnt in truth_demoted.most_common(20):
    print(f"  {cnt:4d}  {tid}")

# ── 6. Sample pp2-only demotions ──────────────────────────────────────────
print("\n=== Sample pp2-only demotions (ret✓, v7✓, pp2✗) ===")
sample_demote = sorted(pp2_only_demotes - set(v7_demotes))[:15]
for pid in sample_demote:
    truth_ids = list(ret[pid]["truth"])
    r_top3 = ret[pid]["top10_ids"][:3]
    v7_top3 = v7[pid]["ranked_ids"][:3]
    p2_top3 = pp2[pid]["ranked_ids"][:3]
    print(f"\n  {pid}")
    print(f"    truth  : {truth_ids}")
    print(f"    ret top3: {r_top3}")
    print(f"    v7  top3: {v7_top3}")
    print(f"    pp2 top3: {p2_top3}")
    print(f"    pp2 pred1: {pp2[pid]['pred1_name']}")

# ── 7. Sample pp2-only promotions ─────────────────────────────────────────
print("\n=== Sample pp2-only promotions (ret✗, v7✗, pp2✓) ===")
sample_promo = sorted(pp2_only_promotes)[:10]
for pid in sample_promo:
    truth_ids = list(ret[pid]["truth"])
    r_top3 = ret[pid]["top10_ids"][:3]
    v7_top3 = v7[pid]["ranked_ids"][:3]
    p2_top3 = pp2[pid]["ranked_ids"][:3]
    print(f"\n  {pid}")
    print(f"    truth  : {truth_ids}")
    print(f"    ret top3: {r_top3}")
    print(f"    v7  top3: {v7_top3}")
    print(f"    pp2 top3: {p2_top3}")

# ── 8. Net gain ───────────────────────────────────────────────────────────
print(f"\n=== Net change (pp2 vs retriever) on fair set ===")
ret_h1  = sum(ret[p]["ret_hit1"] for p in fair)
pp2_h1  = sum(int(pp2[p]["hit1"]) for p in fair)
v7_h1   = sum(int(v7[p]["hit1"])  for p in fair)
print(f"  Retriever hit@1 : {ret_h1}/{len(fair)} = {ret_h1/len(fair):.4f}")
print(f"  MedLlama v7  h@1: {v7_h1}/{len(fair)}  = {v7_h1/len(fair):.4f}")
print(f"  MedLlama pp2 h@1: {pp2_h1}/{len(fair)} = {pp2_h1/len(fair):.4f}")
print(f"  pp2 net vs ret  : {pp2_h1 - ret_h1:+d}")
print(f"  pp2 net vs v7   : {pp2_h1 - v7_h1:+d}")
