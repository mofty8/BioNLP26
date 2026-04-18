#!/usr/bin/env python3
"""Proposal 5: Subtype-Aware Contrastive Training for PhenoDP's PCL_HPOEncoder.

Fine-tunes the existing PCL_HPOEncoder with disease-hierarchy-structured
hard negatives from OMIM Phenotypic Series (via Mondo DB or name-based
subtype extraction from phenotype.hpoa).

The key insight: PhenoDP's existing contrastive training samples random 70%
subsets of a disease's HPOs as positive pairs, with in-batch random negatives.
This teaches coarse discrimination but not fine-grained subtype separation.
We add sibling diseases (same Phenotypic Series) as explicit hard negatives.

Usage:
    # Step 1: Build sibling groups from phenotype.hpoa disease names
    python proposal5_contrastive_training.py --step build-groups

    # Step 2: Fine-tune PCL_HPOEncoder with hard negatives
    python proposal5_contrastive_training.py --step train

    # Step 3: Evaluate the fine-tuned encoder within PhenoDP's 3-signal ensemble
    python proposal5_contrastive_training.py --step evaluate

    # Run all steps
    python proposal5_contrastive_training.py --step all
"""

from __future__ import annotations

import argparse
import json
import math
import os
import pickle
import random
import re
import sqlite3
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_BASE = Path(__file__).resolve().parent

PHENODP_REPO = Path(
    "/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/PehnoPacketPhenoDP/PhenoDP"
)
PHENODP_DATA = PHENODP_REPO / "data"
PHENODP_HPO = PHENODP_DATA / "hpo_latest"
HPOA_PATH = PHENODP_HPO / "phenotype.hpoa"
MONDO_DB = Path("/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/mondo.db")

NODE_EMBEDDING_PATH = PHENODP_DATA / "node_embedding_dict.pkl"
ENCODER_WEIGHTS_PATH = PHENODP_DATA / "transformer_encoder_infoNCE.pth"

CANDIDATE_JSONL = (
    _BASE / "runs"
    / "phenodp_gemma3_6901_no_genes_twostage_20260319_054012_20260319_044040"
    / "candidate_sets" / "phenodp_candidates_top50.jsonl"
)

OUTPUT_DIR = _BASE / "runs" / "proposal5_contrastive"

# ---------------------------------------------------------------------------
# Step 1: Build sibling groups
# ---------------------------------------------------------------------------

def build_groups_from_hpoa(hpoa_path: Path) -> Dict[str, List[str]]:
    """Extract disease subtype families from disease names in phenotype.hpoa.

    Groups diseases whose names share a common stem with numbered suffixes
    (e.g., 'Loeys-Dietz syndrome 1', '... 2', '... 3').

    Returns:
        Dict mapping group_stem -> list of OMIM disease IDs
    """
    disease_names: Dict[str, str] = {}  # OMIM:XXXXXX -> name
    disease_hpos: Dict[str, Set[str]] = defaultdict(set)

    with open(hpoa_path) as f:
        for line in f:
            if line.startswith("#") or line.startswith("database_id"):
                continue
            parts = line.strip().split("\t")
            if len(parts) < 4:
                continue
            did = parts[0].strip()
            name = parts[1].strip()
            qualifier = parts[2].strip().upper()
            hpo_id = parts[3].strip()
            aspect = parts[10].strip() if len(parts) > 10 else "P"

            if not did.startswith("OMIM:"):
                continue
            if qualifier == "NOT" or aspect != "P":
                continue

            disease_names[did] = name
            disease_hpos[did].add(hpo_id)

    # Pattern: extract base name by removing trailing type/number suffixes
    # "Loeys-Dietz syndrome 4" -> "Loeys-Dietz syndrome"
    # "Ehlers-Danlos syndrome, classic type, 1" -> "Ehlers-Danlos syndrome, classic type"
    patterns = [
        r"^(.+?)\s*,?\s*type\s+\w+$",           # "..., type 1" or "... type A"
        r"^(.+?)\s+(\d+[A-Z]?)$",                 # "... 4" or "... 4A"
        r"^(.+?)\s*,\s*(\d+[A-Z]?)$",             # "..., 4"
        r"^(.+?)\s+type\s+(\d+|[IVX]+|[A-Z])$",  # "... type 2" or "... type IV"
    ]

    stem_to_diseases: Dict[str, List[str]] = defaultdict(list)
    for did, name in disease_names.items():
        if len(disease_hpos.get(did, set())) < 3:
            continue  # Skip diseases with too few annotations

        for pat in patterns:
            m = re.match(pat, name, re.IGNORECASE)
            if m:
                stem = m.group(1).strip().rstrip(",").strip().lower()
                if len(stem) > 10:  # Avoid overly short stems
                    stem_to_diseases[stem].append(did)
                break

    # Filter to groups with 2+ members
    groups = {stem: sorted(set(dids)) for stem, dids in stem_to_diseases.items()
              if len(set(dids)) >= 2}

    return groups


def build_groups_from_mondo(mondo_db: Path) -> Dict[str, List[str]]:
    """Extract sibling groups from Mondo OMIMPS (Phenotypic Series) via SQLite.

    Returns:
        Dict mapping OMIMPS_ID -> list of OMIM disease IDs
    """
    conn = sqlite3.connect(str(mondo_db))
    cur = conn.execute("""
        SELECT group_s.object AS omimps_id, omim.object AS omim_id
        FROM statements group_s
        JOIN edge e ON e.object = group_s.subject AND e.predicate = 'rdfs:subClassOf'
        JOIN statements omim ON e.subject = omim.subject
             AND omim.predicate = 'skos:exactMatch'
             AND omim.object LIKE 'OMIM:%' AND omim.object NOT LIKE 'OMIMPS:%'
        WHERE group_s.predicate = 'skos:exactMatch' AND group_s.object LIKE 'OMIMPS:%'
    """)

    groups: Dict[str, List[str]] = defaultdict(list)
    for omimps_id, omim_id in cur:
        groups[omimps_id].append(omim_id)
    conn.close()

    # Filter to groups with 2+ members
    groups = {k: sorted(set(v)) for k, v in groups.items() if len(set(v)) >= 2}
    return groups


def step_build_groups():
    """Build sibling groups and save to JSON."""
    print("=" * 80)
    print("STEP 1: Building disease sibling groups")
    print("=" * 80)

    # Try Mondo first, fall back to name-based
    if MONDO_DB.exists():
        print(f"Trying Mondo DB at {MONDO_DB}...", flush=True)
        try:
            mondo_groups = build_groups_from_mondo(MONDO_DB)
            print(f"  Mondo: {len(mondo_groups)} groups", flush=True)
        except Exception as e:
            print(f"  Mondo failed: {e}", flush=True)
            mondo_groups = {}
    else:
        mondo_groups = {}

    print(f"Building name-based groups from {HPOA_PATH}...", flush=True)
    name_groups = build_groups_from_hpoa(HPOA_PATH)
    print(f"  Name-based: {len(name_groups)} groups", flush=True)

    # Merge: prefer Mondo groups, add unique name-based groups
    # First, build OMIM->group mapping from Mondo
    mondo_omim_to_group = {}
    for gid, dids in mondo_groups.items():
        for did in dids:
            mondo_omim_to_group[did] = gid

    # Add name-based groups where diseases aren't already in Mondo groups
    merged = dict(mondo_groups)
    extra_count = 0
    for stem, dids in name_groups.items():
        # Check if any disease in this group is NOT in a Mondo group
        uncovered = [d for d in dids if d not in mondo_omim_to_group]
        if len(uncovered) >= 2:
            key = f"NAME:{stem}"
            merged[key] = dids
            extra_count += 1

    print(f"\nMerged: {len(merged)} total groups")

    # Stats
    sizes = [len(v) for v in merged.values()]
    total_diseases = sum(sizes)
    print(f"  Total diseases in groups: {total_diseases}")
    print(f"  Group sizes: min={min(sizes)}, median={np.median(sizes):.0f}, "
          f"max={max(sizes)}, mean={np.mean(sizes):.1f}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / "sibling_groups.json"
    with open(out_path, "w") as f:
        json.dump(merged, f, indent=2)
    print(f"\nSaved to {out_path}", flush=True)
    return merged


# ---------------------------------------------------------------------------
# Step 2: Fine-tune PCL_HPOEncoder with hard negatives
# ---------------------------------------------------------------------------

def load_phenodp_data():
    """Load PhenoDP's node embeddings and disease HPO mappings."""
    print("Loading node embeddings...", flush=True)
    with open(NODE_EMBEDDING_PATH, "rb") as f:
        node_embedding = pickle.load(f)
    print(f"  {len(node_embedding)} HPO term embeddings (dim={next(iter(node_embedding.values())).shape[0]})")

    # Load disease -> HPO mapping from phenotype.hpoa
    disease_hpos: Dict[str, List[str]] = defaultdict(list)
    with open(HPOA_PATH) as f:
        for line in f:
            if line.startswith("#") or line.startswith("database_id"):
                continue
            parts = line.strip().split("\t")
            if len(parts) < 4:
                continue
            did = parts[0].strip()
            qualifier = parts[2].strip().upper()
            hpo_id = parts[3].strip()
            aspect = parts[10].strip() if len(parts) > 10 else "P"
            if not did.startswith("OMIM:"):
                continue
            if qualifier == "NOT" or aspect != "P":
                continue
            if hpo_id not in disease_hpos[did]:
                disease_hpos[did].append(hpo_id)

    # Filter to diseases with enough HPOs and with embeddings available
    valid_diseases = {}
    for did, hpos in disease_hpos.items():
        valid_hpos = [h for h in hpos if h in node_embedding]
        if len(valid_hpos) >= 3:
            valid_diseases[did] = valid_hpos

    print(f"  {len(valid_diseases)} OMIM diseases with ≥3 embedded HPO terms")
    return node_embedding, valid_diseases


def get_hps_vec(hps, node_embedding):
    """Get embedding vectors for a list of HPO terms."""
    return np.vstack([node_embedding[h] for h in hps if h in node_embedding])


def pad_or_truncate(vec, max_len=128):
    """Pad or truncate tensor to fixed length."""
    original_length = vec.size(0)
    if original_length > max_len:
        padded_vec = vec[:max_len]
    else:
        pad_size = max_len - original_length
        padded_vec = F.pad(vec, (0, 0, 0, pad_size))
    attention_mask = torch.zeros(max_len, dtype=torch.bool)
    attention_mask[:min(original_length, max_len)] = True
    return padded_vec, attention_mask


class PCL_HPOEncoder(nn.Module):
    """Copy of PhenoDP's PCL_HPOEncoder for standalone fine-tuning."""
    def __init__(self, input_dim=256, num_heads=8, num_layers=3,
                 hidden_dim=512, dropout=0.1, output_dim=1, max_seq_length=128):
        super().__init__()
        self.cls_token = nn.Parameter(torch.zeros(1, 1, input_dim))
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=input_dim, nhead=num_heads, dim_feedforward=hidden_dim
        )
        self.transformer_encoder = nn.TransformerEncoder(encoder_layer, num_layers)
        self.dropout = nn.Dropout(p=dropout)
        self.fc1 = nn.Linear(input_dim, hidden_dim)
        self.fc2 = nn.Linear(hidden_dim, output_dim)
        self.input_dim = input_dim

    def forward(self, vec, mask):
        batch_size, seq_length, _ = vec.size()
        cls_tokens = self.cls_token.expand(batch_size, -1, -1)
        vec = torch.cat((cls_tokens, vec), dim=1)
        vec = vec.permute(1, 0, 2)
        vec = self.transformer_encoder(vec, src_key_padding_mask=mask)
        cls_embedding = vec[0]
        return cls_embedding, vec


def make_triplet_batch(
    disease_hpos: Dict[str, List[str]],
    sibling_groups: Dict[str, List[str]],
    node_embedding: dict,
    batch_size: int = 64,
    subsample_p: float = 0.7,
    rng: random.Random = None,
) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
    """Create a batch of (anchor, positive, hard_negative) triplets.

    Anchor: random 70% subset of disease D's HPOs (simulates a patient)
    Positive: another random 70% subset of the same disease D
    Hard negative: random 70% subset of a sibling disease D' (same phenotypic series)

    Returns: (anchor_vecs, anchor_masks, pos_vecs, pos_masks, neg_vecs, neg_masks)
    """
    if rng is None:
        rng = random.Random(42)

    # Build disease -> group mapping
    disease_to_siblings: Dict[str, List[str]] = {}
    for gid, dids in sibling_groups.items():
        valid_dids = [d for d in dids if d in disease_hpos]
        if len(valid_dids) >= 2:
            for d in valid_dids:
                if d not in disease_to_siblings:
                    disease_to_siblings[d] = []
                disease_to_siblings[d].extend([s for s in valid_dids if s != d])

    # Diseases that have siblings
    eligible = [d for d in disease_to_siblings if len(disease_to_siblings[d]) > 0]
    if not eligible:
        raise ValueError("No eligible diseases with sibling groups found")

    def sample_hpos(disease_id):
        hpos = disease_hpos[disease_id]
        n = max(3, int(len(hpos) * subsample_p))
        n = min(n, len(hpos))
        sampled = rng.sample(hpos, n)
        vec = torch.tensor(get_hps_vec(sampled, node_embedding), dtype=torch.float32)
        vec, mask = pad_or_truncate(vec)
        mask = torch.tensor([True] + list(mask))  # CLS token mask
        return vec, mask

    anchor_vecs, anchor_masks = [], []
    pos_vecs, pos_masks = [], []
    neg_vecs, neg_masks = [], []

    selected = rng.choices(eligible, k=batch_size)
    for d in selected:
        # Anchor and positive: two random subsets of same disease
        a_vec, a_mask = sample_hpos(d)
        p_vec, p_mask = sample_hpos(d)

        # Hard negative: random sibling disease
        sibling = rng.choice(disease_to_siblings[d])
        n_vec, n_mask = sample_hpos(sibling)

        anchor_vecs.append(a_vec)
        anchor_masks.append(a_mask)
        pos_vecs.append(p_vec)
        pos_masks.append(p_mask)
        neg_vecs.append(n_vec)
        neg_masks.append(n_mask)

    return (
        torch.stack(anchor_vecs), torch.stack(anchor_masks).float(),
        torch.stack(pos_vecs), torch.stack(pos_masks).float(),
        torch.stack(neg_vecs), torch.stack(neg_masks).float(),
    )


def triplet_loss(anchor_emb, pos_emb, neg_emb, margin=0.3):
    """Triplet loss: d(anchor, positive) < d(anchor, negative) - margin."""
    pos_dist = 1.0 - F.cosine_similarity(anchor_emb, pos_emb)
    neg_dist = 1.0 - F.cosine_similarity(anchor_emb, neg_emb)
    loss = F.relu(pos_dist - neg_dist + margin)
    return loss.mean()


def combined_loss(model, anchor_v, anchor_m, pos_v, pos_m, neg_v, neg_m,
                  temperature=0.1, triplet_margin=0.3, triplet_weight=0.5):
    """Combined InfoNCE + Triplet loss.

    InfoNCE: standard contrastive between anchor and positive (in-batch negatives)
    Triplet: explicit hard negative from sibling disease
    """
    anchor_cls, _ = model(anchor_v, anchor_m)
    pos_cls, _ = model(pos_v, pos_m)
    neg_cls, _ = model(neg_v, neg_m)

    # InfoNCE between anchor and positive
    N = anchor_cls.shape[0]
    embeddings = torch.cat([anchor_cls, pos_cls], dim=0)
    sim_matrix = F.cosine_similarity(embeddings.unsqueeze(1), embeddings.unsqueeze(0), dim=2)
    labels = torch.arange(N).repeat(2).to(anchor_cls.device)
    mask = torch.eye(2 * N, dtype=torch.bool).to(anchor_cls.device)
    sim_matrix = sim_matrix[~mask].view(2 * N, 2 * N - 1)
    infonce = F.cross_entropy(sim_matrix / temperature, labels)

    # Triplet loss with hard negatives
    trip = triplet_loss(anchor_cls, pos_cls, neg_cls, margin=triplet_margin)

    return (1 - triplet_weight) * infonce + triplet_weight * trip


def step_train(
    epochs: int = 100,
    batch_size: int = 64,
    lr: float = 5e-5,
    triplet_weight: float = 0.5,
    triplet_margin: float = 0.3,
    temperature: float = 0.1,
    seed: int = 42,
):
    """Fine-tune PCL_HPOEncoder with subtype-aware hard negatives."""
    print("=" * 80)
    print("STEP 2: Fine-tuning PCL_HPOEncoder with sibling hard negatives")
    print("=" * 80)

    rng = random.Random(seed)
    torch.manual_seed(seed)
    np.random.seed(seed)

    # Load data
    node_embedding, disease_hpos = load_phenodp_data()

    groups_path = OUTPUT_DIR / "sibling_groups.json"
    if not groups_path.exists():
        print("Sibling groups not found, building...", flush=True)
        sibling_groups = step_build_groups()
    else:
        with open(groups_path) as f:
            sibling_groups = json.load(f)
    print(f"Loaded {len(sibling_groups)} sibling groups", flush=True)

    # Load pre-trained encoder
    print("Loading pre-trained PCL_HPOEncoder...", flush=True)
    model = PCL_HPOEncoder(input_dim=256, num_heads=8, num_layers=3, hidden_dim=512)
    state_dict = torch.load(str(ENCODER_WEIGHTS_PATH), map_location="cpu")
    model.load_state_dict(state_dict, strict=False)
    print("  Loaded.", flush=True)

    # Optimizer with low LR for fine-tuning
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)

    model.train()
    best_loss = float("inf")
    best_state = None

    for epoch in range(epochs):
        try:
            a_v, a_m, p_v, p_m, n_v, n_m = make_triplet_batch(
                disease_hpos, sibling_groups, node_embedding,
                batch_size=batch_size, rng=rng,
            )
        except ValueError as e:
            print(f"  Epoch {epoch}: batch error: {e}")
            continue

        optimizer.zero_grad()
        loss = combined_loss(
            model, a_v, a_m, p_v, p_m, n_v, n_m,
            temperature=temperature,
            triplet_margin=triplet_margin,
            triplet_weight=triplet_weight,
        )
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        optimizer.step()
        scheduler.step()

        if loss.item() < best_loss:
            best_loss = loss.item()
            best_state = {k: v.clone() for k, v in model.state_dict().items()}

        if (epoch + 1) % 10 == 0:
            print(f"  Epoch {epoch+1:4d}/{epochs}: loss={loss.item():.4f} "
                  f"(best={best_loss:.4f}, lr={scheduler.get_last_lr()[0]:.2e})", flush=True)

    # Save best model
    if best_state is not None:
        model.load_state_dict(best_state)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    save_path = OUTPUT_DIR / "finetuned_encoder.pth"
    torch.save(model.state_dict(), str(save_path))
    print(f"\nSaved fine-tuned encoder to {save_path}", flush=True)

    # Also re-compute node embeddings using the fine-tuned encoder
    # (The GCN embeddings don't change — only the transformer encoder changes)
    print("Note: To use the fine-tuned encoder in PhenoDP, replace the encoder weights.")
    print(f"Original: {ENCODER_WEIGHTS_PATH}")
    print(f"Fine-tuned: {save_path}")


# ---------------------------------------------------------------------------
# Step 3: Evaluate
# ---------------------------------------------------------------------------

def step_evaluate():
    """Evaluate fine-tuned encoder by comparing semantic similarity signal
    before and after fine-tuning on the benchmark dataset."""
    print("=" * 80)
    print("STEP 3: Evaluating fine-tuned encoder")
    print("=" * 80)

    node_embedding, disease_hpos = load_phenodp_data()

    # Load original and fine-tuned encoders
    print("Loading original encoder...", flush=True)
    original_model = PCL_HPOEncoder(input_dim=256, num_heads=8, num_layers=3, hidden_dim=512)
    original_state = torch.load(str(ENCODER_WEIGHTS_PATH), map_location="cpu")
    original_model.load_state_dict(original_state, strict=False)
    original_model.eval()

    finetuned_path = OUTPUT_DIR / "finetuned_encoder.pth"
    if not finetuned_path.exists():
        print(f"Fine-tuned encoder not found at {finetuned_path}. Run --step train first.")
        return

    print("Loading fine-tuned encoder...", flush=True)
    finetuned_model = PCL_HPOEncoder(input_dim=256, num_heads=8, num_layers=3, hidden_dim=512)
    finetuned_state = torch.load(str(finetuned_path), map_location="cpu")
    finetuned_model.load_state_dict(finetuned_state, strict=False)
    finetuned_model.eval()

    # Load sibling groups for subtype analysis
    groups_path = OUTPUT_DIR / "sibling_groups.json"
    sibling_groups = {}
    if groups_path.exists():
        with open(groups_path) as f:
            sibling_groups = json.load(f)

    # Build disease -> siblings mapping
    disease_to_siblings = {}
    for gid, dids in sibling_groups.items():
        for d in dids:
            disease_to_siblings[d] = [s for s in dids if s != d]

    def encode_hpos(model, hpo_ids):
        """Encode a set of HPO IDs through the encoder, return CLS embedding."""
        valid = [h for h in hpo_ids if h in node_embedding]
        if not valid:
            return None
        vec = torch.tensor(get_hps_vec(valid, node_embedding), dtype=torch.float32)
        vec, mask = pad_or_truncate(vec)
        mask = torch.tensor([True] + list(mask)).float()
        vec = vec.unsqueeze(0)
        mask = mask.unsqueeze(0)
        with torch.no_grad():
            cls, _ = model(vec, mask)
        return cls.squeeze(0)

    # Load candidate data and evaluate semantic signal
    print("Loading benchmark candidates...", flush=True)
    records = []
    with open(CANDIDATE_JSONL) as f:
        for line in f:
            records.append(json.loads(line))
    print(f"  {len(records)} cases", flush=True)

    # Evaluate: for each case, compute cosine similarity between
    # patient embedding and each candidate disease embedding
    print("\nEvaluating semantic signal (this may take a while)...", flush=True)

    results = {"original": {"h1": 0, "h3": 0, "h5": 0, "h10": 0, "n": 0, "subtype_h1": 0, "subtype_n": 0},
               "finetuned": {"h1": 0, "h3": 0, "h5": 0, "h10": 0, "n": 0, "subtype_h1": 0, "subtype_n": 0}}

    for idx, rec in enumerate(records):
        patient_hpos = rec["phenotype_ids"]
        truth_ids = set(t.upper() for t in rec["truth_ids"])
        candidates = rec["candidates"]

        # Check if this is a subtype case
        is_subtype = any(t in disease_to_siblings for t in truth_ids)

        for model_name, model in [("original", original_model), ("finetuned", finetuned_model)]:
            patient_emb = encode_hpos(model, patient_hpos)
            if patient_emb is None:
                continue

            scored = []
            for c in candidates:
                did = c["disease_id"].upper()
                # Get disease HPOs
                d_hpos = disease_hpos.get(did, [])
                if not d_hpos:
                    scored.append((0.0, did))
                    continue
                disease_emb = encode_hpos(model, d_hpos)
                if disease_emb is None:
                    scored.append((0.0, did))
                    continue
                sim = F.cosine_similarity(patient_emb.unsqueeze(0), disease_emb.unsqueeze(0)).item()
                scored.append((sim, did))

            scored.sort(key=lambda x: -x[0])
            for rank, (_, did) in enumerate(scored):
                if did in truth_ids:
                    if rank < 1: results[model_name]["h1"] += 1
                    if rank < 3: results[model_name]["h3"] += 1
                    if rank < 5: results[model_name]["h5"] += 1
                    if rank < 10: results[model_name]["h10"] += 1
                    if is_subtype and rank < 1:
                        results[model_name]["subtype_h1"] += 1
                    break
            results[model_name]["n"] += 1
            if is_subtype:
                results[model_name]["subtype_n"] += 1

        if (idx + 1) % 100 == 0:
            print(f"  {idx+1}/{len(records)} cases processed...", flush=True)

    # Print results
    print(f"\n{'='*80}")
    print("SEMANTIC SIGNAL EVALUATION (encoder CLS embedding cosine similarity)")
    print(f"{'='*80}\n")

    for model_name in ["original", "finetuned"]:
        r = results[model_name]
        n = r["n"]
        if n == 0:
            continue
        print(f"  {model_name.upper()}: "
              f"H@1={r['h1']/n*100:.2f}%  H@3={r['h3']/n*100:.2f}%  "
              f"H@5={r['h5']/n*100:.2f}%  H@10={r['h10']/n*100:.2f}%  "
              f"(n={n})")
        if r["subtype_n"] > 0:
            print(f"    Subtype cases: H@1={r['subtype_h1']/r['subtype_n']*100:.2f}%  "
                  f"(n={r['subtype_n']})")

    print("\nDone.", flush=True)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Proposal 5: Subtype-Aware Contrastive Training")
    parser.add_argument("--step", choices=["build-groups", "train", "evaluate", "all"], default="all")
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--lr", type=float, default=5e-5)
    parser.add_argument("--triplet-weight", type=float, default=0.5)
    parser.add_argument("--triplet-margin", type=float, default=0.3)
    parser.add_argument("--temperature", type=float, default=0.1)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    if args.step in ("build-groups", "all"):
        step_build_groups()

    if args.step in ("train", "all"):
        step_train(
            epochs=args.epochs, batch_size=args.batch_size, lr=args.lr,
            triplet_weight=args.triplet_weight, triplet_margin=args.triplet_margin,
            temperature=args.temperature, seed=args.seed,
        )

    if args.step in ("evaluate", "all"):
        step_evaluate()


if __name__ == "__main__":
    main()
