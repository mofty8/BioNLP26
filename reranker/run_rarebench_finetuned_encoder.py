#!/usr/bin/env python3
"""RareBench evaluation with fine-tuned PCL_HPOEncoder (Proposal 5).

Runs PhenoDP retriever with the subtype-aware contrastive encoder swapped in.
Tests: Original encoder vs Fine-tuned encoder (Baseline scoring only, no MLP).
"""

from __future__ import annotations

import json
import math
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Set

import numpy as np
import torch

_BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(_BASE))

PHENODP_REPO_ROOT = Path(
    "/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/PehnoPacketPhenoDP/PhenoDP"
)
PHENODP_DATA_DIR = PHENODP_REPO_ROOT / "data"
PHENODP_HPO_DIR  = PHENODP_REPO_ROOT / "data" / "hpo_latest"
FINETUNED_ENCODER = _BASE / "runs" / "pcl_hpoencoder_subtype_finetuned.pth"


def normalize_omim(did):
    did = did.strip()
    if did.upper().startswith("OMIM:"):
        return did.upper()
    m = re.match(r"(\d{6})", did)
    if m:
        return f"OMIM:{m.group(1)}"
    return did.upper()


def run_on_dataset(phenodp_model, ds, dataset_name, top_n=50):
    """Run PhenoDP retriever on a dataset, return ranked results."""

    def run_ranker(given_hps):
        candidate_disease = phenodp_model.get_all_related_diseases(given_hps)
        IC_based = phenodp_model.first_rank_disease(given_hps, candidate_disease)
        candidate_disease = IC_based.iloc[:top_n, 0].values
        Phi_based = phenodp_model.get_phi_ranks_scores(given_hps, candidate_disease)
        Semantic_based = phenodp_model.get_embedding_rank_scores3(given_hps, candidate_disease)
        merged = phenodp_model.get_merge3(IC_based, Phi_based, Semantic_based)
        merged["Total_Similarity"] = merged["Total_Similarity"] / 3.0
        return merged[["Disease", "Total_Similarity"]]

    print(f"\n{'='*70}")
    print(f"Dataset: {dataset_name} ({len(ds)} cases)")
    print(f"{'='*70}")

    results = []
    skipped = 0

    for idx, row in enumerate(ds):
        hpo_terms = row["Phenotype"]
        disease_ids = row["RareDisease"]

        omim_ids = set()
        for did in disease_ids:
            if "OMIM" in did.upper() or re.match(r"^\d{6}$", did.strip()):
                omim_ids.add(normalize_omim(did))
        if not omim_ids:
            skipped += 1
            continue

        filtered_hpos = phenodp_model.filter_hps(list(dict.fromkeys(hpo_terms)))
        if not filtered_hpos:
            skipped += 1
            continue

        try:
            df = run_ranker(filtered_hpos)
        except Exception:
            skipped += 1
            continue

        ranked = []
        for row_data in df.itertuples(index=False):
            did = str(row_data.Disease)
            if ":" not in did:
                did = f"OMIM:{did}"
            ranked.append({"disease_id": did.upper(), "ok": did.upper() in omim_ids})

        results.append(ranked)

        if (idx + 1) % 50 == 0:
            print(f"  Processed {idx+1}/{len(ds)}...", flush=True)

    print(f"  Skipped: {skipped}, Evaluated: {len(results)}")
    return results


def compute_metrics(all_results):
    k_vals = (1, 3, 5, 10)
    hits = {k: 0 for k in k_vals}
    mrr = 0.0
    n = len(all_results)
    for ranked in all_results:
        for rank, cand in enumerate(ranked):
            if cand["ok"]:
                mrr += 1.0 / (rank + 1)
                for k in k_vals:
                    if rank < k:
                        hits[k] += 1
                break
    return {f"H@{k}": hits[k] / n * 100 for k in k_vals} | {"MRR": mrr / n, "n": n}


def main():
    from datasets import load_dataset
    from phenodp_gemma3_pipeline.phenodp_retriever import PhenoDPOptions, PhenoDPRetriever

    print("Loading PhenoDP retriever...", flush=True)
    opts = PhenoDPOptions(
        phenodp_repo_root=str(PHENODP_REPO_ROOT),
        phenodp_data_dir=str(PHENODP_DATA_DIR),
        phenodp_hpo_dir=str(PHENODP_HPO_DIR),
        device="cpu",
        candidate_pool_size=50,
    )
    retriever = PhenoDPRetriever(opts)
    phenodp_model = retriever.model
    print("PhenoDP loaded.", flush=True)

    datasets_to_run = ["HMS", "MME", "LIRICAL"]
    all_orig = {}
    all_ft = {}

    for dataset_name in datasets_to_run:
        print(f"\nLoading {dataset_name}...", flush=True)
        try:
            ds = load_dataset("chenxz/RareBench", dataset_name, split="test", trust_remote_code=True)
        except Exception as e:
            print(f"  ERROR: {e}")
            continue

        # --- Original encoder ---
        print(f"\n[Original encoder]")
        results_orig = run_on_dataset(phenodp_model, ds, dataset_name)
        m = compute_metrics(results_orig)
        print(f"  H@1={m['H@1']:.2f}%  H@3={m['H@3']:.2f}%  H@5={m['H@5']:.2f}%  H@10={m['H@10']:.2f}%  MRR={m['MRR']:.4f}")
        all_orig[dataset_name] = results_orig

        # --- Fine-tuned encoder ---
        print(f"\n[Fine-tuned encoder (Proposal 5)]")
        ft_state = torch.load(str(FINETUNED_ENCODER), map_location="cpu", weights_only=True)
        phenodp_model.PCL_HPOEncoder.load_state_dict(ft_state)
        phenodp_model.PCL_HPOEncoder.eval()
        print(f"  Encoder weights swapped to fine-tuned.")

        results_ft = run_on_dataset(phenodp_model, ds, dataset_name)
        m_ft = compute_metrics(results_ft)
        print(f"  H@1={m_ft['H@1']:.2f}%  H@3={m_ft['H@3']:.2f}%  H@5={m_ft['H@5']:.2f}%  H@10={m_ft['H@10']:.2f}%  MRR={m_ft['MRR']:.4f}")
        all_ft[dataset_name] = results_ft

        delta = m_ft["H@1"] - m["H@1"]
        print(f"  Delta H@1: {delta:+.2f}%")

        # Restore original encoder for next dataset
        retriever2 = PhenoDPRetriever(opts)
        phenodp_model.PCL_HPOEncoder.load_state_dict(
            retriever2.model.PCL_HPOEncoder.state_dict()
        )
        phenodp_model.PCL_HPOEncoder.eval()
        print(f"  Original encoder restored.")

    # Combined
    print(f"\n{'='*70}")
    print("COMBINED SUMMARY")
    print(f"{'='*70}")
    print(f"{'Dataset':<12} {'Orig H@1':>10} {'FT H@1':>10} {'Delta':>8}")
    print("-" * 45)
    for name in datasets_to_run:
        if name not in all_orig:
            continue
        m_o = compute_metrics(all_orig[name])
        m_f = compute_metrics(all_ft[name])
        d = m_f["H@1"] - m_o["H@1"]
        print(f"  {name:<10} {m_o['H@1']:>10.2f}% {m_f['H@1']:>10.2f}% {d:>+7.2f}%")

    combined_orig = [r for v in all_orig.values() for r in v]
    combined_ft   = [r for v in all_ft.values()   for r in v]
    if combined_orig:
        mo = compute_metrics(combined_orig)
        mf = compute_metrics(combined_ft)
        print(f"  {'Combined':<10} {mo['H@1']:>10.2f}% {mf['H@1']:>10.2f}% {mf['H@1']-mo['H@1']:>+7.2f}%")

    print("\nDone.", flush=True)


if __name__ == "__main__":
    main()
