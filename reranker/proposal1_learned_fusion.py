#!/usr/bin/env python3
"""Proposal 1: Learned Asymmetric Signal Fusion for PhenoDP.

Two-phase pipeline:
  Phase 1  --  Extract individual PhenoDP signal scores (IC, Phi, Semantic)
               for every (patient, candidate-disease) pair by monkey-patching
               the Ranker.  Results are saved to a JSONL so this expensive
               step (~7 h) only needs to run once.

  Phase 2  --  Load decomposed signals, compute asymmetric features (recall,
               precision, log annotation count), train a ranking MLP with
               pairwise margin loss, and evaluate via PMID-grouped 5-fold
               nested cross-validation.

Usage:
    # Run Phase 1 (extract signals)  -- takes ~7 h on CPU, saves JSONL
    python proposal1_learned_fusion.py --phase 1

    # Run Phase 2 (train MLP + evaluate) -- fast, ~minutes
    python proposal1_learned_fusion.py --phase 2

    # Run both sequentially
    python proposal1_learned_fusion.py --phase both
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
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
import torch.optim as optim
from scipy import stats as scipy_stats

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_BASE = Path(__file__).resolve().parent

PHENODP_REPO_ROOT = Path(
    "/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/PehnoPacketPhenoDP/PhenoDP"
)
PHENODP_DATA_DIR = PHENODP_REPO_ROOT / "data"
PHENODP_HPO_DIR = PHENODP_REPO_ROOT / "data" / "hpo_latest"
HPOA_PATH = PHENODP_HPO_DIR / "phenotype.hpoa"

CANDIDATE_JSONL = (
    _BASE
    / "runs"
    / "phenodp_gemma3_6901_no_genes_twostage_20260319_054012_20260319_044040"
    / "candidate_sets"
    / "phenodp_candidates_top50.jsonl"
)

# Output of Phase 1
DECOMPOSED_JSONL = _BASE / "runs" / "phenodp_decomposed_signals.jsonl"

# ---------------------------------------------------------------------------
# Phase 1 -- Extract decomposed PhenoDP signals
# ---------------------------------------------------------------------------

def phase1_extract_signals(
    candidate_jsonl: Path = CANDIDATE_JSONL,
    output_jsonl: Path = DECOMPOSED_JSONL,
    top_n: int = 200,
    device: str = "cpu",
) -> None:
    """Re-run PhenoDP ranking with monkey-patched run_Ranker to capture the
    three individual signal DataFrames (IC, Phi, Semantic) before merging."""

    print("=" * 80)
    print("PHASE 1: Extracting decomposed PhenoDP signal scores")
    print("=" * 80)

    sys.path.insert(0, str(_BASE))
    from phenodp_gemma3_pipeline.phenodp_retriever import PhenoDPOptions, PhenoDPRetriever

    opts = PhenoDPOptions(
        phenodp_repo_root=str(PHENODP_REPO_ROOT),
        phenodp_data_dir=str(PHENODP_DATA_DIR),
        phenodp_hpo_dir=str(PHENODP_HPO_DIR),
        ic_type="omim",
        device=device,
        candidate_pool_size=top_n,
    )

    print("Initialising PhenoDP (this loads the ontology + embeddings)...", flush=True)
    retriever = PhenoDPRetriever(opts)
    model = retriever.model  # The PhenoDP Ranker instance

    # -- Monkey-patch: capture individual signals before merging --
    original_get_merge3 = model.get_merge3

    def run_Ranker_decomposed(given_hps: list, top_n: int = 200) -> pd.DataFrame:
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

    # -- Load candidate JSONL to get patient HPOs + truth IDs --
    print(f"Loading patient data from {candidate_jsonl} ...", flush=True)
    records: List[Dict[str, Any]] = []
    with open(candidate_jsonl) as fh:
        for line in fh:
            records.append(json.loads(line))
    print(f"  {len(records)} patients loaded.", flush=True)

    # -- Support resuming --
    output_jsonl.parent.mkdir(parents=True, exist_ok=True)
    already_done: Set[str] = set()
    if output_jsonl.exists():
        with open(output_jsonl) as fh:
            for line in fh:
                obj = json.loads(line)
                already_done.add(obj["patient_id"])
        print(f"  Resuming: {len(already_done)} patients already processed.", flush=True)

    fout = open(output_jsonl, "a")
    t0 = time.time()
    n_processed = 0

    for idx, rec in enumerate(records):
        pid = rec["patient_id"]
        if pid in already_done:
            continue

        phenotype_ids = rec.get("phenotype_ids", [])
        truth_ids = rec.get("truth_ids", [])
        truth_labels = rec.get("truth_labels", [])

        filtered_hpos = model.filter_hps(list(dict.fromkeys(phenotype_ids)))
        if not filtered_hpos:
            print(f"  [{idx+1}/{len(records)}] {pid}: no valid HPOs, skipping")
            continue

        try:
            result_df = run_Ranker_decomposed(filtered_hpos, top_n=top_n)
        except Exception as exc:
            print(f"  [{idx+1}/{len(records)}] {pid}: ERROR {exc}")
            continue

        candidates = []
        for row in result_df.itertuples(index=False):
            candidates.append({
                "disease_raw_id": str(row.Disease),
                "ic_sim": float(row.IC_Similarity),
                "phi_sim": float(row.Phi_Similarity),
                "semantic_sim": float(row.Semantic_Similarity),
                "total_sim": float(row.Total_Similarity),
            })

        out_record = {
            "patient_id": pid,
            "phenotype_ids": phenotype_ids,
            "truth_ids": truth_ids,
            "truth_labels": truth_labels,
            "candidates": candidates,
        }
        fout.write(json.dumps(out_record) + "\n")
        fout.flush()

        n_processed += 1
        elapsed = time.time() - t0
        per_case = elapsed / n_processed
        remaining = per_case * (len(records) - idx - 1)
        if n_processed % 50 == 0:
            print(
                f"  [{idx+1}/{len(records)}] {n_processed} done "
                f"({elapsed:.0f}s elapsed, ~{remaining/3600:.1f}h remaining)",
                flush=True,
            )

    fout.close()
    print(f"\nPhase 1 complete. Output: {output_jsonl}")


# ---------------------------------------------------------------------------
# Phase 2 -- Train ranking MLP + evaluate with nested CV
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
    ic_type: str = "omim",
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Load decomposed signals and compute 6-feature vectors.

    Features per (patient, disease) pair:
      0  IC_sim
      1  Phi_sim
      2  Semantic_sim
      3  Recall     = |patient_HPOs ∩ disease_HPOs| / |patient_HPOs|
      4  Precision  = |patient_HPOs ∩ disease_HPOs| / |disease_HPOs|
      5  log(|disease_HPOs| + 1)
    """
    records: List[Dict[str, Any]] = []
    patient_ids: List[str] = []

    with open(decomposed_jsonl) as fh:
        for line in fh:
            obj = json.loads(line)
            pid = obj["patient_id"]
            patient_hpos = set(obj.get("phenotype_ids", []))
            truth_ids = set(canonicalize_disease_id(t, ic_type) for t in obj.get("truth_ids", []))

            candidates = obj.get("candidates", [])
            if not candidates:
                continue

            features_list = []
            labels = []

            for cand in candidates:
                did = canonicalize_disease_id(cand["disease_raw_id"], ic_type)

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
                "patient_id": pid,
                "features": np.array(features_list, dtype=np.float32),
                "labels": np.array(labels, dtype=np.int64),
            })
            patient_ids.append(pid)

    return records, patient_ids


# ---- MLP model --------------------------------------------------------------

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


# ---- Training ---------------------------------------------------------------

def make_pairwise_samples(
    records: List[Dict[str, Any]],
    max_neg_per_pos: int = 10,
    rng: random.Random | None = None,
) -> Tuple[np.ndarray, np.ndarray]:
    if rng is None:
        rng = random.Random(42)

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


def train_mlp(
    train_records: List[Dict[str, Any]],
    input_dim: int = 6,
    epochs: int = 50,
    lr: float = 1e-3,
    margin: float = 1.0,
    batch_size: int = 512,
    max_neg_per_pos: int = 10,
    weight_decay: float = 1e-4,
    seed: int = 42,
    verbose: bool = False,
) -> RankingMLP:
    rng = random.Random(seed)
    torch.manual_seed(seed)
    np.random.seed(seed)

    pos_feats, neg_feats = make_pairwise_samples(
        train_records, max_neg_per_pos=max_neg_per_pos, rng=rng
    )
    n_pairs = len(pos_feats)
    if n_pairs == 0:
        print("  WARNING: no pairwise samples found!")
        return RankingMLP(input_dim)

    if verbose:
        print(f"  Training on {n_pairs} pairwise samples", flush=True)

    all_feats = np.concatenate([pos_feats, neg_feats], axis=0)
    feat_mean = all_feats.mean(axis=0)
    feat_std = all_feats.std(axis=0)
    feat_std[feat_std < 1e-9] = 1.0

    pos_feats_norm = (pos_feats - feat_mean) / feat_std
    neg_feats_norm = (neg_feats - feat_mean) / feat_std

    pos_tensor = torch.from_numpy(pos_feats_norm)
    neg_tensor = torch.from_numpy(neg_feats_norm)

    model = RankingMLP(input_dim)
    model.feat_mean = torch.tensor(feat_mean, dtype=torch.float32)
    model.feat_std = torch.tensor(feat_std, dtype=torch.float32)

    optimizer = optim.Adam(model.parameters(), lr=lr, weight_decay=weight_decay)
    loss_fn = nn.MarginRankingLoss(margin=margin)

    model.train()
    indices = np.arange(n_pairs)

    for epoch in range(epochs):
        np.random.shuffle(indices)
        total_loss = 0.0
        for start in range(0, n_pairs, batch_size):
            end = min(start + batch_size, n_pairs)
            batch_idx = indices[start:end]
            pos_batch = pos_tensor[batch_idx]
            neg_batch = neg_tensor[batch_idx]
            pos_scores = model(pos_batch)
            neg_scores = model(neg_batch)
            t = torch.ones(len(batch_idx))
            loss = loss_fn(pos_scores, neg_scores, t)
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            total_loss += loss.item() * len(batch_idx)

        if verbose and (epoch + 1) % 10 == 0:
            print(f"    Epoch {epoch+1:3d}/{epochs}: avg loss = {total_loss/n_pairs:.4f}", flush=True)

    model.eval()
    return model


# ---- Evaluation -------------------------------------------------------------

def score_candidates_mlp(model: RankingMLP, features: np.ndarray) -> np.ndarray:
    feat_mean = model.feat_mean.numpy()
    feat_std = model.feat_std.numpy()
    feats_norm = (features - feat_mean) / feat_std
    with torch.no_grad():
        scores = model(torch.from_numpy(feats_norm.astype(np.float32)))
    return scores.numpy()


def evaluate_records(
    model: RankingMLP,
    records: List[Dict[str, Any]],
    k_vals: Tuple[int, ...] = (1, 3, 5, 10),
) -> Dict[str, float]:
    hits = {k: 0 for k in k_vals}
    mrr_sum = 0.0
    n = 0
    for rec in records:
        n += 1  # count ALL cases; misses count as 0
        features = rec["features"]
        labels = rec["labels"]
        if labels.sum() == 0:
            continue  # truth not retrieved — miss, contributes 0 to hits
        scores = score_candidates_mlp(model, features)
        ranking = np.argsort(-scores)
        ranked_labels = labels[ranking]
        correct_positions = np.where(ranked_labels == 1)[0]
        if len(correct_positions) == 0:
            continue
        first_correct_rank = correct_positions[0]
        mrr_sum += 1.0 / (first_correct_rank + 1)
        for k in k_vals:
            if first_correct_rank < k:
                hits[k] += 1
    if n == 0:
        return {f"Hit@{k}": 0.0 for k in k_vals} | {"MRR": 0.0, "n": 0}
    result = {f"Hit@{k}": hits[k] / n * 100 for k in k_vals}
    result["MRR"] = mrr_sum / n
    result["n"] = n
    return result


def evaluate_baseline(
    records: List[Dict[str, Any]],
    k_vals: Tuple[int, ...] = (1, 3, 5, 10),
) -> Dict[str, float]:
    """Rank by PhenoDP's original Total_Similarity (IC + Phi + Semantic) / 3."""
    hits = {k: 0 for k in k_vals}
    mrr_sum = 0.0
    n = 0
    for rec in records:
        n += 1  # count ALL cases; misses count as 0
        features = rec["features"]
        labels = rec["labels"]
        if labels.sum() == 0:
            continue  # truth not retrieved — miss
        baseline_scores = features[:, 0] + features[:, 1] + features[:, 2]
        ranking = np.argsort(-baseline_scores)
        ranked_labels = labels[ranking]
        correct_positions = np.where(ranked_labels == 1)[0]
        if len(correct_positions) == 0:
            continue
        first_correct_rank = correct_positions[0]
        mrr_sum += 1.0 / (first_correct_rank + 1)
        for k in k_vals:
            if first_correct_rank < k:
                hits[k] += 1
    if n == 0:
        return {f"Hit@{k}": 0.0 for k in k_vals} | {"MRR": 0.0, "n": 0}
    result = {f"Hit@{k}": hits[k] / n * 100 for k in k_vals}
    result["MRR"] = mrr_sum / n
    result["n"] = n
    return result


def evaluate_zscore_pr(
    records: List[Dict[str, Any]],
    k_vals: Tuple[int, ...] = (1, 3, 5, 10),
) -> Dict[str, float]:
    """Z-score PR rescoring baseline: z(S) + 1.0*z(R) - 0.5*z(P) on total_sim."""
    hits = {k: 0 for k in k_vals}
    mrr_sum = 0.0
    n = 0

    def zs(v):
        a = np.array(v, dtype=float)
        m, s = a.mean(), a.std()
        return (a - m) / s if s > 1e-9 else np.zeros_like(a)

    for rec in records:
        n += 1  # count ALL cases; misses count as 0
        features = rec["features"]
        labels = rec["labels"]
        if labels.sum() == 0:
            continue  # truth not retrieved — miss
        total_sims = features[:, 0] + features[:, 1] + features[:, 2]
        recalls = features[:, 3]
        precisions = features[:, 4]
        adjusted = zs(total_sims) + 1.0 * zs(recalls) - 0.5 * zs(precisions)
        ranking = np.argsort(-adjusted)
        ranked_labels = labels[ranking]
        correct_positions = np.where(ranked_labels == 1)[0]
        if len(correct_positions) == 0:
            continue
        first_correct_rank = correct_positions[0]
        mrr_sum += 1.0 / (first_correct_rank + 1)
        for k in k_vals:
            if first_correct_rank < k:
                hits[k] += 1
    if n == 0:
        return {f"Hit@{k}": 0.0 for k in k_vals} | {"MRR": 0.0, "n": 0}
    result = {f"Hit@{k}": hits[k] / n * 100 for k in k_vals}
    result["MRR"] = mrr_sum / n
    result["n"] = n
    return result


# ---- PMID-grouped folds ----------------------------------------------------

def extract_pmid(patient_id: str) -> str:
    m = re.match(r"(PMID_\d+)", patient_id)
    return m.group(1) if m else patient_id


def build_pmid_folds(patient_ids: List[str], k: int = 5, seed: int = 42) -> List[List[int]]:
    rng = random.Random(seed)
    pmid_to_indices: Dict[str, List[int]] = defaultdict(list)
    for i, pid in enumerate(patient_ids):
        pmid_to_indices[extract_pmid(pid)].append(i)
    pmids = sorted(pmid_to_indices.keys())
    rng.shuffle(pmids)
    folds: List[List[int]] = [[] for _ in range(k)]
    for i, pmid in enumerate(pmids):
        folds[i % k].extend(pmid_to_indices[pmid])
    return folds


# ---- Phase 2 main ----------------------------------------------------------

def phase2_train_and_evaluate(
    decomposed_jsonl: Path = DECOMPOSED_JSONL,
    k_outer: int = 5,
    epochs: int = 50,
    lr: float = 1e-3,
    margin: float = 1.0,
    batch_size: int = 512,
    max_neg_per_pos: int = 10,
    weight_decay: float = 1e-4,
    seed: int = 42,
) -> None:
    print("=" * 80)
    print("PHASE 2: Learned Asymmetric Signal Fusion -- MLP Training & Evaluation")
    print("=" * 80)

    print("Loading HPO annotations...", flush=True)
    disease_hpos = load_hpo_annotations(HPOA_PATH)
    print(f"  {len(disease_hpos)} diseases with HPO annotations", flush=True)

    print(f"Building dataset from {decomposed_jsonl} ...", flush=True)
    records, patient_ids = build_dataset(decomposed_jsonl, disease_hpos)
    n_total = len(records)
    n_with_truth = sum(1 for r in records if r["labels"].sum() > 0)
    print(f"  {n_total} patients, {n_with_truth} have truth in candidates", flush=True)

    outer_folds = build_pmid_folds(patient_ids, k=k_outer, seed=seed)
    print(f"  Outer fold sizes: {[len(f) for f in outer_folds]}\n", flush=True)

    print(f"{'='*100}")
    print("NESTED 5-FOLD CV: Outer fold = held-out test, remaining = training")
    print(f"{'='*100}\n")

    k_vals = (1, 3, 5, 10)
    outer_mlp_results = []
    outer_baseline_results = []
    outer_zscore_results = []

    for outer_fi in range(k_outer):
        test_indices = outer_folds[outer_fi]
        train_indices = [j for fj in range(k_outer) if fj != outer_fi for j in outer_folds[fj]]

        test_records = [records[j] for j in test_indices]
        train_records = [records[j] for j in train_indices]

        print(f"--- Outer Fold {outer_fi} ---")
        print(f"  Train: {len(train_records)}, Test: {len(test_records)}")

        model = train_mlp(
            train_records, input_dim=6, epochs=epochs, lr=lr,
            margin=margin, batch_size=batch_size,
            max_neg_per_pos=max_neg_per_pos, weight_decay=weight_decay,
            seed=seed + outer_fi * 1000, verbose=True,
        )

        mlp_result = evaluate_records(model, test_records, k_vals=k_vals)
        baseline_result = evaluate_baseline(test_records, k_vals=k_vals)
        zscore_result = evaluate_zscore_pr(test_records, k_vals=k_vals)

        outer_mlp_results.append(mlp_result)
        outer_baseline_results.append(baseline_result)
        outer_zscore_results.append(zscore_result)

        for label, res in [("Baseline", baseline_result), ("Z-score PR", zscore_result), ("MLP", mlp_result)]:
            print(f"  {label:12s}  ", end="")
            for k in k_vals:
                print(f"H@{k}={res[f'Hit@{k}']:.2f}%  ", end="")
            print(f"MRR={res['MRR']:.4f}")
        print(f"  MLP delta H@1: {mlp_result['Hit@1'] - baseline_result['Hit@1']:+.2f}%\n", flush=True)

    # -- Summary --
    print(f"\n{'='*100}")
    print("NESTED CV SUMMARY (unbiased estimates)")
    print(f"{'='*100}\n")

    for label, results in [("Baseline", outer_baseline_results), ("Z-score PR", outer_zscore_results), ("MLP", outer_mlp_results)]:
        print(f"  {label:12s}  ", end="")
        for k in k_vals:
            vals = [r[f"Hit@{k}"] for r in results]
            print(f"H@{k}={np.mean(vals):.2f}% (±{np.std(vals):.2f})  ", end="")
        mrr_vals = [r["MRR"] for r in results]
        print(f"MRR={np.mean(mrr_vals):.4f}")

    print()
    for k in k_vals:
        mlp_vals = [r[f"Hit@{k}"] for r in outer_mlp_results]
        base_vals = [r[f"Hit@{k}"] for r in outer_baseline_results]
        print(f"  Delta H@{k:2d} (MLP vs BL): {np.mean(mlp_vals)-np.mean(base_vals):+.2f}%")

    # Paired t-tests
    print()
    for label, results in [("MLP vs BL", (outer_mlp_results, outer_baseline_results)),
                           ("MLP vs ZPR", (outer_mlp_results, outer_zscore_results))]:
        a = [r["Hit@1"] for r in results[0]]
        b = [r["Hit@1"] for r in results[1]]
        t_stat, p_val = scipy_stats.ttest_rel(a, b)
        sig = "***" if p_val < 0.001 else "**" if p_val < 0.01 else "*" if p_val < 0.05 else "ns"
        print(f"  {label} H@1: t={t_stat:.3f}, p={p_val:.4f} {sig}")

    print("\nDone.", flush=True)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Proposal 1: Learned Asymmetric Signal Fusion")
    parser.add_argument("--phase", choices=["1", "2", "both"], default="both")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--decomposed-jsonl", type=Path, default=DECOMPOSED_JSONL)
    parser.add_argument("--candidate-jsonl", type=Path, default=CANDIDATE_JSONL)
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--margin", type=float, default=1.0)
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--max-neg-per-pos", type=int, default=10)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--top-n", type=int, default=200)
    args = parser.parse_args()

    if args.phase in ("1", "both"):
        phase1_extract_signals(
            candidate_jsonl=args.candidate_jsonl,
            output_jsonl=args.decomposed_jsonl,
            top_n=args.top_n,
            device=args.device,
        )
    if args.phase in ("2", "both"):
        phase2_train_and_evaluate(
            decomposed_jsonl=args.decomposed_jsonl,
            epochs=args.epochs, lr=args.lr, margin=args.margin,
            batch_size=args.batch_size, max_neg_per_pos=args.max_neg_per_pos,
            weight_decay=args.weight_decay, seed=args.seed,
        )


if __name__ == "__main__":
    main()
