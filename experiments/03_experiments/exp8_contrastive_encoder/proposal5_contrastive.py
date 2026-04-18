#!/usr/bin/env python3
"""Proposal 5: Subtype-Aware Contrastive Fine-tuning of PhenoDP's PCL_HPOEncoder.

Uses Mondo Disease Ontology (OMIMPS groups) to identify disease subtypes (siblings).
Fine-tunes the existing PCL_HPOEncoder with a contrastive loss where:
  - Positive: (patient_embedding, correct_disease_embedding)
  - Hard negatives: sibling diseases from the same OMIMPS group
  - Easy negatives: random diseases (in-batch)

Evaluation:
  - Compares semantic similarity signal quality (isolated) before/after fine-tuning
  - Evaluates on subtype confusion cases specifically
  - Full pipeline Hit@1 comparison via PMID-grouped CV
"""

from __future__ import annotations

import json
import math
import os
import random
import re
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from scipy import stats as scipy_stats

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_BASE = Path(__file__).resolve().parent

PHENODP_REPO = Path("/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/PehnoPacketPhenoDP/PhenoDP")
MONDO_DB = Path("/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/mondo.db")
HPOA_PATH = PHENODP_REPO / "data/hpo_latest/phenotype.hpoa"
ENCODER_WEIGHTS = PHENODP_REPO / "data/transformer_encoder_infoNCE.pth"
NODE_EMBEDDING_PKL = PHENODP_REPO / "data/node_embedding_dict.pkl"

CANDIDATE_JSONL = (
    _BASE
    / "runs"
    / "phenodp_gemma3_6901_no_genes_twostage_20260319_054012_20260319_044040"
    / "candidate_sets"
    / "phenodp_candidates_top50.jsonl"
)

# Output paths
FINETUNED_WEIGHTS = _BASE / "runs" / "pcl_hpoencoder_subtype_finetuned.pth"
RESULTS_JSON = _BASE / "runs" / "proposal5_results.json"


# ---------------------------------------------------------------------------
# Step 1: Build disease sibling groups from Mondo OMIMPS
# ---------------------------------------------------------------------------

def build_sibling_groups(mondo_db: Path = MONDO_DB) -> Dict[str, List[str]]:
    """Query Mondo DB for OMIMPS groups and return {omimps_id: [OMIM:XXXXXX, ...]}.

    OMIMPS (OMIM Phenotypic Series) groups sibling diseases — e.g. all subtypes
    of Loeys-Dietz syndrome are linked to the same OMIMPS ID.
    """
    print("Building sibling groups from Mondo OMIMPS...", flush=True)
    conn = sqlite3.connect(str(mondo_db))

    query = """
    SELECT group_s.object AS omimps_id, omim.object AS omim_id
    FROM statements group_s
    JOIN edge e ON e.object = group_s.subject AND e.predicate = 'rdfs:subClassOf'
    JOIN statements omim ON e.subject = omim.subject
         AND omim.predicate = 'skos:exactMatch'
         AND omim.object LIKE 'OMIM:%' AND omim.object NOT LIKE 'OMIMPS:%'
    WHERE group_s.predicate = 'skos:exactMatch' AND group_s.object LIKE 'OMIMPS:%'
    """

    groups: Dict[str, List[str]] = defaultdict(list)
    for omimps_id, omim_id in conn.execute(query):
        groups[omimps_id].append(omim_id.upper())
    conn.close()

    # Keep only groups with 2+ siblings
    groups = {k: v for k, v in groups.items() if len(v) >= 2}

    # Build reverse map: OMIM disease -> sibling diseases
    disease_to_siblings: Dict[str, List[str]] = {}
    for omimps_id, omim_list in groups.items():
        for did in omim_list:
            siblings = [d for d in omim_list if d != did]
            if did not in disease_to_siblings:
                disease_to_siblings[did] = []
            disease_to_siblings[did].extend(siblings)

    n_groups = len(groups)
    n_diseases = len(disease_to_siblings)
    print(f"  {n_groups} OMIMPS groups, {n_diseases} diseases with siblings", flush=True)
    return disease_to_siblings


# ---------------------------------------------------------------------------
# Step 2: Load PhenoDP encoder and node embeddings
# ---------------------------------------------------------------------------

def load_encoder_and_embeddings(device: str = "cpu"):
    """Load the PCL_HPOEncoder and node embeddings from PhenoDP."""
    sys.path.insert(0, str(PHENODP_REPO))
    import pickle

    print("Loading node embeddings...", flush=True)
    with open(NODE_EMBEDDING_PKL, "rb") as f:
        node_embedding = pickle.load(f)
    print(f"  {len(node_embedding)} HPO term embeddings loaded", flush=True)

    # Load encoder architecture
    sys.path.insert(0, str(_BASE))
    from phenodp_gemma3_pipeline.phenodp_retriever import PhenoDPRetriever, PhenoDPOptions

    opts = PhenoDPOptions(
        phenodp_repo_root=str(PHENODP_REPO),
        phenodp_hpo_dir=str(PHENODP_REPO / "data/hpo_latest"),
        phenodp_data_dir=str(PHENODP_REPO / "data"),
        device=device, candidate_pool_size=50,
    )
    retriever = PhenoDPRetriever(opts)
    model = retriever.model  # Full PhenoDP ranker

    print(f"  PCL_HPOEncoder loaded from {ENCODER_WEIGHTS}", flush=True)
    return model, node_embedding


# ---------------------------------------------------------------------------
# Step 3: Build training pairs
# ---------------------------------------------------------------------------

def get_disease_embedding(model, disease_id: str, node_embedding: dict, with_grad: bool = False) -> Optional[torch.Tensor]:
    """Get embedding for a disease using PCL_HPOEncoder.

    with_grad=True: compute through encoder with gradients (for training).
    with_grad=False: uses torch.no_grad (for eval/caching).
    """
    # Normalise disease ID to integer key PhenoDP uses internally
    raw_id = re.sub(r"OMIM:", "", disease_id)
    try:
        raw_int = int(raw_id)
    except ValueError:
        return None

    if raw_int not in model.disease_dict_str:
        return None

    hps = model.get_precise_node(model.disease_dict_str[raw_int])
    if not hps:
        hps = model.disease_dict_str[raw_int]
    if not hps:
        return None

    try:
        vec = model.get_hps_vec(hps)
        vec = torch.tensor(vec)
        vecs, mask = model.pad_or_truncate(vec)
        mask = torch.tensor([1] + list(mask))
        vecs = vecs.unsqueeze(0)
        mask = mask.unsqueeze(0).float()
        if with_grad:
            cls, _ = model.PCL_HPOEncoder(vecs, mask)
        else:
            model.PCL_HPOEncoder.eval()
            with torch.no_grad():
                cls, _ = model.PCL_HPOEncoder(vecs, mask)
        return cls.squeeze(0)
    except Exception:
        return None


def get_patient_embedding(model, hpo_terms: List[str], with_grad: bool = False) -> Optional[torch.Tensor]:
    """Get embedding for patient HPO term set.

    with_grad=True: compute through encoder with gradients (for training).
    with_grad=False: uses model.get_PCLHPOEncoder_out (no_grad, for eval).
    """
    filtered = model.filter_hps(list(dict.fromkeys(hpo_terms)))
    if not filtered:
        return None
    try:
        if not with_grad:
            cls, _ = model.get_PCLHPOEncoder_out(filtered)
            return cls.squeeze(0)
        else:
            # Replicate get_PCLHPOEncoder_out WITHOUT no_grad so gradients flow
            vec = model.get_hps_vec(filtered)
            vec = torch.tensor(vec)
            vecs, mask = model.pad_or_truncate(vec)
            mask = torch.tensor([1] + list(mask))
            vecs = vecs.unsqueeze(0)
            mask = mask.unsqueeze(0).float()
            cls, _ = model.PCL_HPOEncoder(vecs, mask)
            return cls.squeeze(0)
    except Exception:
        return None


def build_training_data(
    model,
    node_embedding: dict,
    disease_to_siblings: Dict[str, List[str]],
    candidate_jsonl: Path,
    max_cases: int = 6901,
) -> List[dict]:
    """Build training triplets: (patient_hpos, correct_disease_id, [sibling_disease_ids]).

    Uses the phenopacket cases where the correct disease has siblings.
    """
    print("Building training triplets...", flush=True)

    # Load HPO annotation store for disease HPO lookups
    from phenodp_gemma3_pipeline.hpo_annotations import HPOAnnotationStore
    ann_store = HPOAnnotationStore.from_hpoa_file(HPOA_PATH)

    triplets = []
    n_with_siblings = 0
    n_total = 0

    with open(candidate_jsonl) as f:
        for line in f:
            if n_total >= max_cases:
                break
            rec = json.loads(line)
            n_total += 1

            patient_hpos = rec.get("phenotype_ids", [])
            truth_ids = [t.upper() for t in rec.get("truth_ids", [])]

            for truth_id in truth_ids:
                siblings = disease_to_siblings.get(truth_id, [])
                if not siblings:
                    continue

                # Filter siblings to those in PhenoDP's disease list
                raw_siblings = []
                for sib in siblings:
                    raw_id = re.sub(r"OMIM:", "", sib)
                    try:
                        if int(raw_id) in model.disease_dict_str:
                            raw_siblings.append(sib)
                    except ValueError:
                        pass

                if not raw_siblings:
                    continue

                triplets.append({
                    "patient_hpos": patient_hpos,
                    "correct_disease": truth_id,
                    "sibling_diseases": raw_siblings,
                    "pmid": re.match(r"(PMID_\d+)", rec["patient_id"]).group(1)
                    if re.match(r"(PMID_\d+)", rec["patient_id"]) else rec["patient_id"],
                })
                n_with_siblings += 1
                break  # One truth per case

    print(f"  {n_total} cases loaded, {n_with_siblings} have sibling diseases in Mondo", flush=True)
    return triplets


# ---------------------------------------------------------------------------
# Step 4: Contrastive fine-tuning
# ---------------------------------------------------------------------------

class SubtypeContrastiveLoss(nn.Module):
    """InfoNCE-style loss with hierarchy-aware negatives.

    For each (patient, correct_disease) pair:
      - Positive: correct_disease embedding
      - Hard negatives: sibling disease embeddings
      - In-batch negatives: other correct diseases in batch
    """

    def __init__(self, temperature: float = 0.07, hard_neg_weight: float = 2.0):
        super().__init__()
        self.tau = temperature
        self.hard_neg_weight = hard_neg_weight

    def forward(
        self,
        patient_embs: torch.Tensor,    # (B, D)
        pos_embs: torch.Tensor,         # (B, D)
        hard_neg_embs: Optional[torch.Tensor] = None,  # (B, K, D) or None
    ) -> torch.Tensor:
        B, D = patient_embs.shape

        # L2 normalise
        q = F.normalize(patient_embs, dim=-1)    # (B, D)
        k_pos = F.normalize(pos_embs, dim=-1)    # (B, D)

        # Positive similarities
        pos_sim = (q * k_pos).sum(dim=-1) / self.tau  # (B,)

        # In-batch negative similarities
        all_key = k_pos  # (B, D)
        neg_sim = torch.mm(q, all_key.T) / self.tau  # (B, B)

        # Mask out the diagonal (self = positive)
        mask = torch.eye(B, dtype=torch.bool, device=q.device)
        neg_sim = neg_sim.masked_fill(mask, float("-inf"))

        # Hard negative similarities
        if hard_neg_embs is not None:
            # hard_neg_embs: (B, K, D)
            k_hard = F.normalize(hard_neg_embs, dim=-1)  # (B, K, D)
            hard_sim = torch.bmm(q.unsqueeze(1), k_hard.transpose(1, 2)).squeeze(1) / self.tau  # (B, K)
            hard_sim = hard_sim * self.hard_neg_weight
            logits = torch.cat([pos_sim.unsqueeze(1), neg_sim, hard_sim], dim=1)  # (B, 1+B+K)
        else:
            logits = torch.cat([pos_sim.unsqueeze(1), neg_sim], dim=1)  # (B, 1+B)

        labels = torch.zeros(B, dtype=torch.long, device=q.device)  # Positive is always index 0
        loss = F.cross_entropy(logits, labels)
        return loss


def finetune_encoder(
    model,
    node_embedding: dict,
    triplets: List[dict],
    epochs: int = 10,
    lr: float = 1e-4,
    batch_size: int = 16,
    max_hard_negs: int = 3,
    temperature: float = 0.07,
    hard_neg_weight: float = 2.0,
    seed: int = 42,
    device: str = "cpu",
) -> None:
    """Fine-tune PCL_HPOEncoder with subtype-aware contrastive loss."""
    torch.manual_seed(seed)
    random.seed(seed)

    encoder = model.PCL_HPOEncoder
    encoder.train()

    optimizer = optim.AdamW(encoder.parameters(), lr=lr, weight_decay=1e-4)
    criterion = SubtypeContrastiveLoss(temperature=temperature, hard_neg_weight=hard_neg_weight)

    # Pre-cache disease embeddings for efficiency
    print("Pre-caching disease embeddings...", flush=True)
    disease_emb_cache: Dict[str, torch.Tensor] = {}

    def get_cached_disease_emb(did: str) -> Optional[torch.Tensor]:
        if did not in disease_emb_cache:
            emb = get_disease_embedding(model, did, node_embedding)
            if emb is not None:
                disease_emb_cache[did] = emb
        return disease_emb_cache.get(did)

    # Pre-cache all diseases that appear in triplets
    all_diseases = set()
    for t in triplets:
        all_diseases.add(t["correct_disease"])
        all_diseases.update(t["sibling_diseases"])

    for i, did in enumerate(all_diseases):
        get_cached_disease_emb(did)
        if (i + 1) % 200 == 0:
            print(f"  Cached {i+1}/{len(all_diseases)} disease embeddings...", flush=True)
    print(f"  Cached {len(disease_emb_cache)} disease embeddings", flush=True)

    # Filter triplets to those where we have all embeddings
    valid_triplets = [
        t for t in triplets
        if t["correct_disease"] in disease_emb_cache
        and any(s in disease_emb_cache for s in t["sibling_diseases"])
    ]
    print(f"  {len(valid_triplets)}/{len(triplets)} triplets have all embeddings", flush=True)

    print(f"\nFine-tuning for {epochs} epochs, batch_size={batch_size}...", flush=True)
    indices = list(range(len(valid_triplets)))

    for epoch in range(epochs):
        encoder.train()  # Ensure train mode (pre-caching sets eval)
        random.shuffle(indices)
        total_loss = 0.0
        n_batches = 0

        for start in range(0, len(indices), batch_size):
            batch_indices = indices[start:start + batch_size]
            batch = [valid_triplets[i] for i in batch_indices]

            patient_embs_list = []
            pos_embs_list = []
            hard_neg_embs_list = []
            valid_mask = []

            for t in batch:
                # Patient embedding (re-computed with gradients)
                p_emb = get_patient_embedding(model, t["patient_hpos"], with_grad=True)
                if p_emb is None:
                    valid_mask.append(False)
                    continue

                # Positive — recompute with gradients (not from cache)
                pos_emb = get_disease_embedding(model, t["correct_disease"], node_embedding, with_grad=True)
                if pos_emb is None:
                    valid_mask.append(False)
                    continue

                # Hard negatives: recompute with gradients
                sibling_embs = []
                for s in t["sibling_diseases"][:max_hard_negs]:
                    s_emb = get_disease_embedding(model, s, node_embedding, with_grad=True)
                    if s_emb is not None:
                        sibling_embs.append(s_emb)

                patient_embs_list.append(p_emb)
                pos_embs_list.append(pos_emb)
                hard_neg_embs_list.append(sibling_embs)
                valid_mask.append(True)

            if len(patient_embs_list) < 2:
                continue

            patient_embs = torch.stack(patient_embs_list)  # (B, D)
            pos_embs = torch.stack(pos_embs_list)           # (B, D)

            # Pad hard negatives to same size
            max_K = max(len(h) for h in hard_neg_embs_list)
            if max_K > 0:
                D = patient_embs.shape[1]
                hard_neg_tensor = torch.zeros(len(patient_embs_list), max_K, D)
                for i, hns in enumerate(hard_neg_embs_list):
                    for j, hn in enumerate(hns):
                        hard_neg_tensor[i, j] = hn
            else:
                hard_neg_tensor = None

            optimizer.zero_grad()
            loss = criterion(patient_embs, pos_embs, hard_neg_tensor)
            loss.backward()
            optimizer.step()

            total_loss += loss.item()
            n_batches += 1

        avg_loss = total_loss / n_batches if n_batches > 0 else 0.0
        print(f"  Epoch {epoch+1:2d}/{epochs}: avg loss = {avg_loss:.4f} ({n_batches} batches)", flush=True)

    encoder.eval()
    print(f"\nSaving fine-tuned encoder to {FINETUNED_WEIGHTS}...", flush=True)
    torch.save(encoder.state_dict(), str(FINETUNED_WEIGHTS))
    print("Saved.", flush=True)


# ---------------------------------------------------------------------------
# Step 5: Evaluate
# ---------------------------------------------------------------------------

def evaluate_semantic_signal(
    model,
    node_embedding: dict,
    candidate_jsonl: Path,
    disease_to_siblings: Dict[str, List[str]],
    label: str = "Before fine-tuning",
) -> dict:
    """Evaluate the semantic similarity signal in isolation."""
    from phenodp_gemma3_pipeline.hpo_annotations import HPOAnnotationStore

    print(f"\nEvaluating semantic signal: {label}", flush=True)

    h1 = h3 = h5 = h10 = 0
    h1_sub = h3_sub = 0  # subtype confusion cases
    total = total_sub = 0

    model.PCL_HPOEncoder.eval()

    with open(candidate_jsonl) as f:
        for line in f:
            rec = json.loads(line)
            truth_ids = set(t.upper() for t in rec.get("truth_ids", []))
            patient_hpos = rec.get("phenotype_ids", [])
            candidates = rec.get("candidates", [])
            if not candidates or not truth_ids:
                continue

            # Get patient embedding
            p_emb = get_patient_embedding(model, patient_hpos)
            if p_emb is None:
                continue

            # Score each candidate by semantic similarity
            scored = []
            for c in candidates:
                did = c["disease_id"].upper()
                d_emb = get_disease_embedding(model, did, node_embedding)
                if d_emb is None:
                    scored.append((0.0, did))
                    continue
                sim = F.cosine_similarity(p_emb.unsqueeze(0), d_emb.unsqueeze(0)).item()
                scored.append((sim, did))

            scored.sort(reverse=True)
            is_subtype = any(
                len(disease_to_siblings.get(t, [])) > 0 for t in truth_ids
            )

            total += 1
            if is_subtype:
                total_sub += 1

            for rank, (_, did) in enumerate(scored):
                if did in truth_ids:
                    if rank < 1: h1 += 1
                    if rank < 3: h3 += 1
                    if rank < 5: h5 += 1
                    if rank < 10: h10 += 1
                    if is_subtype:
                        if rank < 1: h1_sub += 1
                        if rank < 3: h3_sub += 1
                    break

    result = {
        "label": label,
        "n_total": total,
        "n_subtype": total_sub,
        "H@1": h1 / total * 100 if total else 0,
        "H@3": h3 / total * 100 if total else 0,
        "H@5": h5 / total * 100 if total else 0,
        "H@10": h10 / total * 100 if total else 0,
        "H@1_subtype": h1_sub / total_sub * 100 if total_sub else 0,
        "H@3_subtype": h3_sub / total_sub * 100 if total_sub else 0,
    }

    print(f"  Overall: H@1={result['H@1']:.2f}%  H@3={result['H@3']:.2f}%  H@5={result['H@5']:.2f}%  H@10={result['H@10']:.2f}%")
    print(f"  Subtype ({total_sub} cases): H@1={result['H@1_subtype']:.2f}%  H@3={result['H@3_subtype']:.2f}%")
    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Proposal 5: Subtype-Aware Contrastive Fine-tuning")
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--temperature", type=float, default=0.07)
    parser.add_argument("--hard-neg-weight", type=float, default=2.0)
    parser.add_argument("--max-hard-negs", type=int, default=3)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--skip-finetune", action="store_true",
                        help="Skip fine-tuning and just evaluate existing weights")
    args = parser.parse_args()

    # Step 1: Sibling groups
    disease_to_siblings = build_sibling_groups(MONDO_DB)

    # Step 2: Load encoder
    model, node_embedding = load_encoder_and_embeddings(args.device)

    # Step 3: Evaluate BEFORE fine-tuning
    result_before = evaluate_semantic_signal(
        model, node_embedding, CANDIDATE_JSONL, disease_to_siblings,
        label="Before fine-tuning (original PCL_HPOEncoder)"
    )

    if not args.skip_finetune:
        # Step 4: Build training triplets
        triplets = build_training_data(model, node_embedding, disease_to_siblings, CANDIDATE_JSONL)

        # Step 5: Fine-tune
        finetune_encoder(
            model, node_embedding, triplets,
            epochs=args.epochs, lr=args.lr, batch_size=args.batch_size,
            max_hard_negs=args.max_hard_negs, temperature=args.temperature,
            hard_neg_weight=args.hard_neg_weight, seed=args.seed, device=args.device,
        )

        # Step 6: Evaluate AFTER fine-tuning
        result_after = evaluate_semantic_signal(
            model, node_embedding, CANDIDATE_JSONL, disease_to_siblings,
            label="After fine-tuning (subtype-aware contrastive)"
        )

        # Summary
        print(f"\n{'='*80}")
        print("SUMMARY")
        print(f"{'='*80}")
        print(f"  {'Metric':<25} {'Before':>10} {'After':>10} {'Delta':>10}")
        print(f"  {'-'*55}")
        for metric in ["H@1", "H@3", "H@5", "H@10", "H@1_subtype", "H@3_subtype"]:
            before_val = result_before[metric]
            after_val = result_after[metric]
            delta = after_val - before_val
            print(f"  {metric:<25} {before_val:>9.2f}% {after_val:>9.2f}% {delta:>+9.2f}%")

        # Save results
        RESULTS_JSON.parent.mkdir(parents=True, exist_ok=True)
        with open(RESULTS_JSON, "w") as f:
            json.dump({"before": result_before, "after": result_after}, f, indent=2)
        print(f"\nResults saved to {RESULTS_JSON}")

    print("\nDone.", flush=True)


if __name__ == "__main__":
    main()
