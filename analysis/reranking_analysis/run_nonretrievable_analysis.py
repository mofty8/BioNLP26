"""
Error analysis: characterising the non-retrievable cases.

A case is "non-retrievable" when the correct diagnosis is NOT in the PhenoDP
retriever's top-50 candidates — this is the hard ceiling of the retrieval paradigm.

Questions:
  1. What fraction of cases hit this ceiling per dataset?
  2. Do non-retrievable cases have fewer HPO terms (less signal)?
  3. Are there specific disease categories that are systematically missed?
  4. Does HPOA annotation density predict non-retrievability?
     (diseases with sparse HPO annotations in the database → harder to match)
  5. What does the retriever return instead? (wrong disease families?)
  6. Score profile: how far below the 50th candidate does the truth fall?

Datasets: PhenoPacket (primary), RareBench sub-datasets.
"""

import json
import csv
import re
from pathlib import Path
from collections import defaultdict, Counter
import statistics

ROOT       = Path("/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket")
FINAL_RUNS = ROOT / "phenodp_gemma3_candidate_ranking/runs/final_runs"
HPOA_FILE  = ROOT / "phenotype.hpoa"
OUT_DIR    = ROOT / "reranking_analysis_20260412"
TABLE_DIR  = OUT_DIR / "tables"
DATA_DIR   = OUT_DIR / "data"

PP_CAND = FINAL_RUNS / "phenodp_gemma3_v7_full_rerank_20260407_192822/candidate_sets/phenodp_candidates_top50.jsonl"
RB_CAND = FINAL_RUNS / "phenodp_gemma3_rarebench_v7_20260407_145006/candidate_sets/phenodp_candidates_top50.jsonl"

# ──────────────────────────────────────────────────────────────────────────────
# STEP 1: LOAD HPOA ANNOTATION DENSITY
# Number of distinct HPO terms annotated to each disease (OMIM IDs only)
# ──────────────────────────────────────────────────────────────────────────────

print("=== Loading HPOA annotation density ===")

hpoa_count = defaultdict(set)   # disease_id -> set of HPO IDs
with open(HPOA_FILE) as f:
    for line in f:
        if line.startswith("#") or line.startswith("database_id"):
            continue
        parts = line.rstrip("\n").split("\t")
        if len(parts) < 4:
            continue
        db_id    = parts[0].strip()   # e.g. OMIM:123456
        qual     = parts[2].strip()   # qualifier (NOT / empty)
        hpo_id   = parts[3].strip()   # HP:xxxxxxx
        aspect   = parts[10].strip() if len(parts) > 10 else ""
        if qual.upper() == "NOT":
            continue
        if aspect == "P":             # phenotypic abnormality
            hpoa_count[db_id].add(hpo_id)

# Convert to counts
hpoa_n = {did: len(hpos) for did, hpos in hpoa_count.items()}
omim_ids = [k for k in hpoa_n if k.startswith("OMIM:")]
print(f"  HPOA entries: {len(hpoa_n)} diseases, {len(omim_ids)} OMIM")
print(f"  Median OMIM annotation count: {statistics.median(hpoa_n[k] for k in omim_ids):.0f}")
print(f"  Mean OMIM annotation count:   {statistics.mean(hpoa_n[k] for k in omim_ids):.1f}")


# ──────────────────────────────────────────────────────────────────────────────
# STEP 2: CLASSIFY ALL CASES AS RETRIEVABLE / NON-RETRIEVABLE
# ──────────────────────────────────────────────────────────────────────────────

print("\n=== Classifying cases ===")

DISEASE_CAT_KEYWORDS = [
    ("Marfan / Connective tissue", ["marfan", "ectopia lentis", "ehlers-danlos", "loeys-dietz", "fibrillin", "stickler"]),
    ("Rasopathy / RAS pathway",    ["noonan", "costello", "leopard", "cardio-facio", "legius", "neurofibromatosis"]),
    ("Skeletal dysplasia",         ["skeletal", "spondyl", "chondro", "osteogenesis", "achondro", "dysostosis", "craniosynostosis"]),
    ("Cardiomyopathy / Arrhythmia",["cardiomyopathy", "arrhythmia", "brugada", "long qt", "dilated", "hypertrophic"]),
    ("Intellectual disability",    ["intellectual", "mental retarda", "cognitive", "neurodevelopment"]),
    ("Metabolic / Lysosomal",      ["gaucher", "fabry", "niemann", "pompe", "mucopolysac", "glycogen", "lysosomal",
                                    "sphingolipid", "amino acid", "organic acid", "fatty acid", "peroxisom"]),
    ("Muscular dystrophy / Myopathy", ["muscular dystrophy", "myopathy", "limb-girdle", "emery-dreifuss", "facioscapulo"]),
    ("Mitochondrial",              ["mitochondrial", "leigh", "kearns-sayre", "mito"]),
    ("Renal / Nephrotic",          ["renal", "nephrotic", "alport", "polycystic kidney", "tubular", "nephro"]),
    ("Hearing loss",               ["deafness", "hearing loss", "usher", "pendred", "waardenburg"]),
    ("Vision / Retinal",           ["retinitis", "macular", "leber congenital", "stargardt", "choroideremia", "cone"]),
    ("Immunodeficiency",           ["immunodeficiency", "agammaglobulin", "granulomatous", "wiskott", "digeorge"]),
    ("Coagulation / Haematology",  ["hemophilia", "thrombophilia", "von willebrand", "thalassemia", "sickle"]),
    ("Epilepsy / Neurological",    ["epilep", "seizure", "dravet", "angelman", "spinal muscular", "ataxia"]),
    ("Liver / Hepatic",            ["hepat", "liver", "wilson", "crigler", "gilber"]),
    ("Endocrine / Hormonal",       ["diabetes", "thyroid", "adrenal", "pituitary", "hypoparathyroid", "hypophosphat"]),
    ("Cancer predisposition",      ["lynch", "brca", "polyposis", "cowden", "gorlin", "von hippel", "retinoblastoma"]),
]

def get_category(disease_name):
    dn = disease_name.lower()
    for cat, keywords in DISEASE_CAT_KEYWORDS:
        if any(kw in dn for kw in keywords):
            return cat
    return "Other"

def classify_cases(cand_file, dataset_label):
    retrievable   = []
    non_retrievable = []

    with open(cand_file) as f:
        for line in f:
            d = json.loads(line)
            pid        = d["patient_id"]
            truth_ids  = set(d["truth_ids"])
            truth_label = (d.get("truth_labels") or ["Unknown"])[0] if d.get("truth_labels") else "Unknown"
            cands      = d["candidates"]
            n_pos_hpo  = len(d.get("phenotype_ids", []))
            n_neg_hpo  = len(d.get("negative_phenotype_ids", []))
            has_genes  = len(d.get("genes", [])) > 0

            # Retrieval rank (within top-50)
            ret_rank = None
            for i, c in enumerate(cands[:50]):
                if c["disease_id"] in truth_ids:
                    ret_rank = i + 1
                    break

            # Score of 50th candidate (upper-bound on truth score if non-retrievable)
            score_50 = cands[49]["score"] if len(cands) >= 50 else None
            score_1  = cands[0]["score"]  if cands else None

            # Primary truth OMIM ID (if any)
            truth_omim = next((t for t in truth_ids if t.startswith("OMIM:")), None)
            hpoa_ann   = hpoa_n.get(truth_omim, 0) if truth_omim else 0

            # Top-5 retrieved disease categories (what retriever surfaces)
            top5_cats = [get_category(c["disease_name"]) for c in cands[:5]]

            sub_ds = pid.split("_")[0] if "_" in pid else dataset_label

            row = {
                "patient_id":   pid,
                "dataset":      sub_ds,
                "truth_label":  truth_label,
                "truth_omim":   truth_omim,
                "retrieval_rank": ret_rank,        # None = not in top-50
                "n_pos_hpo":    n_pos_hpo,
                "n_neg_hpo":    n_neg_hpo,
                "has_genes":    has_genes,
                "score_1":      score_1,
                "score_50":     score_50,
                "hpoa_annotations": hpoa_ann,
                "truth_category":   get_category(truth_label),
                "top1_disease":     cands[0]["disease_name"] if cands else "",
                "top5_categories":  top5_cats,
            }

            if ret_rank is None:
                non_retrievable.append(row)
            else:
                retrievable.append(row)

    total = len(retrievable) + len(non_retrievable)
    print(f"  {dataset_label}: {total} cases | "
          f"retrievable={len(retrievable)} ({len(retrievable)/total*100:.1f}%) | "
          f"non-retrievable={len(non_retrievable)} ({len(non_retrievable)/total*100:.1f}%)")
    return retrievable, non_retrievable

pp_ret_cases,  pp_nonret   = classify_cases(PP_CAND, "PhenoPacket")
rb_ret_cases,  rb_nonret   = classify_cases(RB_CAND, "RareBench")

# Split RareBench by sub-dataset
rb_nonret_by_ds = defaultdict(list)
rb_ret_by_ds    = defaultdict(list)
for r in rb_nonret:
    rb_nonret_by_ds[r["dataset"]].append(r)
for r in rb_ret_cases:
    rb_ret_by_ds[r["dataset"]].append(r)
for ds in ["RAMEDIS", "HMS", "LIRICAL", "MME"]:
    nr = len(rb_nonret_by_ds[ds])
    rt = len(rb_ret_by_ds[ds])
    total = nr + rt
    print(f"    {ds}: {nr}/{total} non-retrievable ({nr/total*100:.1f}%)")


# ──────────────────────────────────────────────────────────────────────────────
# STEP 3: FEATURE COMPARISON — RETRIEVABLE vs NON-RETRIEVABLE
# ──────────────────────────────────────────────────────────────────────────────

print("\n=== Section 1: Feature comparison (PhenoPacket) ===")

def mean(lst, key):
    vals = [r[key] for r in lst if r[key] is not None]
    return statistics.mean(vals) if vals else None

def median(lst, key):
    vals = [r[key] for r in lst if r[key] is not None]
    return statistics.median(vals) if vals else None

def pct(lst, pred):
    return sum(1 for r in lst if pred(r)) / len(lst) * 100 if lst else 0

for label, group in [("Retrievable", pp_ret_cases), ("Non-retrievable", pp_nonret)]:
    n = len(group)
    print(f"\n  {label} (n={n}):")
    print(f"    Mean pos HPO:          {mean(group, 'n_pos_hpo'):.2f}")
    print(f"    Median pos HPO:        {median(group, 'n_pos_hpo'):.0f}")
    print(f"    Mean neg HPO:          {mean(group, 'n_neg_hpo'):.2f}")
    print(f"    Has genes (%):         {pct(group, lambda r: r['has_genes']):.1f}%")
    print(f"    Mean HPOA annotations: {mean(group, 'hpoa_annotations'):.1f}")
    print(f"    Median HPOA ann:       {median(group, 'hpoa_annotations'):.0f}")
    print(f"    Mean top-1 score:      {mean(group, 'score_1'):.4f}")

# HPO count bins
print("\n  Non-retrievable rate by HPO count bin (PhenoPacket):")
bins = [(1, 3), (3, 5), (5, 8), (8, 12), (12, 20), (20, 100)]
all_pp = pp_ret_cases + pp_nonret
for lo, hi in bins:
    bucket = [r for r in all_pp if lo <= r["n_pos_hpo"] < hi]
    nr     = sum(1 for r in bucket if r["retrieval_rank"] is None)
    if bucket:
        print(f"    HPO [{lo:2d},{hi:3d}):  n={len(bucket):4d} | non-ret={nr:4d} ({nr/len(bucket)*100:5.1f}%)")

# HPOA annotation density bins
print("\n  Non-retrievable rate by HPOA annotation count (PhenoPacket):")
hpoa_bins = [(0, 1), (1, 5), (5, 10), (10, 20), (20, 40), (40, 200)]
for lo, hi in hpoa_bins:
    bucket = [r for r in all_pp if lo <= r["hpoa_annotations"] < hi]
    nr     = sum(1 for r in bucket if r["retrieval_rank"] is None)
    if bucket:
        print(f"    HPOA [{lo:3d},{hi:4d}): n={len(bucket):4d} | non-ret={nr:4d} ({nr/len(bucket)*100:5.1f}%)")


# ──────────────────────────────────────────────────────────────────────────────
# STEP 4: DISEASE-LEVEL NON-RETRIEVABILITY
# ──────────────────────────────────────────────────────────────────────────────

print("\n=== Section 2: Disease-level non-retrievability (PhenoPacket) ===")

# Per-disease non-retrievability rate (diseases with ≥3 cases)
disease_nr = defaultdict(lambda: {"total": 0, "non_ret": 0, "hpoa": None})
for r in all_pp:
    label = r["truth_label"]
    disease_nr[label]["total"] += 1
    if r["retrieval_rank"] is None:
        disease_nr[label]["non_ret"] += 1
    if r["hpoa_annotations"] > 0:
        disease_nr[label]["hpoa"] = r["hpoa_annotations"]

disease_rows = []
for label, stats in disease_nr.items():
    if stats["total"] < 3:
        continue
    nr_rate = stats["non_ret"] / stats["total"]
    disease_rows.append({
        "disease": label,
        "n_cases": stats["total"],
        "n_non_ret": stats["non_ret"],
        "non_ret_rate": round(nr_rate, 4),
        "hpoa_annotations": stats["hpoa"] or 0,
        "category": get_category(label),
    })

# Sort by non_ret_rate
by_rate = sorted(disease_rows, key=lambda r: -r["non_ret_rate"])
print(f"\n  Diseases with ≥3 cases: {len(disease_rows)}")
print(f"\n  Top 20 diseases by non-retrievable rate:")
for r in by_rate[:20]:
    print(f"    {r['disease'][:50]:<50} | n={r['n_cases']:3d} | nr={r['n_non_ret']:3d} ({r['non_ret_rate']*100:5.1f}%) | hpoa={r['hpoa_annotations']:3d}")

print(f"\n  Diseases with 100% non-retrievable rate (all cases missed, ≥3 cases):")
always_missed = [r for r in disease_rows if r["non_ret_rate"] == 1.0]
always_missed.sort(key=lambda r: -r["n_cases"])
for r in always_missed[:15]:
    print(f"    {r['disease'][:55]:<55} | n={r['n_cases']:3d} | hpoa={r['hpoa_annotations']:3d}")


# ──────────────────────────────────────────────────────────────────────────────
# STEP 5: CATEGORY-LEVEL NON-RETRIEVABILITY
# ──────────────────────────────────────────────────────────────────────────────

print("\n=== Section 3: Category-level non-retrievability (PhenoPacket) ===")

cat_stats = defaultdict(lambda: {"total": 0, "non_ret": 0, "hpoa_vals": []})
for r in all_pp:
    cat = r["truth_category"]
    cat_stats[cat]["total"] += 1
    if r["retrieval_rank"] is None:
        cat_stats[cat]["non_ret"] += 1
    if r["hpoa_annotations"] > 0:
        cat_stats[cat]["hpoa_vals"].append(r["hpoa_annotations"])

cat_rows = []
for cat, s in cat_stats.items():
    if s["total"] < 5:
        continue
    nr_rate = s["non_ret"] / s["total"]
    med_hpoa = statistics.median(s["hpoa_vals"]) if s["hpoa_vals"] else 0
    cat_rows.append({
        "category": cat,
        "n_cases": s["total"],
        "n_non_ret": s["non_ret"],
        "non_ret_rate": round(nr_rate, 4),
        "median_hpoa": round(med_hpoa, 1),
    })

cat_rows.sort(key=lambda r: -r["non_ret_rate"])
print(f"\n  {'Category':<35} | {'Cases':>5} | {'NonRet':>6} | {'Rate':>6} | {'medHPOA':>7}")
print("  " + "-" * 70)
for r in cat_rows:
    print(f"  {r['category']:<35} | {r['n_cases']:5d} | {r['n_non_ret']:6d} | {r['non_ret_rate']*100:5.1f}% | {r['median_hpoa']:7.0f}")


# ──────────────────────────────────────────────────────────────────────────────
# STEP 6: WHAT DOES THE RETRIEVER SURFACE INSTEAD?
# For non-retrievable cases, what are the top-1 retrieved diseases?
# ──────────────────────────────────────────────────────────────────────────────

print("\n=== Section 4: What retriever surfaces for non-retrievable cases ===")

# For non-retrievable PhenoPacket cases: count top-1 retrieved disease categories
top1_cats_nonret = Counter(r["top1_disease"] for r in pp_nonret)
top1_cat_nonret  = Counter(get_category(r["top1_disease"]) for r in pp_nonret)

print(f"\n  Category of rank-1 candidate in non-retrievable cases (PhenoPacket):")
for cat, cnt in top1_cat_nonret.most_common(12):
    print(f"    {cat:<35} | {cnt:4d} ({cnt/len(pp_nonret)*100:.1f}%)")

print(f"\n  Most common rank-1 wrong diseases (non-retrievable cases):")
for disease, cnt in top1_cats_nonret.most_common(12):
    cat = get_category(disease)
    print(f"    [{cnt:3d}x] {disease[:50]:<50} ({cat})")


# ──────────────────────────────────────────────────────────────────────────────
# STEP 7: SCORE PROFILE — HOW FAR BELOW TOP-50 DOES TRUTH FALL?
# ──────────────────────────────────────────────────────────────────────────────

print("\n=== Section 5: Score profile ===")

# For non-retrievable cases: what is the 50th score (upper bound for truth)?
scores_50_nonret = [r["score_50"] for r in pp_nonret if r["score_50"] is not None]
scores_1_nonret  = [r["score_1"]  for r in pp_nonret if r["score_1"]  is not None]
scores_50_ret    = [r["score_50"] for r in pp_ret_cases if r["score_50"] is not None]
scores_1_ret     = [r["score_1"]  for r in pp_ret_cases if r["score_1"]  is not None]

print(f"\n  PhenoPacket score profiles:")
print(f"                      Non-retrievable   Retrievable")
print(f"  rank-1 score mean:  {statistics.mean(scores_1_nonret):.4f}            {statistics.mean(scores_1_ret):.4f}")
print(f"  rank-50 score mean: {statistics.mean(scores_50_nonret):.4f}            {statistics.mean(scores_50_ret):.4f}")
print(f"  rank-1 score med:   {statistics.median(scores_1_nonret):.4f}            {statistics.median(scores_1_ret):.4f}")
print()
print(f"  Interpretation: truth score < {statistics.mean(scores_50_nonret):.4f} for non-retrievable cases")
print(f"  Score gap (truth excluded at score < rank-50 mean)")


# ──────────────────────────────────────────────────────────────────────────────
# STEP 8: RAREBENCH — WHICH SUB-DATASET IS HARDEST AND WHY?
# ──────────────────────────────────────────────────────────────────────────────

print("\n=== Section 6: RareBench sub-dataset non-retrievability ===")

for ds in ["RAMEDIS", "HMS", "LIRICAL", "MME"]:
    nr   = rb_nonret_by_ds[ds]
    ret  = rb_ret_by_ds[ds]
    all_ = nr + ret
    if not all_:
        continue
    n_nr = len(nr)
    total = len(all_)
    print(f"\n  {ds}: {n_nr}/{total} non-retrievable ({n_nr/total*100:.1f}%)")
    if nr:
        print(f"    Mean pos HPO (non-ret): {mean(nr, 'n_pos_hpo'):.1f}")
        print(f"    Mean pos HPO (ret):     {mean(ret, 'n_pos_hpo'):.1f}")
        print(f"    Mean HPOA ann (non-ret):{mean(nr, 'hpoa_annotations'):.1f}")
        print(f"    Mean HPOA ann (ret):    {mean(ret, 'hpoa_annotations'):.1f}")

        # Top non-retrievable diseases
        nr_diseases = Counter(r["truth_label"] for r in nr)
        print(f"    Top non-retrievable diseases:")
        for disease, cnt in nr_diseases.most_common(5):
            print(f"      [{cnt:2d}x] {disease[:55]}")


# ──────────────────────────────────────────────────────────────────────────────
# SAVE OUTPUTS
# ──────────────────────────────────────────────────────────────────────────────

print("\n=== Saving outputs ===")

def write_csv(path, rows, fields):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

# 1. Per-disease non-retrievability (PhenoPacket)
write_csv(TABLE_DIR / "table_nonretrievable_by_disease.csv",
          sorted(disease_rows, key=lambda r: -r["n_non_ret"]),
          ["disease", "category", "n_cases", "n_non_ret", "non_ret_rate", "hpoa_annotations"])
print(f"  Saved table_nonretrievable_by_disease.csv")

# 2. Category-level non-retrievability
write_csv(TABLE_DIR / "table_nonretrievable_by_category.csv",
          cat_rows,
          ["category", "n_cases", "n_non_ret", "non_ret_rate", "median_hpoa"])
print(f"  Saved table_nonretrievable_by_category.csv")

# 3. Per-case non-retrievable cases (for supplementary / further analysis)
nonret_fields = ["patient_id", "dataset", "truth_label", "truth_omim",
                 "n_pos_hpo", "n_neg_hpo", "has_genes", "hpoa_annotations",
                 "truth_category", "score_1", "score_50", "top1_disease"]
write_csv(TABLE_DIR / "table_nonretrievable_cases_pp.csv",
          pp_nonret,
          nonret_fields)
print(f"  Saved table_nonretrievable_cases_pp.csv ({len(pp_nonret)} cases)")

# 4. Summary stats as JSON
summary = {
    "phenopacket": {
        "total": len(all_pp),
        "non_retrievable": len(pp_nonret),
        "non_retrievable_pct": round(len(pp_nonret)/len(all_pp)*100, 2),
        "retrievable_mean_pos_hpo":   round(mean(pp_ret_cases, "n_pos_hpo"), 2),
        "nonret_mean_pos_hpo":        round(mean(pp_nonret,    "n_pos_hpo"), 2),
        "retrievable_median_hpoa":    statistics.median(r["hpoa_annotations"] for r in pp_ret_cases),
        "nonret_median_hpoa":         statistics.median(r["hpoa_annotations"] for r in pp_nonret),
        "always_missed_diseases":     len(always_missed),
        "score_50_nonret_mean":       round(statistics.mean(scores_50_nonret), 4),
    },
    "rarebench": {
        ds: {
            "total": len(rb_ret_by_ds[ds]) + len(rb_nonret_by_ds[ds]),
            "non_retrievable": len(rb_nonret_by_ds[ds]),
            "non_retrievable_pct": round(
                len(rb_nonret_by_ds[ds]) /
                max(1, len(rb_ret_by_ds[ds]) + len(rb_nonret_by_ds[ds])) * 100, 2),
        }
        for ds in ["RAMEDIS", "HMS", "LIRICAL", "MME"]
    }
}
with open(DATA_DIR / "nonretrievable_summary.json", "w") as f:
    json.dump(summary, f, indent=2)
print(f"  Saved nonretrievable_summary.json")

print("\n=== DONE ===")
