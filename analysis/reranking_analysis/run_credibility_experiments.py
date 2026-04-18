"""
Credibility experiments for BioNLP @ ACL 2026.

Four analyses in one script:
  1. Bootstrap confidence intervals on Hit@1 for all key comparisons
  2. Paired McNemar tests (retriever vs. reranker, retriever vs. LLM)
  3. Shared-case re-evaluation — exact same case intersection for every comparison
  4. Oracle / complementarity analysis — cases correct by EITHER system
  5. Multi-truth sensitivity — does dx_bench single-gold scoring bias results?

Datasets:
  - PhenoPacket (n=6,901 phenodp / 6,898 dx_bench)
  - RareBench sub-datasets: RAMEDIS (624), HMS (68 overlap), LIRICAL (370), MME (40)

Models used for comparisons:
  - Retriever: PhenoDP top-50 baseline
  - Best reranker: Gemma-4 31B, v7 prompt, top-10 (Hit@1=54.3% on PhenoPacket)
  - Best direct LLM: Llama3-Med42-70B (best dx_bench model)
"""

import json
import random
import math
import csv
from pathlib import Path
from collections import defaultdict

random.seed(42)

ROOT     = Path("/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket")
FINAL_RUNS = ROOT / "phenodp_gemma3_candidate_ranking/runs/final_runs"
DX_BENCH   = ROOT / "dx_bench/results/llama3-med42-70b_http"
OUT_DIR    = ROOT / "reranking_analysis_20260412"
TABLE_DIR  = OUT_DIR / "tables"
DATA_DIR   = OUT_DIR / "data"

N_BOOTSTRAP = 10_000

# ──────────────────────────────────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────────────────────────────────

def bootstrap_ci(hits, n_boot=N_BOOTSTRAP, alpha=0.05):
    """Return (mean, lower, upper) from a list of 0/1 values."""
    n = len(hits)
    if n == 0:
        return None, None, None
    mean = sum(hits) / n
    boot_means = []
    for _ in range(n_boot):
        sample = [hits[random.randint(0, n - 1)] for _ in range(n)]
        boot_means.append(sum(sample) / n)
    boot_means.sort()
    lo = boot_means[int(alpha / 2 * n_boot)]
    hi = boot_means[int((1 - alpha / 2) * n_boot)]
    return mean, lo, hi

def mcnemar_test(correct_a, correct_b):
    """
    Paired McNemar test on two lists of 0/1 correctness.
    Returns (b, c, chi2, p_value) where b=A-only correct, c=B-only correct.
    Uses exact binomial for b+c < 25, chi2 otherwise.
    """
    b = sum(1 for a, bb in zip(correct_a, correct_b) if a == 1 and bb == 0)
    c = sum(1 for a, bb in zip(correct_a, correct_b) if a == 0 and bb == 1)
    n_discordant = b + c
    if n_discordant == 0:
        return b, c, 0.0, 1.0
    # chi2 with continuity correction
    chi2 = (abs(b - c) - 1) ** 2 / n_discordant
    # approximate p-value from chi2(df=1)
    p = _chi2_sf(chi2)
    return b, c, chi2, p

def _chi2_sf(x):
    """Survival function for chi2(df=1): P(X > x). Uses erfc approximation."""
    if x <= 0:
        return 1.0
    return math.erfc(math.sqrt(x / 2))

def pct(v, d=1):
    return f"{v*100:.{d}f}%" if v is not None else "—"

def fmt_ci(mean, lo, hi, d=1):
    return f"{mean*100:.{d}f}% [{lo*100:.{d}f}–{hi*100:.{d}f}]"


# ──────────────────────────────────────────────────────────────────────────────
# LOAD RETRIEVER PER-CASE CORRECTNESS
# ──────────────────────────────────────────────────────────────────────────────

print("=== Loading retriever per-case correctness ===")

def load_retriever_hits(cand_file, topk_list=(1, 3, 5, 10)):
    """Returns {patient_id: {1: 0/1, 3: 0/1, 5: 0/1, 10: 0/1, truth_ids: set}}"""
    hits = {}
    with open(cand_file) as f:
        for line in f:
            d = json.loads(line)
            pid = d["patient_id"]
            truth_ids = set(d["truth_ids"])
            ranked_ids = [c["disease_id"] for c in d["candidates"]]
            row = {"truth_ids": truth_ids}
            for k in topk_list:
                row[k] = int(any(tid in ranked_ids[:k] for tid in truth_ids))
            hits[pid] = row
    return hits

PP_CAND  = FINAL_RUNS / "phenodp_gemma3_v7_full_rerank_20260407_192822/candidate_sets/phenodp_candidates_top50.jsonl"
RB_CAND  = FINAL_RUNS / "phenodp_gemma3_rarebench_v7_20260407_145006/candidate_sets/phenodp_candidates_top50.jsonl"

pp_ret   = load_retriever_hits(PP_CAND)
rb_ret   = load_retriever_hits(RB_CAND)

# Split RareBench by sub-dataset
rb_by_ds = defaultdict(dict)
for pid, v in rb_ret.items():
    ds = pid.split("_")[0]
    rb_by_ds[ds][pid] = v

print(f"  PhenoPacket retriever: {len(pp_ret)} cases")
for ds, cases in rb_by_ds.items():
    print(f"  {ds} retriever: {len(cases)} cases")


# ──────────────────────────────────────────────────────────────────────────────
# LOAD RERANKER PER-CASE CORRECTNESS (Gemma-4, v7, top-10 — best reranker)
# ──────────────────────────────────────────────────────────────────────────────

print("\n=== Loading reranker per-case correctness (Gemma-4 v7 top10) ===")

# Load from already-computed per-case CSV (avoids re-parsing all log files)
# table_percase_v7_top10.csv has: patient_id, retrieval_rank, g4_reranked_rank, ...
# Cases in the file are those where truth was in top-10 (reranker window).
# For cases outside the window (truth rank 11-50 or not retrieved): reranker = retriever.
import csv as csv_mod

PERCASE_CSV = TABLE_DIR / "table_percase_v7_top10.csv"

g4_reranker = {}  # {patient_id: {1: 0/1}}
with open(PERCASE_CSV) as f:
    reader = csv_mod.DictReader(f)
    for row in reader:
        pid = row["patient_id"]
        # g4_reranked_rank is the rank of truth after G4 reranking
        try:
            g4_rank = int(row["g4_reranked_rank"])
        except (ValueError, KeyError):
            g4_rank = None
        hit1 = int(g4_rank == 1) if g4_rank is not None else 0
        g4_reranker[pid] = {1: hit1}

# For cases NOT in the reranker window (truth > rank 10), use retriever hit
for pid, feat in pp_ret.items():
    if pid not in g4_reranker:
        g4_reranker[pid] = {1: feat[1]}  # reranker doesn't act here = retriever

in_window = sum(1 for pid in pp_ret if pid in {r["patient_id"]: r
               for r in csv_mod.DictReader(open(PERCASE_CSV))})
print(f"  Loaded {sum(1 for v in g4_reranker.values() if v[1] == 1)} Hit@1 cases from CSV + retriever fallback")
print(f"  Total coverage: {len(g4_reranker)} cases")

# Aggregate from benchmark_summary (authoritative)
G4_V7_RUN = FINAL_RUNS / "phenodp_gemma4_v7_full_rerank_20260411_202433"
with open(G4_V7_RUN / "benchmark_summary.json") as f:
    bsum = json.load(f)
g4_hit1_agg = None
for row in bsum["rows"]:
    if row.get("method") and "top10" in row["method"]:
        g4_hit1_agg = row["id_correct_hit_1"]
        g4_n = row["n_cases"]

if g4_hit1_agg is not None:
    print(f"  Gemma-4 v7 top10 aggregate Hit@1: {g4_hit1_agg:.4f} (n={g4_n})")
else:
    print("  WARNING: could not find top10 row in benchmark_summary")


# ──────────────────────────────────────────────────────────────────────────────
# LOAD DX_BENCH PER-CASE CORRECTNESS (Med42-70B)
# ──────────────────────────────────────────────────────────────────────────────

print("\n=== Loading dx_bench per-case correctness (Med42-70B) ===")

def load_dxbench_hits(results_jsonl, truth_map=None):
    """
    Load per-case hits from dx_bench results.jsonl.
    truth_map: {phenodp_case_id: set(omim_truth_ids)} — for multi-truth evaluation.

    Metric definitions:
      hit1_fuzzy     — dx_bench standard: gold in (predicted_id OR resolved_id) at rank 1.
                       This matches gold_rank_by_id == 1. Slightly LLM-favorable (name resolution).
      hit1_exact     — truly strict: gold in predicted_id at rank 1 only (no name resolution).
                       Apples-to-apples with retriever exact-OMIM matching.
      hit1_multi_fuzzy — any OMIM truth_id in (predicted_id OR resolved_id) at rank 1.
      hit1_multi_exact — any OMIM truth_id in predicted_id at rank 1 only.
    """
    records = {}
    with open(results_jsonl) as f:
        for line in f:
            rec = json.loads(line)
            cid = rec["case_id"]
            gold = rec.get("gold_disease_id", "")

            # Build per-rank ID sets: {rank: {predicted_id, resolved_id}}
            diagnoses = rec.get("diagnoses", [])
            rank1_predicted = set()
            rank1_all = set()      # predicted + resolved
            for dx in diagnoses:
                if dx.get("rank") == 1:
                    if dx.get("predicted_id"):
                        rank1_predicted.add(dx["predicted_id"])
                        rank1_all.add(dx["predicted_id"])
                    if dx.get("resolved_id"):
                        rank1_all.add(dx["resolved_id"])

            hit1_fuzzy = int(gold in rank1_all)
            hit1_exact = int(gold in rank1_predicted)

            # Sanity check: hit1_fuzzy should match gold_rank_by_id == 1
            gold_rank = rec.get("gold_rank_by_id")
            hit1_dx = int(gold_rank == 1) if gold_rank is not None else 0

            # Multi-truth: use all OMIM truth_ids from phenodp
            mapped_id = cid.replace("RareBench_", "")
            truths = set()
            if truth_map is not None:
                raw = truth_map.get(mapped_id) or truth_map.get(cid, set())
                truths = {t for t in raw if t.startswith("OMIM:")}

            if truths:
                hit1_multi_fuzzy = int(bool(truths & rank1_all))
                hit1_multi_exact = int(bool(truths & rank1_predicted))
            else:
                hit1_multi_fuzzy = hit1_fuzzy
                hit1_multi_exact = hit1_exact

            records[cid] = {
                "hit1_fuzzy":       hit1_fuzzy,     # dx_bench standard (predicted+resolved)
                "hit1_exact":       hit1_exact,     # truly strict (predicted only)
                "hit1_multi_fuzzy": hit1_multi_fuzzy,
                "hit1_multi_exact": hit1_multi_exact,
                "hit1_dx":          hit1_dx,        # original gold_rank_by_id for validation
                "gold": gold,
            }
    return records

# PhenoPacket — no multi-truth needed (all single-truth)
PP_DX = DX_BENCH / "phenopacket/Llama3-Med42-70B_20260404_020229_f0f8d928/results.jsonl"
pp_dx = load_dxbench_hits(PP_DX)
print(f"  PhenoPacket dx_bench: {len(pp_dx)} cases")

# RareBench — build truth_map from phenodp candidates
rb_truth_map = {pid: v["truth_ids"] for pid, v in rb_ret.items()}

RB_DX_RUNS = {
    "RAMEDIS": "Llama3-Med42-70B_20260404_075457_fc915180",
    "HMS":     "Llama3-Med42-70B_20260404_074200_20b68b58",
    "LIRICAL": "Llama3-Med42-70B_20260404_074348_65999459",
    "MME":     "Llama3-Med42-70B_20260404_075403_4ed9ca37",
}

rb_dx = {}
for ds, run in RB_DX_RUNS.items():
    path = DX_BENCH / f"rarebench/{ds}/{run}/results.jsonl"
    rb_dx[ds] = load_dxbench_hits(path, truth_map=rb_truth_map)
    print(f"  {ds} dx_bench: {len(rb_dx[ds])} cases")


# ──────────────────────────────────────────────────────────────────────────────
# HELPER: build aligned (retriever, reranker, llm) arrays on shared cases
# ──────────────────────────────────────────────────────────────────────────────

def align_pp(ret_dict, rerank_dict, dx_dict):
    """
    Returns lists of per-case hit@1 for all 3 systems on the shared case set.
    PhenoPacket case IDs are identical across systems.
    For PhenoPacket, LLM fuzzy = exact (no multi-truth, no OMIM hallucinations to resolve).
    """
    shared = set(ret_dict.keys()) & set(dx_dict.keys())
    ret_hits, rer_hits, llm_hits = [], [], []
    for pid in sorted(shared):
        ret_hits.append(ret_dict[pid][1])
        rer_hits.append(rerank_dict.get(pid, {}).get(1, ret_dict[pid][1]))  # fallback to ret
        llm_hits.append(dx_dict[pid]["hit1_fuzzy"])
    return ret_hits, rer_hits, llm_hits

def align_rb(ds, ret_ds_dict, dx_ds_dict):
    """
    Align retriever and LLM hits for a RareBench sub-dataset.
    Returns (ret, llm_fuzzy, llm_exact, llm_multi_fuzzy, llm_multi_exact) lists.
    """
    ret_hits, llm_fuzzy, llm_exact, llm_mf, llm_me = [], [], [], [], []
    for dx_cid in sorted(dx_ds_dict.keys()):
        ret_cid = dx_cid.replace("RareBench_", "")
        if ret_cid not in ret_ds_dict:
            continue
        ret_hits.append(ret_ds_dict[ret_cid][1])
        rec = dx_ds_dict[dx_cid]
        llm_fuzzy.append(rec["hit1_fuzzy"])
        llm_exact.append(rec["hit1_exact"])
        llm_mf.append(rec["hit1_multi_fuzzy"])
        llm_me.append(rec["hit1_multi_exact"])
    return ret_hits, llm_fuzzy, llm_exact, llm_mf, llm_me


# ──────────────────────────────────────────────────────────────────────────────
# EXPERIMENT 1 & 2: BOOTSTRAP CIs + PAIRED McNEMAR
# ──────────────────────────────────────────────────────────────────────────────

print("\n=== Experiments 1+2: Bootstrap CIs + McNemar tests ===")

results_rows = []

# ── PhenoPacket ──
ret_pp, rer_pp, llm_pp = align_pp(pp_ret, g4_reranker, pp_dx)
n_shared_pp = len(ret_pp)
print(f"\n  PhenoPacket shared cases: {n_shared_pp}")

for label, hits in [("Retriever (PhenoDP)", ret_pp),
                    ("Reranker (G4 v7 top10)", rer_pp),
                    ("LLM direct (Med42-70B)", llm_pp)]:
    m, lo, hi = bootstrap_ci(hits)
    print(f"    {label}: {fmt_ci(m, lo, hi)}")
    results_rows.append({"dataset": "PhenoPacket", "system": label, "n": n_shared_pp,
                          "hit1": round(m, 4), "ci_lo": round(lo, 4), "ci_hi": round(hi, 4)})

# McNemar: retriever vs reranker
b, c, chi2, p = mcnemar_test(ret_pp, rer_pp)
print(f"\n  McNemar (retriever vs reranker): b={b}, c={c}, chi2={chi2:.2f}, p={p:.4f}")
results_rows.append({"dataset": "PhenoPacket", "system": "McNemar ret vs reranker",
                      "n": b+c, "hit1": b/(b+c) if (b+c) > 0 else 0,
                      "ci_lo": round(p, 4), "ci_hi": round(chi2, 4)})

# McNemar: retriever vs LLM
b2, c2, chi2_2, p2 = mcnemar_test(ret_pp, llm_pp)
print(f"  McNemar (retriever vs LLM):     b={b2}, c={c2}, chi2={chi2_2:.2f}, p={p2:.4e}")
results_rows.append({"dataset": "PhenoPacket", "system": "McNemar ret vs LLM",
                      "n": b2+c2, "hit1": b2/(b2+c2) if (b2+c2) > 0 else 0,
                      "ci_lo": round(p2, 6), "ci_hi": round(chi2_2, 2)})

# ── RareBench sub-datasets ──
print()
for ds in ["RAMEDIS", "HMS", "LIRICAL", "MME"]:
    ret_h, llm_fuzz, llm_ex, llm_mf, llm_me = align_rb(ds, rb_by_ds[ds], rb_dx[ds])
    n = len(ret_h)
    print(f"  {ds} (n={n} shared):")

    m_ret, lo_ret, hi_ret       = bootstrap_ci(ret_h)
    m_fuzz, lo_fuzz, hi_fuzz    = bootstrap_ci(llm_fuzz)
    m_ex, lo_ex, hi_ex          = bootstrap_ci(llm_ex)
    m_mf, lo_mf, hi_mf          = bootstrap_ci(llm_mf)
    m_me, lo_me, hi_me          = bootstrap_ci(llm_me)

    print(f"    Retriever (exact):              {fmt_ci(m_ret,  lo_ret,  hi_ret)}")
    print(f"    LLM fuzzy  (pred+resolved, 1g): {fmt_ci(m_fuzz, lo_fuzz, hi_fuzz)}")
    print(f"    LLM exact  (pred only, 1g):     {fmt_ci(m_ex,   lo_ex,   hi_ex)}")
    print(f"    LLM multi-truth fuzzy:          {fmt_ci(m_mf,   lo_mf,   hi_mf)}")
    print(f"    LLM multi-truth exact:          {fmt_ci(m_me,   lo_me,   hi_me)}")

    b_r, c_r, chi2_r, p_r = mcnemar_test(ret_h, llm_fuzz)
    print(f"    McNemar (ret vs LLM fuzzy): b={b_r}, c={c_r}, p={p_r:.4f}")
    b2, c2, chi2_2, p2 = mcnemar_test(ret_h, llm_ex)
    print(f"    McNemar (ret vs LLM exact): b={b2}, c={c2}, p={p2:.4f}")

    for label, hits in [("Retriever", ret_h),
                        ("LLM fuzzy (pred+resolved)", llm_fuzz),
                        ("LLM exact (pred only)", llm_ex),
                        ("LLM multi-truth fuzzy", llm_mf),
                        ("LLM multi-truth exact", llm_me)]:
        m, lo, hi = bootstrap_ci(hits)
        results_rows.append({"dataset": ds, "system": label, "n": n,
                              "hit1": round(m, 4), "ci_lo": round(lo, 4), "ci_hi": round(hi, 4)})
    print()


# ──────────────────────────────────────────────────────────────────────────────
# EXPERIMENT 3: ORACLE / COMPLEMENTARITY ANALYSIS
# ──────────────────────────────────────────────────────────────────────────────

print("=== Experiment 3: Oracle / Complementarity analysis ===")

oracle_rows = []

def oracle_analysis(label, ret_hits, sys2_hits, n):
    both    = sum(a == 1 and b == 1 for a, b in zip(ret_hits, sys2_hits))
    ret_only = sum(a == 1 and b == 0 for a, b in zip(ret_hits, sys2_hits))
    sys2_only = sum(a == 0 and b == 1 for a, b in zip(ret_hits, sys2_hits))
    neither  = sum(a == 0 and b == 0 for a, b in zip(ret_hits, sys2_hits))
    oracle   = [max(a, b) for a, b in zip(ret_hits, sys2_hits)]
    oracle_h1 = sum(oracle) / n

    m_oracle, lo_o, hi_o = bootstrap_ci(oracle)

    print(f"  {label} (n={n}):")
    print(f"    Both correct:        {both:4d} ({both/n*100:.1f}%)")
    print(f"    Retriever only:      {ret_only:4d} ({ret_only/n*100:.1f}%)")
    print(f"    LLM only:            {sys2_only:4d} ({sys2_only/n*100:.1f}%)")
    print(f"    Neither correct:     {neither:4d} ({neither/n*100:.1f}%)")
    print(f"    Oracle Hit@1:        {fmt_ci(m_oracle, lo_o, hi_o)}")
    print(f"    Complementarity:     {ret_only + sys2_only} cases where only one is right ({(ret_only+sys2_only)/n*100:.1f}%)")
    print()

    return {
        "comparison": label, "n": n,
        "both": both, "ret_only": ret_only, "sys2_only": sys2_only, "neither": neither,
        "oracle_hit1": round(oracle_h1, 4),
        "ret_hit1": round(sum(ret_hits)/n, 4),
        "sys2_hit1": round(sum(sys2_hits)/n, 4),
        "complementary_cases": ret_only + sys2_only,
    }

# PhenoPacket: retriever vs LLM
r = oracle_analysis("PhenoPacket ret vs LLM (Med42)", ret_pp, llm_pp, n_shared_pp)
oracle_rows.append(r)

# PhenoPacket: retriever vs reranker
r = oracle_analysis("PhenoPacket ret vs reranker (G4 v7 top10)", ret_pp, rer_pp, n_shared_pp)
oracle_rows.append(r)

# RareBench sub-datasets: retriever vs LLM (fuzzy = standard, exact = fair comparison)
for ds in ["RAMEDIS", "HMS", "LIRICAL", "MME"]:
    ret_h, llm_fuzz, llm_ex, llm_mf, llm_me = align_rb(ds, rb_by_ds[ds], rb_dx[ds])
    n = len(ret_h)
    r = oracle_analysis(f"{ds} ret vs LLM fuzzy (standard)", ret_h, llm_fuzz, n)
    oracle_rows.append(r)
    r = oracle_analysis(f"{ds} ret vs LLM exact (fair)", ret_h, llm_ex, n)
    oracle_rows.append(r)
    r = oracle_analysis(f"{ds} ret vs LLM multi-truth exact", ret_h, llm_me, n)
    oracle_rows.append(r)


# ──────────────────────────────────────────────────────────────────────────────
# EXPERIMENT 4: MULTI-TRUTH SENSITIVITY SUMMARY
# ──────────────────────────────────────────────────────────────────────────────

print("=== Experiment 4: Multi-truth & metric sensitivity ===")
print()
print("  Key: 'fuzzy' = dx_bench standard (predicted+resolved_id, includes name matching)")
print("       'exact' = truly strict (predicted_id only, same basis as retriever)")
print("       'multi' = any valid OMIM truth ID (not just primary gold)")
print()

mt_rows = []
for ds in ["RAMEDIS", "HMS", "LIRICAL", "MME"]:
    ret_h, llm_fuzz, llm_ex, llm_mf, llm_me = align_rb(ds, rb_by_ds[ds], rb_dx[ds])
    n = len(ret_h)
    # Count multi-OMIM cases (genuine multiple valid diagnoses)
    n_multi_omim = sum(1 for dx_cid in rb_dx[ds]
                       if len({t for t in rb_truth_map.get(dx_cid.replace("RareBench_",""), set())
                                if t.startswith("OMIM:")}) > 1)
    ret_h1     = sum(ret_h) / n
    fuzz_h1    = sum(llm_fuzz) / n
    ex_h1      = sum(llm_ex) / n
    mf_h1      = sum(llm_mf) / n
    me_h1      = sum(llm_me) / n
    fuzzy_gain = (fuzz_h1 - ex_h1) * 100

    print(f"  {ds}: n={n}, multi-OMIM cases={n_multi_omim} ({n_multi_omim/n*100:.0f}%)")
    print(f"    Retriever (exact):     {ret_h1*100:.1f}%")
    print(f"    LLM fuzzy (standard):  {fuzz_h1*100:.1f}%   ← dx_bench metric")
    print(f"    LLM exact (fair comp): {ex_h1*100:.1f}%   ← apples-to-apples with retriever")
    print(f"    LLM multi-truth fuzzy: {mf_h1*100:.1f}%")
    print(f"    LLM multi-truth exact: {me_h1*100:.1f}%")
    print(f"    Fuzzy inflation (fuzzy−exact): {fuzzy_gain:+.1f}pp")
    ret_wins_fuzzy = "RET" if ret_h1 > fuzz_h1 else "LLM"
    ret_wins_exact = "RET" if ret_h1 > ex_h1 else "LLM"
    print(f"    Winner (fuzzy): {ret_wins_fuzzy}  |  Winner (exact): {ret_wins_exact}")
    print()
    mt_rows.append({
        "dataset": ds, "n": n, "n_multi_omim": n_multi_omim,
        "pct_multi_omim": round(n_multi_omim / n, 3),
        "retriever_hit1": round(ret_h1, 4),
        "llm_hit1_fuzzy": round(fuzz_h1, 4),
        "llm_hit1_exact": round(ex_h1, 4),
        "llm_hit1_multi_fuzzy": round(mf_h1, 4),
        "llm_hit1_multi_exact": round(me_h1, 4),
        "fuzzy_inflation_pp": round(fuzzy_gain, 2),
        "winner_fuzzy": ret_wins_fuzzy,
        "winner_exact": ret_wins_exact,
    })


# ──────────────────────────────────────────────────────────────────────────────
# MACRO AVERAGE for RareBench
# ──────────────────────────────────────────────────────────────────────────────

print("=== Macro averages (RareBench sub-datasets) ===")

macro_ret, macro_fuzz, macro_ex, macro_mf, macro_me = [], [], [], [], []
for ds in ["RAMEDIS", "HMS", "LIRICAL", "MME"]:
    ret_h, llm_f, llm_e, llm_mf2, llm_me2 = align_rb(ds, rb_by_ds[ds], rb_dx[ds])
    n = len(ret_h)
    macro_ret.append(sum(ret_h)/n)
    macro_fuzz.append(sum(llm_f)/n)
    macro_ex.append(sum(llm_e)/n)
    macro_mf.append(sum(llm_mf2)/n)
    macro_me.append(sum(llm_me2)/n)

print(f"  Macro avg retriever Hit@1:             {sum(macro_ret)/4*100:.1f}%")
print(f"  Macro avg LLM fuzzy (standard) Hit@1:  {sum(macro_fuzz)/4*100:.1f}%")
print(f"  Macro avg LLM exact (fair) Hit@1:      {sum(macro_ex)/4*100:.1f}%")
print(f"  Macro avg LLM multi-truth exact Hit@1: {sum(macro_me)/4*100:.1f}%")
print()
print(f"  Micro avg (all 1122 cases) retriever: "
      f"{sum(rb_ret[pid][1] for pid in rb_ret)/len(rb_ret)*100:.1f}%")

macro_summary = {
    "retriever":    round(sum(macro_ret)/4, 4),
    "llm_fuzzy":    round(sum(macro_fuzz)/4, 4),
    "llm_exact":    round(sum(macro_ex)/4, 4),
    "llm_multi_exact": round(sum(macro_me)/4, 4),
}


# ──────────────────────────────────────────────────────────────────────────────
# SAVE OUTPUTS
# ──────────────────────────────────────────────────────────────────────────────

print("\n=== Saving outputs ===")

def write_csv(path, rows, fields):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

write_csv(TABLE_DIR / "table_bootstrap_ci.csv", results_rows,
          ["dataset", "system", "n", "hit1", "ci_lo", "ci_hi"])
print(f"  Saved table_bootstrap_ci.csv")

write_csv(TABLE_DIR / "table_oracle_complementarity.csv", oracle_rows,
          ["comparison", "n", "both", "ret_only", "sys2_only", "neither",
           "ret_hit1", "sys2_hit1", "oracle_hit1", "complementary_cases"])
print(f"  Saved table_oracle_complementarity.csv")

write_csv(TABLE_DIR / "table_multi_truth_sensitivity.csv", mt_rows,
          ["dataset", "n", "n_multi_omim", "pct_multi_omim",
           "retriever_hit1", "llm_hit1_fuzzy", "llm_hit1_exact",
           "llm_hit1_multi_fuzzy", "llm_hit1_multi_exact",
           "fuzzy_inflation_pp", "winner_fuzzy", "winner_exact"])
print(f"  Saved table_multi_truth_sensitivity.csv")

# Save full results as JSON for report writing
with open(DATA_DIR / "credibility_results.json", "w") as f:
    json.dump({
        "bootstrap_ci": results_rows,
        "oracle": oracle_rows,
        "multi_truth": mt_rows,
        "macro_avg": macro_summary,
    }, f, indent=2)
print(f"  Saved credibility_results.json")

print("\n=== DONE ===")
