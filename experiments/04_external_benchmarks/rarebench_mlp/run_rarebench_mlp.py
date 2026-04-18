#!/usr/bin/env python3
"""RareBench external validation: Baseline vs Z-score PR vs MLP (Proposal 1).

Steps:
  1. Train a final MLP on ALL 6,901 cases (original encoder features from Phase 1)
  2. Run PhenoDP on RareBench cases with monkey-patched extraction (IC/Phi/Semantic)
  3. Build 6-feature vectors and re-rank with MLP
  4. Report: Baseline vs Z-score PR vs MLP on HMS, MME, LIRICAL

Optionally also tests the fine-tuned encoder from Proposal 5.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np
import pandas as pd
import torch
import torch.nn as nn

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(_BASE))

PHENODP_REPO_ROOT = Path(
    "/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/PehnoPacketPhenoDP/PhenoDP"
)
PHENODP_DATA_DIR = PHENODP_REPO_ROOT / "data"
PHENODP_HPO_DIR = PHENODP_REPO_ROOT / "data" / "hpo_latest"
HPOA_PATH = PHENODP_HPO_DIR / "phenotype.hpoa"
DECOMPOSED_JSONL = _BASE / "runs" / "phenodp_decomposed_signals.jsonl"
FINETUNED_ENCODER = _BASE / "runs" / "pcl_hpoencoder_subtype_finetuned.pth"
FINAL_MLP_PATH = _BASE / "runs" / "proposal1_final_mlp.pth"

# ---------------------------------------------------------------------------
# MLP model (same as proposal1_learned_fusion.py)
# ---------------------------------------------------------------------------

class RankingMLP(nn.Module):
    def __init__(self, input_dim: int = 6):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, 32),
            nn.ReLU(),
            nn.Linear(32, 16),
            nn.ReLU(),
            nn.Linear(16, 1),
        )
        self.register_buffer("feat_mean", torch.zeros(input_dim))
        self.register_buffer("feat_std", torch.ones(input_dim))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x).squeeze(-1)


# ---------------------------------------------------------------------------
# Step 1: Train final MLP on all 6,901 cases
# ---------------------------------------------------------------------------

def load_hpo_annotations(hpoa_path: Path = HPOA_PATH) -> Dict[str, Set[str]]:
    disease_hpos: Dict[str, Set[str]] = defaultdict(set)
    with open(hpoa_path, encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("#") or line.startswith("database_id"):
                continue
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 8:
                continue
            disease_id = parts[0].strip()
            qualifier = parts[2].strip().upper()
            hpo_id = parts[3].strip()
            aspect = parts[10].strip() if len(parts) > 10 else "P"
            if qualifier == "NOT" or aspect != "P":
                continue
            disease_hpos[disease_id].add(hpo_id)
    return dict(disease_hpos)


def canonicalize_disease_id(raw: str, ic_type: str = "omim") -> str:
    raw = str(raw).strip()
    if not raw:
        return ""
    if ":" in raw:
        return raw.upper()
    if ic_type == "omim":
        return f"OMIM:{int(raw)}"
    return raw


def build_dataset(
    decomposed_jsonl: Path,
    disease_hpos: Dict[str, Set[str]],
) -> List[Dict[str, Any]]:
    """Load decomposed signals and compute 6-feature vectors."""
    records = []
    with open(decomposed_jsonl) as fh:
        for line in fh:
            obj = json.loads(line)
            patient_hpos = set(obj.get("phenotype_ids", []))
            truth_ids = set(canonicalize_disease_id(t) for t in obj.get("truth_ids", []))

            candidates = obj.get("candidates", [])
            if not candidates:
                continue

            features_list = []
            labels = []

            for cand in candidates:
                did = canonicalize_disease_id(cand["disease_raw_id"])
                d_hpos = disease_hpos.get(did, set())
                overlap = len(patient_hpos & d_hpos)
                recall = overlap / len(patient_hpos) if patient_hpos else 0.0
                precision = overlap / len(d_hpos) if d_hpos else 0.0
                log_ann_count = math.log(len(d_hpos) + 1)

                features_list.append([
                    cand["ic_sim"], cand["phi_sim"], cand["semantic_sim"],
                    recall, precision, log_ann_count,
                ])
                labels.append(1 if did in truth_ids else 0)

            records.append({
                "features": np.array(features_list, dtype=np.float32),
                "labels": np.array(labels, dtype=np.int64),
            })
    return records


def make_pairwise_samples(records, max_neg_per_pos=10, seed=42):
    import random
    rng = random.Random(seed)
    pos_list, neg_list = [], []
    for rec in records:
        feats = rec["features"]
        labels = rec["labels"]
        pos_idxs = np.where(labels == 1)[0]
        neg_idxs = np.where(labels == 0)[0]
        if len(pos_idxs) == 0 or len(neg_idxs) == 0:
            continue
        for pi in pos_idxs:
            neg_sample = list(neg_idxs)
            if len(neg_sample) > max_neg_per_pos:
                neg_sample = rng.sample(neg_sample, max_neg_per_pos)
            for ni in neg_sample:
                pos_list.append(feats[pi])
                neg_list.append(feats[ni])
    return np.array(pos_list, dtype=np.float32), np.array(neg_list, dtype=np.float32)


def train_final_mlp(
    decomposed_jsonl: Path = DECOMPOSED_JSONL,
    save_path: Path = FINAL_MLP_PATH,
    epochs: int = 50,
    lr: float = 1e-3,
    batch_size: int = 512,
    seed: int = 42,
) -> RankingMLP:
    """Train a single MLP on all 6,901 cases and save."""
    import random
    import torch.optim as optim

    print("=" * 80)
    print("STEP 1: Train final MLP on all 6,901 cases (original encoder features)")
    print("=" * 80)

    disease_hpos = load_hpo_annotations()
    print(f"  {len(disease_hpos)} diseases with HPO annotations")

    records = build_dataset(decomposed_jsonl, disease_hpos)
    print(f"  {len(records)} patients loaded")

    pos_feats, neg_feats = make_pairwise_samples(records, seed=seed)
    n_pairs = len(pos_feats)
    print(f"  {n_pairs} pairwise training samples")

    all_feats = np.concatenate([pos_feats, neg_feats], axis=0)
    feat_mean = all_feats.mean(axis=0)
    feat_std = all_feats.std(axis=0)
    feat_std[feat_std < 1e-9] = 1.0

    pos_norm = torch.from_numpy((pos_feats - feat_mean) / feat_std)
    neg_norm = torch.from_numpy((neg_feats - feat_mean) / feat_std)

    random.seed(seed)
    torch.manual_seed(seed)
    np.random.seed(seed)

    model = RankingMLP(6)
    model.feat_mean = torch.tensor(feat_mean, dtype=torch.float32)
    model.feat_std = torch.tensor(feat_std, dtype=torch.float32)

    optimizer = optim.Adam(model.parameters(), lr=lr, weight_decay=1e-4)
    loss_fn = nn.MarginRankingLoss(margin=1.0)
    model.train()
    indices = np.arange(n_pairs)

    for epoch in range(epochs):
        np.random.shuffle(indices)
        total_loss = 0.0
        for start in range(0, n_pairs, batch_size):
            end = min(start + batch_size, n_pairs)
            batch_idx = indices[start:end]
            pos_scores = model(pos_norm[batch_idx])
            neg_scores = model(neg_norm[batch_idx])
            t = torch.ones(len(batch_idx))
            loss = loss_fn(pos_scores, neg_scores, t)
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            total_loss += loss.item() * len(batch_idx)
        if (epoch + 1) % 10 == 0:
            print(f"    Epoch {epoch+1:3d}/{epochs}: avg loss = {total_loss/n_pairs:.4f}", flush=True)

    model.eval()
    torch.save(model.state_dict(), str(save_path))
    print(f"  Saved final MLP to {save_path}")
    return model


# ---------------------------------------------------------------------------
# Step 2: Run PhenoDP on RareBench with decomposed signal extraction
# ---------------------------------------------------------------------------

def normalize_omim(did):
    did = did.strip()
    if did.startswith("OMIM:"):
        return did.upper()
    m = re.match(r"(\d{6})", did)
    if m:
        return f"OMIM:{m.group(1)}"
    return did.upper()


def run_rarebench_extraction(
    model,  # PhenoDP Ranker
    disease_hpos: Dict[str, Set[str]],
    dataset_name: str,
    ds,  # HuggingFace dataset
    top_n: int = 50,
) -> List[Dict[str, Any]]:
    """Run PhenoDP on RareBench cases, extracting decomposed signals."""

    original_get_merge3 = model.get_merge3

    def run_Ranker_decomposed(given_hps, top_n=top_n):
        candidate_disease = model.get_all_related_diseases(given_hps)
        IC_based = model.first_rank_disease(given_hps, candidate_disease)
        candidate_disease = IC_based.iloc[:top_n, 0].values
        Phi_based = model.get_phi_ranks_scores(given_hps, candidate_disease)
        Semantic_based = model.get_embedding_rank_scores3(given_hps, candidate_disease)

        merged = original_get_merge3(IC_based, Phi_based, Semantic_based)
        merged = merged.rename(columns={
            "Similarity_df": "IC_Similarity",
            "Similarity_df1": "Phi_Similarity",
            "Similarity_df2": "Semantic_Similarity",
        })
        merged["Total_Similarity"] = merged["Total_Similarity"] / 3.0
        return merged[
            ["Disease", "IC_Similarity", "Phi_Similarity", "Semantic_Similarity", "Total_Similarity"]
        ]

    print(f"\n{'='*80}")
    print(f"Dataset: {dataset_name} ({len(ds)} cases)")
    print(f"{'='*80}")

    results = []
    skipped_no_omim = 0
    skipped_fail = 0

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

        # Filter HPOs
        filtered_hpos = model.filter_hps(list(dict.fromkeys(hpo_terms)))
        if not filtered_hpos:
            skipped_fail += 1
            continue

        try:
            result_df = run_Ranker_decomposed(filtered_hpos, top_n=top_n)
        except Exception as e:
            skipped_fail += 1
            continue

        patient_hpos_set = set(hpo_terms)

        # Build feature vectors for each candidate
        candidates = []
        for row_data in result_df.itertuples(index=False):
            did_raw = str(row_data.Disease)
            did = canonicalize_disease_id(did_raw)
            d_hpos = disease_hpos.get(did, set())
            overlap = len(patient_hpos_set & d_hpos)
            recall = overlap / len(patient_hpos_set) if patient_hpos_set else 0.0
            precision = overlap / len(d_hpos) if d_hpos else 0.0
            log_ann_count = math.log(len(d_hpos) + 1)

            candidates.append({
                "disease_id": did,
                "ic_sim": float(row_data.IC_Similarity),
                "phi_sim": float(row_data.Phi_Similarity),
                "semantic_sim": float(row_data.Semantic_Similarity),
                "total_sim": float(row_data.Total_Similarity),
                "recall": recall,
                "precision": precision,
                "log_ann_count": log_ann_count,
                "ok": did in omim_ids,
            })

        results.append({"omim_ids": omim_ids, "candidates": candidates})

        if (idx + 1) % 50 == 0:
            print(f"  Processed {idx + 1}/{len(ds)} cases...", flush=True)

    print(f"  Skipped: no_omim={skipped_no_omim}, fail={skipped_fail}")
    print(f"  Evaluating {len(results)} cases")
    return results


# ---------------------------------------------------------------------------
# Step 3: Evaluate — Baseline vs Z-score PR vs MLP
# ---------------------------------------------------------------------------

def zs(v):
    a = np.array(v, dtype=float)
    m, s = a.mean(), a.std()
    return (a - m) / s if s > 1e-9 else np.zeros_like(a)


def evaluate_all_methods(
    results: List[Dict[str, Any]],
    mlp_model: RankingMLP,
) -> Dict[str, Dict[str, float]]:
    """Evaluate Baseline, Z-score PR, and MLP on extracted results."""
    n = len(results)
    methods = {
        "Baseline": {},
        "Z-score PR": {},
        "MLP": {},
    }
    k_vals = (1, 3, 5, 10)

    for method_name in methods:
        hits = {k: 0 for k in k_vals}
        mrr_sum = 0.0

        for r in results:
            cands = r["candidates"]
            if not cands:
                continue

            if method_name == "Baseline":
                # Rank by Total_Similarity (original PhenoDP score)
                scores = [c["total_sim"] for c in cands]

            elif method_name == "Z-score PR":
                # z(Total_Sim) + 1.0*z(Recall) - 0.5*z(Precision)
                zs_s = zs([c["total_sim"] for c in cands])
                zs_r = zs([c["recall"] for c in cands])
                zs_p = zs([c["precision"] for c in cands])
                scores = (zs_s + 1.0 * zs_r - 0.5 * zs_p).tolist()

            elif method_name == "MLP":
                # Build 6-feature vectors and score with MLP
                feats = np.array([
                    [c["ic_sim"], c["phi_sim"], c["semantic_sim"],
                     c["recall"], c["precision"], c["log_ann_count"]]
                    for c in cands
                ], dtype=np.float32)
                feat_mean = mlp_model.feat_mean.numpy()
                feat_std = mlp_model.feat_std.numpy()
                feats_norm = (feats - feat_mean) / feat_std
                with torch.no_grad():
                    scores = mlp_model(torch.from_numpy(feats_norm)).numpy().tolist()

            # Rank and evaluate
            ranked_indices = np.argsort(-np.array(scores))
            for rank, ci in enumerate(ranked_indices):
                if cands[ci]["ok"]:
                    mrr_sum += 1.0 / (rank + 1)
                    for k in k_vals:
                        if rank < k:
                            hits[k] += 1
                    break

        methods[method_name] = {
            f"H@{k}": hits[k] / n * 100 for k in k_vals
        }
        methods[method_name]["MRR"] = mrr_sum / n
        methods[method_name]["n"] = n

    return methods


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="RareBench external validation with MLP")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--top-n", type=int, default=50)
    parser.add_argument("--datasets", nargs="+", default=["RAMEDIS", "HMS", "MME", "LIRICAL"])
    parser.add_argument("--skip-train", action="store_true", help="Load existing MLP instead of retraining")
    args = parser.parse_args()

    from datasets import load_dataset
    from phenodp_gemma3_pipeline.phenodp_retriever import PhenoDPOptions, PhenoDPRetriever

    # --- Step 1: Train or load final MLP ---
    if args.skip_train and FINAL_MLP_PATH.exists():
        print(f"Loading pre-trained MLP from {FINAL_MLP_PATH}")
        mlp_model = RankingMLP(6)
        mlp_model.load_state_dict(torch.load(str(FINAL_MLP_PATH), weights_only=True))
        mlp_model.eval()
    else:
        mlp_model = train_final_mlp()

    # --- Step 2: Load PhenoDP ---
    print("\n" + "=" * 80)
    print("STEP 2: Load PhenoDP retriever")
    print("=" * 80)

    opts = PhenoDPOptions(
        phenodp_repo_root=str(PHENODP_REPO_ROOT),
        phenodp_data_dir=str(PHENODP_DATA_DIR),
        phenodp_hpo_dir=str(PHENODP_HPO_DIR),
        device=args.device,
        candidate_pool_size=args.top_n,
    )
    retriever = PhenoDPRetriever(opts)
    phenodp_model = retriever.model
    print("PhenoDP loaded.", flush=True)

    # Load HPO annotations for Recall/Precision computation
    disease_hpos = load_hpo_annotations()
    print(f"  {len(disease_hpos)} diseases with HPO annotations")

    # --- Step 3: Run on each RareBench dataset ---
    all_results = {}
    for dataset_name in args.datasets:
        print(f"\nLoading {dataset_name} from HuggingFace...", flush=True)
        try:
            ds = load_dataset("chenxz/RareBench", dataset_name, split="test", trust_remote_code=True)
        except Exception as e:
            print(f"  ERROR loading {dataset_name}: {e}")
            continue

        results = run_rarebench_extraction(
            phenodp_model, disease_hpos, dataset_name, ds, top_n=args.top_n
        )
        all_results[dataset_name] = results

        metrics = evaluate_all_methods(results, mlp_model)
        for method, m in metrics.items():
            print(f"  {method:15s}: H@1={m['H@1']:6.2f}%  H@3={m['H@3']:6.2f}%  "
                  f"H@5={m['H@5']:6.2f}%  H@10={m['H@10']:6.2f}%  MRR={m['MRR']:.4f}")

    # --- Step 4: Combined results ---
    if len(all_results) > 1:
        print(f"\n{'='*80}")
        print("COMBINED (all datasets)")
        print(f"{'='*80}")

        combined = []
        for name in all_results:
            combined.extend(all_results[name])

        metrics = evaluate_all_methods(combined, mlp_model)
        for method, m in metrics.items():
            print(f"  {method:15s}: H@1={m['H@1']:6.2f}%  H@3={m['H@3']:6.2f}%  "
                  f"H@5={m['H@5']:6.2f}%  H@10={m['H@10']:6.2f}%  MRR={m['MRR']:.4f}")

        d_bl = metrics["MLP"]["H@1"] - metrics["Baseline"]["H@1"]
        d_zpr = metrics["MLP"]["H@1"] - metrics["Z-score PR"]["H@1"]
        print(f"\n  MLP vs Baseline H@1: {d_bl:+.2f}%")
        print(f"  MLP vs Z-score PR H@1: {d_zpr:+.2f}%")

    print("\nDone.", flush=True)


if __name__ == "__main__":
    main()
