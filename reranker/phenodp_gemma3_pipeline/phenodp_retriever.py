from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional, Set

import numpy as np
import torch
import torch.nn as nn
from pyhpo import Ontology

from .models import DiseaseCandidate

if TYPE_CHECKING:
    from .hpo_annotations import HPOAnnotationStore


@dataclass
class PhenoDPOptions:
    phenodp_repo_root: str
    phenodp_data_dir: str
    phenodp_hpo_dir: str
    ic_type: str = "omim"
    device: str = "cpu"
    candidate_pool_size: int = 200


class PhenoDPRetriever:
    def __init__(self, opts: PhenoDPOptions):
        self.opts = opts
        repo_root = Path(opts.phenodp_repo_root)
        if not repo_root.exists():
            raise FileNotFoundError(f"PhenoDP repo root not found: {repo_root}")

        core_module = self._load_module(repo_root / "phenodp" / "core.py", "phenodp_core_local")
        preprocess_module = self._load_module(repo_root / "phenodp" / "preprocess.py", "phenodp_preprocess_local")
        utils_module = self._load_module(repo_root / "phenodp" / "utils.py", "phenodp_utils_local")

        # Silence the internal tqdm bars inside PhenoDP core
        import tqdm as _tqdm
        core_module.tqdm = lambda *a, **kw: _tqdm.tqdm(*a, **{**kw, "disable": True})

        self._PhenoDP = core_module.PhenoDP
        self._PhenoDPInitial = preprocess_module.PhenoDP_Initial
        self._PCL_HPOEncoder = _LocalPCLHPOEncoder
        self._load_similarity_matrix = utils_module.load_similarity_matrix
        self._load_node_embeddings = utils_module.load_node_embeddings

        device = opts.device if opts.device == "cpu" or torch.cuda.is_available() else "cpu"
        self.device = device
        self.ontology = Ontology(data_folder=opts.phenodp_hpo_dir)
        if not hasattr(self.ontology, "to_dataframe"):
            term_ids = [term.id for term in self.ontology]

            class _OntologyFrame:
                def __init__(self, index):
                    self.index = index

            self.ontology.to_dataframe = lambda: _OntologyFrame(term_ids)  # type: ignore[attr-defined]

        encoder = self._PCL_HPOEncoder(
            input_dim=256,
            num_heads=8,
            num_layers=3,
            hidden_dim=512,
            output_dim=1,
            max_seq_length=128,
        )
        pre_model = self._PhenoDPInitial(self.ontology, ic_type=opts.ic_type)
        similarity_matrix = self._load_similarity_matrix(str(Path(opts.phenodp_data_dir) / "JC_sim_dict.pkl"))
        node_embeddings = self._load_node_embeddings(str(Path(opts.phenodp_data_dir) / "node_embedding_dict.pkl"))
        state = torch.load(
            str(Path(opts.phenodp_data_dir) / "transformer_encoder_infoNCE.pth"),
            map_location=device,
        )
        encoder.load_state_dict(state)
        self.model = self._PhenoDP(pre_model, similarity_matrix, node_embeddings, encoder)
        self.disease_name_map = self._build_disease_name_map()

    @staticmethod
    def _load_module(module_path: Path, module_name: str):
        if not module_path.exists():
            raise FileNotFoundError(f"Required PhenoDP module not found: {module_path}")
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Could not load module from {module_path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def _build_disease_name_map(self) -> Dict[str, str]:
        if self.opts.ic_type == "omim":
            diseases = self.ontology.omim_diseases
            prefix = "OMIM"
        elif self.opts.ic_type == "orpha":
            diseases = self.ontology.orpha_diseases
            prefix = "ORPHA"
        else:
            raise ValueError(f"Unsupported ic_type: {self.opts.ic_type}")

        mapping: Dict[str, str] = {}
        for disease in diseases:
            disease_id = str(getattr(disease, "id", "")).strip()
            if not disease_id:
                continue
            disease_name = str(getattr(disease, "name", None) or f"{prefix}:{disease_id}")
            mapping[disease_id] = disease_name
        return mapping

    def _canonicalize_id(self, disease_id: str) -> str:
        raw = str(disease_id or "").strip()
        if not raw:
            return ""
        if ":" in raw:
            return raw.upper()
        if self.opts.ic_type == "omim":
            return f"OMIM:{int(raw)}"
        if self.opts.ic_type == "orpha":
            return f"ORPHA:{int(raw)}"
        return raw

    @staticmethod
    def _zscore(values: np.ndarray) -> np.ndarray:
        m, s = values.mean(), values.std()
        return (values - m) / s if s > 1e-9 else np.zeros_like(values)

    def retrieve(
        self,
        phenotype_ids: List[str],
        top_k: int,
        neg_phenotype_ids: Optional[List[str]] = None,
        annotation_store: "Optional[HPOAnnotationStore]" = None,
        neg_penalty_weight: float = 0.15,
        precision_recall_rescoring: bool = False,
        recall_weight: float = 1.0,
        precision_penalty_weight: float = 0.5,
    ) -> List[DiseaseCandidate]:
        filtered_hpos = self.model.filter_hps(list(dict.fromkeys(phenotype_ids)))
        if not filtered_hpos:
            return []
        # Retrieve exactly top_k candidates; rescoring re-ranks within this set
        results = self.model.run_Ranker(filtered_hpos, top_n=int(top_k))

        # Build raw candidate list from PhenoDP results
        pos_set: Set[str] = set(phenotype_ids)
        raw_candidates: List[dict] = []
        for row in results.itertuples(index=False):
            raw_disease_id = str(getattr(row, "Disease"))
            disease_id = self._canonicalize_id(raw_disease_id)
            total_similarity = float(getattr(row, "Total_Similarity"))
            raw_candidates.append({
                "raw_disease_id": raw_disease_id,
                "disease_id": disease_id,
                "score": total_similarity,
            })

        # Apply precision-recall rescoring with z-score normalization
        if precision_recall_rescoring and annotation_store:
            for cand in raw_candidates:
                disease_hpos = set(
                    a.hpo_id for a in annotation_store.get_annotations(cand["disease_id"])
                )
                overlap = len(pos_set & disease_hpos)
                cand["recall"] = overlap / len(pos_set) if pos_set else 0.0
                cand["precision"] = overlap / len(disease_hpos) if disease_hpos else 0.0

            # Z-score normalize each signal across the candidate list
            scores = np.array([c["score"] for c in raw_candidates], dtype=float)
            recalls = np.array([c["recall"] for c in raw_candidates], dtype=float)
            precisions = np.array([c["precision"] for c in raw_candidates], dtype=float)

            z_scores = self._zscore(scores)
            z_recalls = self._zscore(recalls)
            z_precisions = self._zscore(precisions)

            for idx, cand in enumerate(raw_candidates):
                cand["adjusted_score"] = (
                    z_scores[idx]
                    + recall_weight * z_recalls[idx]
                    - precision_penalty_weight * z_precisions[idx]
                )
            raw_candidates.sort(key=lambda c: c["adjusted_score"], reverse=True)
        else:
            for cand in raw_candidates:
                cand["recall"] = 0.0
                cand["precision"] = 0.0
                cand["adjusted_score"] = cand["score"]

        # Take top-k and build output
        candidates: List[DiseaseCandidate] = []
        for rank, cand in enumerate(raw_candidates[:int(top_k)], start=1):
            disease_name = self.disease_name_map.get(cand["raw_disease_id"], cand["disease_id"])
            candidates.append(
                DiseaseCandidate(
                    disease_id=cand["disease_id"],
                    disease_name=disease_name,
                    score=cand["adjusted_score"],
                    retrieval_rank=rank,
                    source_score=cand["score"],
                    raw_disease_id=cand["raw_disease_id"],
                    metadata={
                        "raw_total_similarity": cand["score"],
                        "recall": cand["recall"],
                        "precision": cand["precision"],
                    },
                )
            )
        return candidates


class _LocalPCLHPOEncoder(nn.Module):
    def __init__(
        self,
        input_dim: int = 256,
        num_heads: int = 8,
        num_layers: int = 3,
        hidden_dim: int = 512,
        dropout: float = 0.1,
        output_dim: int = 1,
        max_seq_length: int = 128,
    ):
        super().__init__()
        self.cls_token = nn.Parameter(torch.zeros(1, 1, input_dim))
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=input_dim,
            nhead=num_heads,
            dim_feedforward=hidden_dim,
        )
        self.transformer_encoder = nn.TransformerEncoder(encoder_layer, num_layers)
        self.dropout = nn.Dropout(p=dropout)
        self.fc1 = nn.Linear(input_dim, hidden_dim)
        self.fc2 = nn.Linear(hidden_dim, output_dim)
        self.input_dim = input_dim

    def forward(self, vec, mask):
        batch_size, _, _ = vec.size()
        cls_tokens = self.cls_token.expand(batch_size, -1, -1)
        vec = torch.cat((cls_tokens, vec), dim=1)
        vec = vec.permute(1, 0, 2)
        vec = self.transformer_encoder(vec, src_key_padding_mask=mask)
        cls_embedding = vec[0]
        return cls_embedding, vec
