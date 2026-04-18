#!/usr/bin/env python3
"""Analyze why z-score PR rescoring hurts on HMS dataset."""

import sys, os, re, numpy as np
from collections import Counter

sys.path.insert(0, ".")
from phenodp_gemma3_pipeline.hpo_annotations import HPOAnnotationStore
from phenodp_gemma3_pipeline.phenodp_retriever import PhenoDPRetriever, PhenoDPOptions
from datasets import load_dataset

PHENODP_REPO = "/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/PehnoPacketPhenoDP/PhenoDP"
HPOA_PATH = os.path.join(PHENODP_REPO, "data/hpo_latest/phenotype.hpoa")

print("Loading...", flush=True)
ann_store = HPOAnnotationStore.from_hpoa_file(HPOA_PATH)
disease_hpos_cache = {}
def get_disease_hpos(disease_id):
    if disease_id not in disease_hpos_cache:
        anns = ann_store.get_annotations(disease_id)
        disease_hpos_cache[disease_id] = set(a.hpo_id for a in anns)
    return disease_hpos_cache[disease_id]

opts = PhenoDPOptions(
    phenodp_repo_root=PHENODP_REPO,
    phenodp_hpo_dir=os.path.join(PHENODP_REPO, "data/hpo_latest"),
    phenodp_data_dir=os.path.join(PHENODP_REPO, "data"),
    device="cpu",
    candidate_pool_size=50,
)
retriever = PhenoDPRetriever(opts)

def normalize_omim(did):
    did = did.strip()
    if did.startswith("OMIM:"):
        return did.upper()
    m = re.match(r"(\d{6})", did)
    if m:
        return f"OMIM:{m.group(1)}"
    return did.upper()

def zs(v):
    a = np.array(v, dtype=float)
    m, s = a.mean(), a.std()
    return (a - m) / s if s > 1e-9 else np.zeros_like(a)

# Load HMS
print("Loading HMS...", flush=True)
ds = load_dataset("chenxz/RareBench", "HMS", split="test", trust_remote_code=True)

# Also load RAMEDIS for comparison
print("Loading RAMEDIS...", flush=True)
ds_ramedis = load_dataset("chenxz/RareBench", "RAMEDIS", split="test", trust_remote_code=True)

# ── Dataset characteristics ───────────────────────────────────────────
print(f"\n{'='*80}")
print("DATASET CHARACTERISTICS")
print(f"{'='*80}\n")

for name, dataset in [("HMS", ds), ("RAMEDIS", ds_ramedis)]:
    hpo_counts = [len(row["Phenotype"]) for row in dataset]
    print(f"{name}: {len(dataset)} cases")
    print(f"  HPO terms per case: min={min(hpo_counts)}, median={np.median(hpo_counts):.0f}, "
          f"max={max(hpo_counts)}, mean={np.mean(hpo_counts):.1f}")

    # Disease distribution
    diseases = []
    for row in dataset:
        for d in row["RareDisease"]:
            if "OMIM" in d.upper() or re.match(r"^\d{6}$", d.strip()):
                diseases.append(normalize_omim(d))
    disease_counts = Counter(diseases)
    print(f"  Unique OMIM diseases: {len(disease_counts)}")
    print(f"  Most common: {disease_counts.most_common(5)}")
    print()

# ── Case-by-case HMS analysis ────────────────────────────────────────
print(f"\n{'='*80}")
print("CASE-BY-CASE HMS ANALYSIS")
print(f"{'='*80}\n")

promotions = 0
demotions = 0
no_change = 0
not_found = 0
demotion_details = []
promotion_details = []

for idx, row in enumerate(ds):
    hpo_terms = row["Phenotype"]
    disease_ids = row["RareDisease"]

    omim_ids = set()
    for did in disease_ids:
        if "OMIM" in did.upper() or re.match(r"^\d{6}$", did.strip()):
            omim_ids.add(normalize_omim(did))

    if not omim_ids:
        continue

    try:
        candidates = retriever.retrieve(phenotype_ids=hpo_terms, top_k=50, precision_recall_rescoring=False)
    except:
        continue

    if not candidates:
        continue

    pos_set = set(hpo_terms)
    cands = []
    for c in candidates:
        did = c.disease_id.upper()
        dh = get_disease_hpos(did)
        ov = len(pos_set & dh)
        cands.append({
            "disease_id": did,
            "score": c.source_score if c.source_score else c.score,
            "recall": ov / len(pos_set) if pos_set else 0,
            "precision": ov / len(dh) if dh else 0,
            "ok": did in omim_ids,
        })

    # Find correct disease rank in baseline
    baseline_rank = None
    for i, c in enumerate(cands):
        if c["ok"]:
            baseline_rank = i
            break

    if baseline_rank is None:
        not_found += 1
        continue

    # Rescore
    zs_s = zs([c["score"] for c in cands])
    zs_r = zs([c["recall"] for c in cands])
    zs_p = zs([c["precision"] for c in cands])
    adjusted = zs_s + 1.0 * zs_r - 0.5 * zs_p
    ranked = sorted(zip(adjusted, range(len(cands))), reverse=True)

    rescore_rank = None
    for rank, (_, ci) in enumerate(ranked):
        if cands[ci]["ok"]:
            rescore_rank = rank
            break

    correct = cands[baseline_rank]
    n_hpo = len(hpo_terms)
    n_disease_hpo = len(get_disease_hpos(correct["disease_id"]))

    if rescore_rank < baseline_rank:
        promotions += 1
        promotion_details.append({
            "idx": idx, "n_hpo": n_hpo, "n_disease_hpo": n_disease_hpo,
            "baseline_rank": baseline_rank, "rescore_rank": rescore_rank,
            "recall": correct["recall"], "precision": correct["precision"],
            "score": correct["score"],
        })
    elif rescore_rank > baseline_rank:
        demotions += 1
        # Who took the correct disease's spot?
        usurper_ci = ranked[baseline_rank][1]
        usurper = cands[usurper_ci]
        demotion_details.append({
            "idx": idx, "n_hpo": n_hpo, "n_disease_hpo": n_disease_hpo,
            "baseline_rank": baseline_rank, "rescore_rank": rescore_rank,
            "correct_recall": correct["recall"], "correct_precision": correct["precision"],
            "correct_score": correct["score"],
            "usurper_id": usurper["disease_id"],
            "usurper_recall": usurper["recall"], "usurper_precision": usurper["precision"],
            "usurper_score": usurper["score"],
        })
    else:
        no_change += 1

print(f"Promotions: {promotions}")
print(f"Demotions: {demotions}")
print(f"No change: {no_change}")
print(f"Not found: {not_found}")
print(f"Total with correct in top-50: {promotions + demotions + no_change}")

# ── Analyze demotions ─────────────────────────────────────────────────
if demotion_details:
    print(f"\n--- DEMOTION DETAILS ({len(demotion_details)} cases) ---\n")
    for d in demotion_details:
        print(f"  Case {d['idx']}: {d['n_hpo']} HPOs, disease has {d['n_disease_hpo']} HPO annotations")
        print(f"    Baseline rank {d['baseline_rank']} -> Rescore rank {d['rescore_rank']}")
        print(f"    Correct: score={d['correct_score']:.4f}, recall={d['correct_recall']:.3f}, precision={d['correct_precision']:.3f}")
        print(f"    Usurper: {d['usurper_id']}, score={d['usurper_score']:.4f}, recall={d['usurper_recall']:.3f}, precision={d['usurper_precision']:.3f}")
        print()

    # Aggregate stats
    demo_hpo = [d["n_hpo"] for d in demotion_details]
    demo_disease_hpo = [d["n_disease_hpo"] for d in demotion_details]
    demo_recall = [d["correct_recall"] for d in demotion_details]
    demo_precision = [d["correct_precision"] for d in demotion_details]

    print(f"  Demotion stats:")
    print(f"    Patient HPO count: mean={np.mean(demo_hpo):.1f}, median={np.median(demo_hpo):.0f}")
    print(f"    Disease HPO count: mean={np.mean(demo_disease_hpo):.1f}, median={np.median(demo_disease_hpo):.0f}")
    print(f"    Correct recall: mean={np.mean(demo_recall):.3f}")
    print(f"    Correct precision: mean={np.mean(demo_precision):.3f}")

# ── Analyze promotions ────────────────────────────────────────────────
if promotion_details:
    print(f"\n--- PROMOTION DETAILS ({len(promotion_details)} cases) ---\n")
    promo_hpo = [d["n_hpo"] for d in promotion_details]
    promo_disease_hpo = [d["n_disease_hpo"] for d in promotion_details]
    promo_recall = [d["recall"] for d in promotion_details]
    promo_precision = [d["precision"] for d in promotion_details]

    print(f"  Promotion stats:")
    print(f"    Patient HPO count: mean={np.mean(promo_hpo):.1f}, median={np.median(promo_hpo):.0f}")
    print(f"    Disease HPO count: mean={np.mean(promo_disease_hpo):.1f}, median={np.median(promo_disease_hpo):.0f}")
    print(f"    Correct recall: mean={np.mean(promo_recall):.3f}")
    print(f"    Correct precision: mean={np.mean(promo_precision):.3f}")

# ── Compare HMS vs RAMEDIS demotion rates ─────────────────────────────
print(f"\n{'='*80}")
print("HPO ANNOTATION COVERAGE COMPARISON")
print(f"{'='*80}\n")

for name, dataset in [("HMS", ds), ("RAMEDIS", ds_ramedis)]:
    missing_ann = 0
    total = 0
    ann_sizes = []
    for row in dataset:
        for did in row["RareDisease"]:
            if "OMIM" in did.upper() or re.match(r"^\d{6}$", did.strip()):
                nid = normalize_omim(did)
                total += 1
                dh = get_disease_hpos(nid)
                ann_sizes.append(len(dh))
                if len(dh) == 0:
                    missing_ann += 1
    print(f"{name}:")
    print(f"  Diseases with 0 annotations: {missing_ann}/{total} ({missing_ann/total*100:.1f}%)")
    if ann_sizes:
        print(f"  Annotation size: mean={np.mean(ann_sizes):.1f}, median={np.median(ann_sizes):.0f}, "
              f"min={min(ann_sizes)}, max={max(ann_sizes)}")
    print()

print("Done.", flush=True)
