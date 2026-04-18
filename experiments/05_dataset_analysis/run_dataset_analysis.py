#!/usr/bin/env python3
"""Dataset distribution analysis: compare our 6,901 training cases vs RareBench.

Analyzes:
  - HPO terms per patient (count, distribution)
  - Unique diseases, disease frequency
  - HPO term overlap with training set
  - Disease overlap with training set
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

import numpy as np

_BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(_BASE))

CANDIDATE_JSONL = (
    _BASE
    / "runs"
    / "phenodp_gemma3_6901_no_genes_twostage_20260319_054012_20260319_044040"
    / "candidate_sets"
    / "phenodp_candidates_top50.jsonl"
)

PHENODP_REPO_ROOT = Path(
    "/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/PehnoPacketPhenoDP/PhenoDP"
)
HPOA_PATH = PHENODP_REPO_ROOT / "data" / "hpo_latest" / "phenotype.hpoa"


def normalize_omim(did):
    did = str(did).strip()
    if did.upper().startswith("OMIM:"):
        return did.upper()
    m = re.match(r"(\d{6})", did)
    if m:
        return f"OMIM:{m.group(1)}"
    return did.upper()


def stats(values, label):
    a = np.array(values)
    print(f"  {label}:")
    print(f"    n={len(a)}, mean={a.mean():.1f}, median={np.median(a):.1f}, "
          f"std={a.std():.1f}, min={a.min()}, max={a.max()}")
    pcts = np.percentile(a, [10, 25, 75, 90])
    print(f"    p10={pcts[0]:.1f}  p25={pcts[1]:.1f}  p75={pcts[2]:.1f}  p90={pcts[3]:.1f}")


def load_training_data():
    """Load our 6,901 training cases."""
    hpo_counts = []
    disease_ids = []
    all_hpos = set()

    with open(CANDIDATE_JSONL) as f:
        for line in f:
            rec = json.loads(line)
            hpos = rec.get("phenotype_ids", [])
            hpo_counts.append(len(hpos))
            all_hpos.update(hpos)
            for tid in rec.get("truth_ids", []):
                disease_ids.append(normalize_omim(tid))

    return hpo_counts, disease_ids, all_hpos


def load_rarebench_dataset(dataset_name):
    from datasets import load_dataset
    print(f"  Loading {dataset_name}...", flush=True)
    ds = load_dataset("chenxz/RareBench", dataset_name, split="test", trust_remote_code=True)

    hpo_counts = []
    disease_ids = []
    all_hpos = set()

    for row in ds:
        hpos = row["Phenotype"]
        hpo_counts.append(len(hpos))
        all_hpos.update(hpos)
        for did in row["RareDisease"]:
            if "OMIM" in did.upper() or re.match(r"^\d{6}$", did.strip()):
                disease_ids.append(normalize_omim(did))

    return hpo_counts, disease_ids, all_hpos


def print_section(name, hpo_counts, disease_ids, all_hpos,
                  train_hpos=None, train_diseases=None):
    print(f"\n{'='*70}")
    print(f"  {name}  ({len(hpo_counts)} cases)")
    print(f"{'='*70}")

    stats(hpo_counts, "HPO terms per patient")

    disease_counter = Counter(disease_ids)
    print(f"\n  Diseases:")
    print(f"    Unique diseases: {len(disease_counter)}")
    print(f"    Top 5 most frequent:")
    for did, cnt in disease_counter.most_common(5):
        pct = cnt / len(hpo_counts) * 100
        print(f"      {did}: {cnt} cases ({pct:.1f}%)")

    if train_hpos is not None:
        overlap_hpo = len(all_hpos & train_hpos) / len(all_hpos) * 100
        print(f"\n  HPO term overlap with training set:")
        print(f"    {len(all_hpos)} unique HPO terms, {overlap_hpo:.1f}% also in training set")

    if train_diseases is not None:
        train_disease_set = set(train_diseases)
        test_disease_set = set(disease_ids)
        overlap_dis = len(test_disease_set & train_disease_set) / len(test_disease_set) * 100
        print(f"\n  Disease overlap with training set:")
        print(f"    {len(test_disease_set)} unique diseases, {overlap_dis:.1f}% also in training set")
        unseen = test_disease_set - train_disease_set
        print(f"    {len(unseen)} diseases NOT seen during training:")
        for d in sorted(unseen)[:10]:
            print(f"      {d}")
        if len(unseen) > 10:
            print(f"      ... and {len(unseen)-10} more")


def main():
    print("Loading HPO annotations for disease coverage stats...")

    print("\nLoading training data (6,901 cases)...")
    train_hpo_counts, train_disease_ids, train_hpos = load_training_data()
    train_disease_set = set(train_disease_ids)

    print_section(
        "TRAINING SET (6,901 publication cases)",
        train_hpo_counts, train_disease_ids, train_hpos
    )

    for dataset_name in ["HMS", "MME", "LIRICAL"]:
        try:
            hpo_counts, disease_ids, all_hpos = load_rarebench_dataset(dataset_name)
            print_section(
                dataset_name,
                hpo_counts, disease_ids, all_hpos,
                train_hpos=train_hpos,
                train_diseases=train_disease_set,
            )
        except Exception as e:
            print(f"\nERROR loading {dataset_name}: {e}")

    # Side-by-side HPO count comparison
    print(f"\n{'='*70}")
    print("  SIDE-BY-SIDE: Median HPO terms per patient")
    print(f"{'='*70}")
    print(f"  Training (6,901):  {np.median(train_hpo_counts):.0f} HPO terms (mean {np.mean(train_hpo_counts):.1f})")

    print("\nDone.", flush=True)


if __name__ == "__main__":
    main()
