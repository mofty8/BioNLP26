#!/usr/bin/env python3
"""Deep inspection of pp2-only promotions for MedLlama70B pp2prompt_v2."""
from __future__ import annotations
import json, csv
from collections import Counter, defaultdict
from pathlib import Path

RUNS = Path("/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/phenodp_gemma3_candidate_ranking/runs")

CANDS = RUNS / "phenodp_gemma3_v7_full_rerank_20260407_192822/candidate_sets/phenodp_candidates_top50.jsonl"
V7_CSV  = RUNS / "phenodp_medllama70b_v7_full_rerank_20260405_104044/methods/reranker_medllama70b_top10/results.csv"
PP2_CSV = RUNS / "phenodp_medllama70b_pp2prompt_v2_full_rerank_20260408_180417/methods/reranker_medllama70b_top10/results.csv"

# ── 1. Load retriever top-10 ───────────────────────────────────────────────
ret = {}
for line in open(CANDS):
    rec = json.loads(line)
    pid = rec["patient_id"]
    truth = set(rec["truth_ids"])
    cands = rec["candidates"][:10]
    ids = [c.get("disease_id", "") if isinstance(c, dict) else str(c) for c in cands]
    names = [c.get("disease_name", "") if isinstance(c, dict) else "" for c in cands]
    ret_rank = next((i + 1 for i, cid in enumerate(ids) if cid in truth), 0)
    # full top-50 for rank context
    all50 = rec["candidates"]
    all50_ids = [c.get("disease_id", "") if isinstance(c, dict) else str(c) for c in all50]
    ret50_rank = next((i + 1 for i, cid in enumerate(all50_ids) if cid in truth), 0)
    ret[pid] = {
        "truth": truth,
        "top10_ids": ids,
        "top10_names": names,
        "ret_rank": ret_rank,
        "ret50_rank": ret50_rank,
        "ret_hit1": int(ret_rank == 1),
    }

# ── 2. Load CSV results ────────────────────────────────────────────────────
def load_csv(path):
    out = {}
    with open(path) as f:
        for row in csv.DictReader(f):
            pid = row["patient_id"]
            ranked_ids = [x for x in row.get("ranked_ids", "").split("|") if x]
            ranked_names = [x for x in row.get("ranked_names", "").split("|") if x]
            out[pid] = {
                "hit1":  float(row.get("id_correct_hit_1", 0) or 0),
                "hit3":  float(row.get("id_correct_hit_3", 0) or 0),
                "hit10": float(row.get("id_correct_hit_10", 0) or 0),
                "pred1": row.get("pred1_id", ""),
                "pred1_name": row.get("pred1_name", ""),
                "ranked_ids": ranked_ids,
                "ranked_names": ranked_names,
                "truth_labels": row.get("truth_labels", ""),
            }
    return out

v7  = load_csv(V7_CSV)
pp2 = load_csv(PP2_CSV)

common = set(ret) & set(v7) & set(pp2)
fair = {pid for pid in common if ret[pid]["ret_rank"] > 0}

# ── 3. Identify pp2-only promotions ───────────────────────────────────────
# ret hit@1=0, v7 hit@1=0, pp2 hit@1=1
pp2_only_promotes = []
for pid in fair:
    if ret[pid]["ret_hit1"] == 0 and int(v7[pid]["hit1"]) == 0 and int(pp2[pid]["hit1"]) == 1:
        pp2_only_promotes.append(pid)

print(f"pp2-only promotions: {len(pp2_only_promotes)}\n")

# ── 4. What retriever rank was the truth at? (how hard were these cases) ──
ret_rank_dist = Counter(ret[pid]["ret_rank"] for pid in pp2_only_promotes)
print("=== Retriever rank of truth for pp2-only promotions ===")
for rank in sorted(ret_rank_dist):
    print(f"  ret rank {rank:2d}: {ret_rank_dist[rank]:3d} cases")

# ── 5. What disease families get promoted? ────────────────────────────────
truth_promoted = Counter()
truth_promoted_names = {}
for pid in pp2_only_promotes:
    for tid in ret[pid]["truth"]:
        truth_promoted[tid] += 1
        truth_promoted_names[tid] = pp2[pid]["truth_labels"]  # reuse csv label

print("\n=== Top-30 truth diseases that pp2 uniquely promotes (pp2-only) ===")
for tid, cnt in truth_promoted.most_common(30):
    name = truth_promoted_names.get(tid, "")
    print(f"  {cnt:3d}  {tid}  {name}")

# ── 6. What was the retriever's rank-1 for these cases? ───────────────────
ret_rank1_when_promoting = Counter()
for pid in pp2_only_promotes:
    ret_rank1_id = ret[pid]["top10_ids"][0] if ret[pid]["top10_ids"] else ""
    ret_rank1_name = ret[pid]["top10_names"][0] if ret[pid]["top10_names"] else ""
    ret_rank1_when_promoting[ret_rank1_name] += 1

print("\n=== What retriever had at rank-1 in pp2-only promotions (top-20) ===")
for name, cnt in ret_rank1_when_promoting.most_common(20):
    print(f"  {cnt:3d}  {name}")

# ── 7. Detailed samples grouped by retriever-rank ────────────────────────
by_ret_rank = defaultdict(list)
for pid in pp2_only_promotes:
    by_ret_rank[ret[pid]["ret_rank"]].append(pid)

print("\n=== Sample pp2-only promotions by retriever rank of truth ===")
for rank in [2, 3, 4, 5, 6, 7, 8, 9, 10]:
    cases = by_ret_rank[rank]
    if not cases:
        continue
    print(f"\n--- Truth was at retriever rank {rank} ({len(cases)} cases) ---")
    for pid in cases[:6]:
        truth_ids = list(ret[pid]["truth"])
        r_top3 = list(zip(ret[pid]["top10_ids"][:5], ret[pid]["top10_names"][:5]))
        v7_top3 = list(zip(v7[pid]["ranked_ids"][:5], v7[pid]["ranked_names"][:5]))
        p2_top3 = list(zip(pp2[pid]["ranked_ids"][:5], pp2[pid]["ranked_names"][:5]))
        print(f"\n  {pid}")
        print(f"    truth     : {truth_ids} — {pp2[pid]['truth_labels']}")
        print(f"    ret top5  : {[f'{n}({i})' for i,n in r_top3]}")
        print(f"    v7  top5  : {[f'{n}({i})' for i,n in v7_top3]}")
        print(f"    pp2 top5  : {[f'{n}({i})' for i,n in p2_top3]}")

# ── 8. Hit@3 and hit@10 breakdown ─────────────────────────────────────────
print("\n=== pp2-only promotions: how pp2 ranks the truth (1 by definition) ===")
# All these are hit@1=1 for pp2, but let's confirm
all_pp2_rank1 = sum(1 for pid in pp2_only_promotes if pp2[pid]["ranked_ids"] and
                    pp2[pid]["ranked_ids"][0] in ret[pid]["truth"])
print(f"  Confirmed pp2 rank=1: {all_pp2_rank1}/{len(pp2_only_promotes)}")

# ── 9. Net summary ────────────────────────────────────────────────────────
print("\n=== Hit@1/3/10 on fair set for pp2-only promotion cases ===")
print(f"  Cases: {len(pp2_only_promotes)}")
ret_h1  = sum(ret[p]["ret_hit1"] for p in pp2_only_promotes)
v7_h1   = sum(int(v7[p]["hit1"])  for p in pp2_only_promotes)
pp2_h1  = sum(int(pp2[p]["hit1"]) for p in pp2_only_promotes)
v7_h3   = sum(int(v7[p]["hit3"])  for p in pp2_only_promotes)
pp2_h3  = sum(int(pp2[p]["hit3"]) for p in pp2_only_promotes)
print(f"  Retriever hit@1 in this subset: {ret_h1} (should be 0)")
print(f"  v7  hit@1: {v7_h1}  hit@3: {v7_h3}")
print(f"  pp2 hit@1: {pp2_h1} hit@3: {pp2_h3}")

# ── 10. Were these promotions cases where v7 at least got hit@3/10? ───────
v7_hit3_in_pp2promo = [pid for pid in pp2_only_promotes if v7[pid]["hit3"] == 1]
v7_hit10_in_pp2promo = [pid for pid in pp2_only_promotes if v7[pid]["hit10"] == 1]
print(f"\n  Of {len(pp2_only_promotes)} pp2-only promos:")
print(f"    v7 hit@3  in these: {len(v7_hit3_in_pp2promo)}")
print(f"    v7 hit@10 in these: {len(v7_hit10_in_pp2promo)}")
print(f"    v7 missed entirely : {len(pp2_only_promotes) - len(v7_hit10_in_pp2promo)}")
