#!/usr/bin/env python3
"""External validation on RareBench (RAMEDIS, HMS, MME).

Uses the existing PhenoDPRetriever from the pipeline to run retrieval,
then compares baseline vs z-score PR rescoring.
"""

import sys, os, re, json, numpy as np
from pathlib import Path

sys.path.insert(0, ".")

from phenodp_gemma3_pipeline.hpo_annotations import HPOAnnotationStore
from phenodp_gemma3_pipeline.phenodp_retriever import PhenoDPRetriever, PhenoDPOptions
from datasets import load_dataset

# ── Config ────────────────────────────────────────────────────────────
PHENODP_REPO = "/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/PehnoPacketPhenoDP/PhenoDP"
HPOA_PATH = os.path.join(PHENODP_REPO, "data/hpo_latest/phenotype.hpoa")
TOP_K = 50

# ── Load HPO annotations ─────────────────────────────────────────────
print("Loading HPO annotations...", flush=True)
ann_store = HPOAnnotationStore.from_hpoa_file(HPOA_PATH)
disease_hpos_cache = {}
def get_disease_hpos(disease_id):
    if disease_id not in disease_hpos_cache:
        anns = ann_store.get_annotations(disease_id)
        disease_hpos_cache[disease_id] = set(a.hpo_id for a in anns)
    return disease_hpos_cache[disease_id]

# ── Load PhenoDP Retriever ────────────────────────────────────────────
print("Loading PhenoDP retriever...", flush=True)
opts = PhenoDPOptions(
    phenodp_repo_root=PHENODP_REPO,
    phenodp_hpo_dir=os.path.join(PHENODP_REPO, "data/hpo_latest"),
    phenodp_data_dir=os.path.join(PHENODP_REPO, "data"),
    device="cpu",
    candidate_pool_size=TOP_K,
)
retriever = PhenoDPRetriever(opts)
print("PhenoDP retriever loaded.", flush=True)


# ── Helpers ───────────────────────────────────────────────────────────
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


def evaluate_cases(results_list):
    """Evaluate baseline and z-score rescoring on a list of case results."""
    output = {}
    n = len(results_list)

    for method_name, use_rescore in [("Baseline", False), ("Z-score PR", True)]:
        h1 = h3 = h5 = h10 = found = 0
        for r in results_list:
            cands = r["cands"]
            if not cands:
                continue

            if use_rescore:
                zs_s = zs([c["score"] for c in cands])
                zs_r = zs([c["recall"] for c in cands])
                zs_p = zs([c["precision"] for c in cands])
                adjusted = zs_s + 1.0 * zs_r - 0.5 * zs_p
                ranked = sorted(zip(adjusted, range(len(cands))), reverse=True)
            else:
                ranked = [(0, i) for i in range(len(cands))]

            for rank, (_, ci) in enumerate(ranked):
                if cands[ci]["ok"]:
                    if rank < 1: h1 += 1
                    if rank < 3: h3 += 1
                    if rank < 5: h5 += 1
                    if rank < 10: h10 += 1
                    found += 1
                    break

        output[method_name] = {
            "h1": h1/n*100, "h3": h3/n*100,
            "h5": h5/n*100, "h10": h10/n*100,
            "found": found/n*100,
        }
    return output


# ── Run evaluation on one dataset ────────────────────────────────────
def run_dataset(ds, dataset_name):
    print(f"\n{'='*80}")
    print(f"Dataset: {dataset_name} ({len(ds)} cases)")
    print(f"{'='*80}")

    results = []
    skipped_no_omim = 0
    skipped_retrieval_fail = 0

    for idx, row in enumerate(ds):
        hpo_terms = row["Phenotype"]
        disease_ids = row["RareDisease"]

        # Filter to OMIM IDs
        omim_ids = set()
        for did in disease_ids:
            if "OMIM" in did.upper() or re.match(r"^\d{6}$", did.strip()):
                omim_ids.add(normalize_omim(did))

        if not omim_ids:
            skipped_no_omim += 1
            continue

        # Run PhenoDP retrieval (baseline, no rescoring)
        try:
            candidates = retriever.retrieve(
                phenotype_ids=hpo_terms,
                top_k=TOP_K,
                precision_recall_rescoring=False,
            )
        except Exception as e:
            skipped_retrieval_fail += 1
            continue

        if not candidates:
            skipped_retrieval_fail += 1
            continue

        # Build evaluation structure
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

        results.append({"omim_ids": omim_ids, "cands": cands})

        if (idx + 1) % 50 == 0:
            print(f"  Processed {idx + 1}/{len(ds)} cases...", flush=True)

    print(f"  Skipped: no_omim={skipped_no_omim}, retrieval_fail={skipped_retrieval_fail}")
    print(f"  Evaluating {len(results)} cases")

    metrics = evaluate_cases(results)
    for method, m in metrics.items():
        print(f"  {method}: H@1={m['h1']:.2f}%  H@3={m['h3']:.2f}%  "
              f"H@5={m['h5']:.2f}%  H@10={m['h10']:.2f}%  Found={m['found']:.2f}%")

    return results


# ── Main ──────────────────────────────────────────────────────────────
all_results = {}
for name in ["RAMEDIS", "HMS", "MME"]:
    print(f"\nLoading {name}...", flush=True)
    ds = load_dataset("chenxz/RareBench", name, split="test", trust_remote_code=True)
    all_results[name] = run_dataset(ds, name)

# ── Combined ──────────────────────────────────────────────────────────
print(f"\n{'='*80}")
print("COMBINED (RAMEDIS + HMS + MME)")
print(f"{'='*80}")

combined = []
for name in ["RAMEDIS", "HMS", "MME"]:
    combined.extend(all_results[name])

n = len(combined)
print(f"Total evaluated cases: {n}")

metrics = evaluate_cases(combined)
for method, m in metrics.items():
    print(f"  {method}: H@1={m['h1']:.2f}%  H@3={m['h3']:.2f}%  "
          f"H@5={m['h5']:.2f}%  H@10={m['h10']:.2f}%  Found={m['found']:.2f}%")

# Delta
d = metrics["Z-score PR"]["h1"] - metrics["Baseline"]["h1"]
print(f"\n  Delta H@1: {d:+.2f}%")

# Also include LIRICAL from RareBench
print(f"\n{'='*80}")
print("BONUS: LIRICAL from RareBench (may overlap with our training data)")
print(f"{'='*80}")
ds_lirical = load_dataset("chenxz/RareBench", "LIRICAL", split="test", trust_remote_code=True)
lirical_results = run_dataset(ds_lirical, "LIRICAL (RareBench)")
metrics_l = evaluate_cases(lirical_results)
for method, m in metrics_l.items():
    print(f"  {method}: H@1={m['h1']:.2f}%  H@3={m['h3']:.2f}%  "
          f"H@5={m['h5']:.2f}%  H@10={m['h10']:.2f}%  Found={m['found']:.2f}%")

print("\nDone.", flush=True)
