"""
Disease-level pattern analysis: which diseases get promoted / demoted and why.

Uses the same log parsing as run_promo_pattern_analysis.py but aggregates
by truth disease label to answer:
  1. Which diseases benefit most from LLM reranking (high promotion rate)?
  2. Which diseases are harmed most (high demotion rate)?
  3. What does the LLM prefer instead when it demotes the correct disease?
     (confusion pairs)
  4. Are demotion patterns consistent with LLM frequency bias (well-known diseases
     being preferred over rarer ones)?
  5. Disease-category patterns (OMIM disease class groupings)?

Focus: PhenoPacket dataset (n=6,901), v7 prompt, top-10 (most scope for reranking).
Best single model: Gemma-4 31B.  We also check cross-model consistency of findings.
"""

import json
import re
import csv
from pathlib import Path
from collections import defaultdict, Counter
import statistics

ROOT = Path("/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket")
FINAL_RUNS = ROOT / "phenodp_gemma3_candidate_ranking/runs/final_runs"
OUT_DIR = ROOT / "reranking_analysis_20260412"
TABLE_DIR = OUT_DIR / "tables"
DATA_DIR = OUT_DIR / "data"

# ──────────────────────────────────────────────────────────────────────────────
# LOG PARSING HELPERS (same as existing scripts)
# ──────────────────────────────────────────────────────────────────────────────

def parse_candidate_list_from_prompt(log_text):
    name_to_id = {}
    for match in re.finditer(r"\d+\.\s+(.+?)\s+\((OMIM:\d+|ORPHA:\d+)\)", log_text):
        name = match.group(1).strip().lower()
        name_to_id[name] = match.group(2)
    return name_to_id

def parse_reranked_output(log_text):
    raw_section = re.search(r"RAW OUTPUT:\s*(.*?)$", log_text, re.DOTALL)
    if not raw_section:
        return None, None
    raw_text = raw_section.group(1).strip()
    raw_text = re.sub(r"^```(?:json)?", "", raw_text, flags=re.MULTILINE).strip()
    raw_text = re.sub(r"```$", "", raw_text, flags=re.MULTILINE).strip()

    if raw_text.startswith("{"):
        try:
            data = json.loads(raw_text)
            selected = data.get("selected_candidate", {}).get("id")
            ranking = data.get("ranking", [])
            ranked_ids = [item["id"] for item in sorted(ranking, key=lambda x: x.get("rank", 99))]
            return selected, ranked_ids or None
        except Exception:
            sel_m = re.search(r'"selected_candidate".*?"id"\s*:\s*"([^"]+)"', raw_text)
            if sel_m:
                sel_id = sel_m.group(1)
                all_ids = re.findall(r'"id"\s*:\s*"([A-Z0-9:]+)"', raw_text)
                ranked = [sel_id] + [x for x in all_ids if x != sel_id]
                return sel_id, ranked if ranked else None
            return None, None

    name_to_id = parse_candidate_list_from_prompt(log_text)
    if not name_to_id:
        return None, None
    ranked_names = []
    for m in re.finditer(r"^(\d+)\.\s+(.+)$", raw_text, re.MULTILINE):
        rank_num = int(m.group(1))
        name = re.sub(r"\s*\((?:OMIM|ORPHA):\d+\)\s*$", "", m.group(2)).strip().lower()
        ranked_names.append((rank_num, name))
    ranked_names.sort(key=lambda x: x[0])
    ranked_ids = []
    for _, name in ranked_names:
        oid = name_to_id.get(name)
        if oid is None:
            for cname, cid in name_to_id.items():
                if cname in name or name in cname:
                    oid = cid
                    break
        if oid:
            ranked_ids.append(oid)
    if not ranked_ids:
        return None, None
    return ranked_ids[0], ranked_ids


# ──────────────────────────────────────────────────────────────────────────────
# LOAD CANDIDATE FEATURES + BUILD ID→NAME MAP
# ──────────────────────────────────────────────────────────────────────────────

print("=== Loading candidate features ===")

PP_CAND_FILE = FINAL_RUNS / "phenodp_gemma3_v7_full_rerank_20260407_192822/candidate_sets/phenodp_candidates_top50.jsonl"

# id→name lookup built from all candidates seen across all cases
disease_id_to_name = {}

def load_case_features(cand_file):
    features = {}
    with open(cand_file) as f:
        for line in f:
            d = json.loads(line)
            pid = d["patient_id"]
            cands = d["candidates"]
            truth_ids = set(d["truth_ids"])
            truth_labels = d.get("truth_labels", [])

            for c in cands:
                if c["disease_id"] not in disease_id_to_name:
                    disease_id_to_name[c["disease_id"]] = c["disease_name"]
            # also store truth label
            for tid, tlabel in zip(d["truth_ids"], truth_labels):
                if tid not in disease_id_to_name:
                    disease_id_to_name[tid] = tlabel

            ret_rank = None
            for i, c in enumerate(cands[:50]):
                if c["disease_id"] in truth_ids:
                    ret_rank = i + 1
                    break

            score_gap_1_2 = (cands[0]["score"] - cands[1]["score"]) if len(cands) > 1 else None

            features[pid] = {
                "patient_id": pid,
                "truth_ids": list(truth_ids),
                "truth_labels": truth_labels,
                "n_pos_hpo": len(d.get("phenotype_ids", [])),
                "n_neg_hpo": len(d.get("negative_phenotype_ids", [])),
                "has_genes": len(d.get("genes", [])) > 0,
                "retrieval_rank": ret_rank,
                "top1_id": cands[0]["disease_id"] if cands else None,
                "top1_name": cands[0]["disease_name"] if cands else None,
                "top1_score": cands[0]["score"] if cands else None,
                "score_gap_1_2": score_gap_1_2,
                "candidates": [(c["disease_id"], c["disease_name"], c["score"]) for c in cands[:10]],
            }
    return features

pp_features = load_case_features(PP_CAND_FILE)
print(f"  Loaded {len(pp_features)} PhenoPacket cases")
print(f"  Disease ID→name map: {len(disease_id_to_name)} entries")


# ──────────────────────────────────────────────────────────────────────────────
# PARSE V7 LOGS — collect per-case (truth_label, llm_top1_id, outcome)
# ──────────────────────────────────────────────────────────────────────────────

print("\n=== Parsing v7 logs for 3 models (top-10 only) ===")

V7_PP_RUNS = {
    "gemma3-27b": FINAL_RUNS / "phenodp_gemma3_v7_full_rerank_20260407_192822",
    "gemma4-31b": FINAL_RUNS / "phenodp_gemma4_v7_full_rerank_20260411_202433",
    "llama3.3-70b": FINAL_RUNS / "phenodp_llama70b_v7_full_rerank_20260410_102154",
}

TOPK = 10

def parse_run_top10(run_dir, model_name, case_features):
    """Returns {pid: {reranked_rank, llm_top1_id, delta, fallback}}"""
    method_dir = None
    for d in (run_dir / "methods").iterdir():
        if f"top{TOPK}" in d.name:
            method_dir = d
            break
    if method_dir is None:
        print(f"  WARNING: no top{TOPK} method dir in {run_dir}")
        return {}

    logs_dir = method_dir / "logs"
    results = {}
    log_files = list(logs_dir.glob("*.txt"))
    for log_file in log_files:
        pid = log_file.stem
        feat = case_features.get(pid, {})
        truth_ids = set(feat.get("truth_ids", []))
        ret_rank = feat.get("retrieval_rank")

        if ret_rank is None or ret_rank > TOPK:
            continue

        log_text = log_file.read_text(errors="ignore")
        selected_id, ranked_ids = parse_reranked_output(log_text)

        if ranked_ids is None:
            results[pid] = {
                "reranked_rank": ret_rank,
                "llm_top1_id": feat.get("top1_id"),
                "delta": 0,
                "fallback": True,
            }
            continue

        reranked_rank = None
        for i, rid in enumerate(ranked_ids[:TOPK]):
            if rid in truth_ids:
                reranked_rank = i + 1
                break
        if reranked_rank is None:
            reranked_rank = ret_rank

        results[pid] = {
            "reranked_rank": reranked_rank,
            "llm_top1_id": ranked_ids[0] if ranked_ids else feat.get("top1_id"),
            "llm_top1_name": disease_id_to_name.get(ranked_ids[0], ranked_ids[0]) if ranked_ids else None,
            "delta": ret_rank - reranked_rank,
            "fallback": False,
        }

    print(f"  {model_name}: {len(results)} in-window cases parsed")
    return results


model_results = {}
for model, run_dir in sorted(V7_PP_RUNS.items()):
    model_results[model] = parse_run_top10(run_dir, model, pp_features)


# ──────────────────────────────────────────────────────────────────────────────
# BUILD PER-CASE JOINT OUTCOMES (all 3 models must have the case)
# ──────────────────────────────────────────────────────────────────────────────

print("\n=== Building joint per-case outcomes ===")

models = ["gemma3-27b", "gemma4-31b", "llama3.3-70b"]

# All cases in window for at least one model
all_pids = set()
for m in models:
    all_pids |= set(model_results[m].keys())

print(f"  Total in-window cases (union): {len(all_pids)}")

# For disease-level analysis focus on cases where G4 (best model) has result
g4_pids = set(model_results["gemma4-31b"].keys())
print(f"  Gemma-4 in-window cases: {len(g4_pids)}")


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 1: PER-DISEASE PROMOTION / DEMOTION RATES (Gemma-4, v7, top-10)
# ──────────────────────────────────────────────────────────────────────────────

print("\n=== Section 1: Per-disease promotion/demotion rates ===")

# disease_label → {promoted, demoted, unchanged, total}
disease_stats = defaultdict(lambda: {
    "promoted": 0, "demoted": 0, "unchanged": 0, "total": 0,
    "promo_delta_sum": 0, "demo_delta_sum": 0,
})

g4_res = model_results["gemma4-31b"]

for pid, res in g4_res.items():
    feat = pp_features.get(pid, {})
    truth_labels = feat.get("truth_labels", ["Unknown"])
    label = truth_labels[0] if truth_labels else "Unknown"

    delta = res["delta"]
    disease_stats[label]["total"] += 1

    if delta > 0:
        disease_stats[label]["promoted"] += 1
        disease_stats[label]["promo_delta_sum"] += delta
    elif delta < 0:
        disease_stats[label]["demoted"] += 1
        disease_stats[label]["demo_delta_sum"] += abs(delta)
    else:
        disease_stats[label]["unchanged"] += 1

# Filter to diseases with ≥3 cases in window
disease_rows = []
for label, stats in disease_stats.items():
    total = stats["total"]
    if total < 3:
        continue
    promo = stats["promoted"]
    demo = stats["demoted"]
    promo_rate = promo / total
    demo_rate = demo / total
    net = promo - demo
    disease_rows.append({
        "disease": label,
        "n_in_window": total,
        "n_promoted": promo,
        "n_demoted": demo,
        "n_unchanged": stats["unchanged"],
        "promo_rate": round(promo_rate, 4),
        "demo_rate": round(demo_rate, 4),
        "net": net,
        "net_rate": round((promo - demo) / total, 4),
        "mean_promo_delta": round(stats["promo_delta_sum"] / promo, 2) if promo > 0 else 0,
        "mean_demo_delta": round(stats["demo_delta_sum"] / demo, 2) if demo > 0 else 0,
    })

# Sort by promo_rate descending for "most helped" diseases
disease_rows_promo = sorted(disease_rows, key=lambda r: (-r["promo_rate"], -r["n_in_window"]))
# Sort by demo_rate descending for "most harmed" diseases
disease_rows_demo = sorted(disease_rows, key=lambda r: (-r["demo_rate"], -r["n_in_window"]))

print(f"  Diseases with ≥3 cases in window: {len(disease_rows)}")
print(f"\n  TOP 20 most promoted diseases:")
for r in disease_rows_promo[:20]:
    print(f"    {r['disease'][:50]:<50} | n={r['n_in_window']:3d} | promo={r['n_promoted']:2d} ({r['promo_rate']*100:.0f}%) | demo={r['n_demoted']:2d} ({r['demo_rate']*100:.0f}%)")

print(f"\n  TOP 20 most demoted diseases:")
for r in disease_rows_demo[:20]:
    if r["demo_rate"] > 0:
        print(f"    {r['disease'][:50]:<50} | n={r['n_in_window']:3d} | demo={r['n_demoted']:2d} ({r['demo_rate']*100:.0f}%) | promo={r['n_promoted']:2d} ({r['promo_rate']*100:.0f}%)")


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 2: DEMOTION CONFUSION PAIRS — what does LLM prefer instead?
# ──────────────────────────────────────────────────────────────────────────────

print("\n=== Section 2: Demotion confusion pairs ===")

# For each case where truth was at rank-1 and got demoted, record:
# (truth_label) → (llm_preferred_id, llm_preferred_name, count)
confusion_pairs = defaultdict(Counter)  # truth_label → Counter(llm_preferred_name)

# All demotions from rank-1 across all 3 models
demotion_events = []  # (pid, model, truth_label, llm_top1_id, llm_top1_name, score_gap)

for model in models:
    for pid, res in model_results[model].items():
        feat = pp_features.get(pid, {})
        ret_rank = feat.get("retrieval_rank")
        delta = res["delta"]
        if ret_rank == 1 and delta < 0:  # demoted from rank-1
            truth_labels = feat.get("truth_labels", ["Unknown"])
            truth_label = truth_labels[0] if truth_labels else "Unknown"
            llm_name = res.get("llm_top1_name") or disease_id_to_name.get(res.get("llm_top1_id", ""), "Unknown")
            llm_id = res.get("llm_top1_id", "Unknown")
            gap = feat.get("score_gap_1_2", 0)

            confusion_pairs[truth_label][llm_name] += 1
            demotion_events.append({
                "patient_id": pid,
                "model": model,
                "truth_label": truth_label,
                "llm_top1_id": llm_id,
                "llm_top1_name": llm_name,
                "score_gap": round(gap, 4) if gap else 0,
                "n_pos_hpo": feat.get("n_pos_hpo", 0),
                "n_neg_hpo": feat.get("n_neg_hpo", 0),
            })

print(f"  Total rank-1 demotion events (all 3 models): {len(demotion_events)}")
print(f"  Unique truth diseases demoted: {len(confusion_pairs)}")

# Top confusion pairs (truth → LLM preference) with ≥2 occurrences
print("\n  Top confusion pairs (truth → LLM preferred, ≥2 occurrences across any model):")
all_pairs = []
for truth, counter in confusion_pairs.items():
    for llm_name, count in counter.most_common():
        if count >= 2:
            all_pairs.append((count, truth, llm_name))
all_pairs.sort(reverse=True)
for count, truth, llm_name in all_pairs[:30]:
    print(f"    [{count:2d}x] {truth[:45]:<45} → {llm_name[:45]}")


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 3: PROMOTED CASES — which diseases get correctly promoted?
# ──────────────────────────────────────────────────────────────────────────────

print("\n=== Section 3: Diseases with consistent promotions ===")

# For each case promoted by G4 to rank-1, record truth_label and starting rank
promotion_events = []

for pid, res in g4_res.items():
    feat = pp_features.get(pid, {})
    ret_rank = feat.get("retrieval_rank")
    reranked_rank = res["reranked_rank"]
    if reranked_rank == 1 and ret_rank and ret_rank > 1:  # promoted TO rank-1
        truth_labels = feat.get("truth_labels", ["Unknown"])
        truth_label = truth_labels[0] if truth_labels else "Unknown"
        gap = feat.get("score_gap_1_2", 0)
        promotion_events.append({
            "patient_id": pid,
            "truth_label": truth_label,
            "from_rank": ret_rank,
            "score_gap": round(gap, 4) if gap else 0,
            "n_pos_hpo": feat.get("n_pos_hpo", 0),
            "n_neg_hpo": feat.get("n_neg_hpo", 0),
        })

print(f"  Total promotions to rank-1 (Gemma-4): {len(promotion_events)}")

# Group by disease
promo_by_disease = defaultdict(list)
for e in promotion_events:
    promo_by_disease[e["truth_label"]].append(e)

# Diseases with multiple promoted cases
multi_promo = sorted([(len(v), k, v) for k, v in promo_by_disease.items()], reverse=True)
print(f"\n  Diseases with ≥2 cases promoted to rank-1 by Gemma-4:")
for count, label, events in multi_promo:
    if count >= 2:
        from_ranks = [e["from_rank"] for e in events]
        mean_gap = statistics.mean([e["score_gap"] for e in events])
        print(f"    [{count:2d}x] {label[:50]:<50} | from ranks {sorted(from_ranks)} | mean gap={mean_gap:.3f}")


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 4: CROSS-MODEL CONSISTENCY FOR DEMOTION PAIRS
# ──────────────────────────────────────────────────────────────────────────────

print("\n=== Section 4: Cross-model consistency for demotion confusion pairs ===")

# Which confusion pairs are consistent across all 3 models?
# For each case, find cases where all models demote the same truth disease in favor of same LLM choice

# Per-case demotion summary
case_demotion = defaultdict(dict)  # pid → {model: llm_top1_name}
for e in demotion_events:
    case_demotion[e["patient_id"]][e["model"]] = e["llm_top1_name"]

consistent_demotions = []
for pid, model_prefs in case_demotion.items():
    if len(model_prefs) == 3:  # all models demoted this case
        prefs = list(model_prefs.values())
        if len(set(prefs)) == 1:  # all prefer same disease
            feat = pp_features.get(pid, {})
            truth_labels = feat.get("truth_labels", ["Unknown"])
            consistent_demotions.append({
                "patient_id": pid,
                "truth_label": truth_labels[0] if truth_labels else "Unknown",
                "llm_preferred": prefs[0],
                "score_gap": feat.get("score_gap_1_2", 0),
                "n_pos_hpo": feat.get("n_pos_hpo", 0),
                "n_neg_hpo": feat.get("n_neg_hpo", 0),
            })

print(f"  Cases where all 3 models agree on demotion AND prefer same disease: {len(consistent_demotions)}")

# Group by (truth, llm_preferred) pair
pair_counter = Counter()
for e in consistent_demotions:
    pair_counter[(e["truth_label"], e["llm_preferred"])] += 1

print("\n  Consistent confusion pairs (all 3 models agree):")
for (truth, llm_pref), count in pair_counter.most_common(20):
    print(f"    [{count:2d}x] {truth[:45]:<45} → {llm_pref[:45]}")


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 5: DISEASE CATEGORY ANALYSIS
# ──────────────────────────────────────────────────────────────────────────────

print("\n=== Section 5: Disease category patterns ===")

# Classify diseases into rough categories by keyword matching on disease name
# These are coarse but sufficient to detect category-level bias

CATEGORY_KEYWORDS = [
    ("Marfan / Connective tissue", ["marfan", "ectopia lentis", "ehlers-danlos", "loeys-dietz", "fibrillin"]),
    ("Rasopathy / RAS pathway",    ["noonan", "costello", "leopard", "cardio-facio", "legius", "neurofibromatosis"]),
    ("Skeletal dysplasia",         ["skeletal", "spondyl", "chondro", "osteogenesis", "achondro", "dysostosis"]),
    ("Cardiomyopathy",             ["cardiomyopathy", "arrhythmia", "brugada", "long qt", "dilated"]),
    ("Intellectual disability",    ["intellectual", "mental retarda", "cognitive", "id,", "id -", "rett"]),
    ("Metabolic / Lysosomal",      ["gaucher", "fabry", "niemann", "pompe", "mucopolysac", "glycogen", "lysosomal", "sphingolipid"]),
    ("Muscular dystrophy",         ["muscular dystrophy", "myopathy", "limb-girdle", "emery-dreifuss", "facioscapulo"]),
    ("Hereditary cancer",          ["lynch", "brca", "polyposis", "cowden", "gorlin", "von hippel", "retinoblastoma"]),
    ("Mitochondrial",              ["mitochondrial", "mito", "leigh", "kearns-sayre"]),
    ("Renal / Nephrotic",          ["renal", "nephrotic", "alport", "polycystic kidney", "tubular"]),
    ("Hearing loss",               ["deafness", "hearing loss", "usher", "pendred", "waardenburg"]),
    ("Vision / Retinal",           ["retinitis", "macular", "leber", "stargardt", "choroideremia"]),
    ("Immunodeficiency",           ["immunodeficiency", "agammaglobulin", "cgd", "granulomatous", "wiskott"]),
    ("Coagulation / Blood",        ["hemophilia", "thrombophilia", "von willebrand", "thalassemia", "sickle cell"]),
    ("Epilepsy / Neurological",    ["epilep", "seizure", "dravet", "angelman", "rett", "spinal muscular"]),
    ("Aarskog-Scott family",       ["aarskog", "faciodigitogenital"]),
    ("Amyloidosis",                ["amyloidosis"]),
    ("Holt-Oram family",           ["holt-oram"]),
]

def get_category(disease_name):
    dn = disease_name.lower()
    for cat, keywords in CATEGORY_KEYWORDS:
        if any(kw in dn for kw in keywords):
            return cat
    return "Other"

# Apply to disease rows
cat_stats = defaultdict(lambda: {"n_diseases": 0, "n_cases": 0, "n_promoted": 0, "n_demoted": 0})

for r in disease_rows:
    cat = get_category(r["disease"])
    cat_stats[cat]["n_diseases"] += 1
    cat_stats[cat]["n_cases"] += r["n_in_window"]
    cat_stats[cat]["n_promoted"] += r["n_promoted"]
    cat_stats[cat]["n_demoted"] += r["n_demoted"]

print(f"\n  Category-level promotion/demotion rates (Gemma-4, v7, top-10):")
cat_rows_sorted = sorted(
    cat_stats.items(),
    key=lambda x: -(x[1]["n_promoted"] / x[1]["n_cases"] if x[1]["n_cases"] else 0)
)
for cat, stats in cat_rows_sorted:
    n = stats["n_cases"]
    if n == 0: continue
    pr = stats["n_promoted"] / n * 100
    dr = stats["n_demoted"] / n * 100
    print(f"    {cat:<35} | {stats['n_diseases']:2d} diseases | {n:4d} cases | promo={pr:5.1f}% | demo={dr:5.1f}% | net={(pr-dr):+.1f}%")

# Which confusion pairs cross category boundaries?
print("\n  Confusion pairs where LLM prefers disease from SAME category (plausible mix-up):")
for (truth, llm_pref), count in pair_counter.most_common():
    truth_cat = get_category(truth)
    llm_cat = get_category(llm_pref)
    if truth_cat == llm_cat and truth_cat != "Other":
        print(f"    [{count:2d}x] {truth[:40]:<40} → {llm_pref[:40]:<40}  [SAME: {truth_cat}]")

print("\n  Confusion pairs where LLM promotes a DIFFERENT category:")
for (truth, llm_pref), count in pair_counter.most_common():
    truth_cat = get_category(truth)
    llm_cat = get_category(llm_pref)
    if truth_cat != llm_cat and count >= 2:
        print(f"    [{count:2d}x] {truth[:40]:<40} → {llm_pref[:40]:<40}  [{truth_cat} → {llm_cat}]")


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 6: ANALYSIS OF DISEASES WITH 100% UNCHANGED RATE (LLM never changes)
# ──────────────────────────────────────────────────────────────────────────────

print("\n=== Section 6: Diseases LLM never changes ===")

# Diseases where LLM makes zero changes across all cases (fully trusts retriever)
never_changed = [r for r in disease_rows if r["n_promoted"] == 0 and r["n_demoted"] == 0 and r["n_in_window"] >= 5]
never_changed.sort(key=lambda r: -r["n_in_window"])
print(f"  Diseases with ≥5 window cases and zero changes: {len(never_changed)}")
print(f"  Top examples:")
for r in never_changed[:15]:
    print(f"    {r['disease'][:55]:<55} | n={r['n_in_window']:3d}")


# ──────────────────────────────────────────────────────────────────────────────
# SAVE OUTPUTS
# ──────────────────────────────────────────────────────────────────────────────

print("\n=== Saving outputs ===")

# 1. Per-disease promotion/demotion rates
disease_fields = ["disease", "n_in_window", "n_promoted", "n_demoted", "n_unchanged",
                  "promo_rate", "demo_rate", "net", "net_rate", "mean_promo_delta", "mean_demo_delta"]

disease_rows_full = sorted(disease_rows, key=lambda r: -r["net_rate"])
write_path = TABLE_DIR / "table_disease_promo_demo_rates.csv"
with open(write_path, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=disease_fields)
    w.writeheader()
    w.writerows(disease_rows_full)
print(f"  Saved {write_path}")

# 2. Demotion confusion pairs (all events)
confusion_fields = ["patient_id", "model", "truth_label", "llm_top1_id", "llm_top1_name", "score_gap", "n_pos_hpo", "n_neg_hpo"]
write_path = TABLE_DIR / "table_demotion_confusion_pairs.csv"
with open(write_path, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=confusion_fields)
    w.writeheader()
    w.writerows(demotion_events)
print(f"  Saved {write_path}")

# 3. Consistently demoted cases (all 3 models agree)
consistent_fields = ["patient_id", "truth_label", "llm_preferred", "score_gap", "n_pos_hpo", "n_neg_hpo"]
write_path = TABLE_DIR / "table_consistent_demotions.csv"
with open(write_path, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=consistent_fields)
    w.writeheader()
    w.writerows(consistent_demotions)
print(f"  Saved {write_path}")

# 4. Promotion events (Gemma-4)
promo_fields = ["patient_id", "truth_label", "from_rank", "score_gap", "n_pos_hpo", "n_neg_hpo"]
write_path = TABLE_DIR / "table_promotion_events.csv"
with open(write_path, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=promo_fields)
    w.writeheader()
    w.writerows(promotion_events)
print(f"  Saved {write_path}")

# 5. Category-level stats
cat_fields = ["category", "n_diseases", "n_cases", "n_promoted", "n_demoted", "promo_rate", "demo_rate", "net_rate"]
cat_out_rows = []
for cat, stats in cat_stats.items():
    n = stats["n_cases"]
    if n == 0: continue
    cat_out_rows.append({
        "category": cat,
        "n_diseases": stats["n_diseases"],
        "n_cases": n,
        "n_promoted": stats["n_promoted"],
        "n_demoted": stats["n_demoted"],
        "promo_rate": round(stats["n_promoted"] / n, 4),
        "demo_rate": round(stats["n_demoted"] / n, 4),
        "net_rate": round((stats["n_promoted"] - stats["n_demoted"]) / n, 4),
    })
cat_out_rows.sort(key=lambda r: -r["net_rate"])
write_path = TABLE_DIR / "table_disease_category_rates.csv"
with open(write_path, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=cat_fields)
    w.writeheader()
    w.writerows(cat_out_rows)
print(f"  Saved {write_path}")

print("\n=== DONE ===")
