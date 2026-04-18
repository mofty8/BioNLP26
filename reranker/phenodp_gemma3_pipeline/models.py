from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class PatientCase:
    patient_id: str
    description: str
    phenotype_ids: List[str]
    phenotype_labels: List[str]
    neg_phenotype_ids: List[str] = field(default_factory=list)
    neg_phenotype_labels: List[str] = field(default_factory=list)
    genes: List[str] = field(default_factory=list)
    sex: Optional[str] = None
    age: Optional[str] = None
    source_prefix: Optional[str] = None
    file_path: Optional[str] = None


@dataclass(frozen=True)
class Truth:
    disease_ids: List[str]
    disease_labels: List[str]


@dataclass
class DiseaseCandidate:
    disease_id: str
    disease_name: str
    score: float
    retrieval_rank: int
    source_score: float
    raw_disease_id: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> Dict[str, Any]:
        return {
            "disease_id": self.disease_id,
            "disease_name": self.disease_name,
            "score": float(self.score),
            "retrieval_rank": int(self.retrieval_rank),
            "source_score": float(self.source_score),
            "raw_disease_id": self.raw_disease_id,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_json(cls, obj: Dict[str, Any]) -> "DiseaseCandidate":
        return cls(
            disease_id=str(obj.get("disease_id") or ""),
            disease_name=str(obj.get("disease_name") or obj.get("disease_label") or obj.get("disease_id") or ""),
            score=float(obj.get("score", 0.0)),
            retrieval_rank=int(obj.get("retrieval_rank", 0) or 0),
            source_score=float(obj.get("source_score", obj.get("score", 0.0))),
            raw_disease_id=str(obj.get("raw_disease_id") or ""),
            metadata=dict(obj.get("metadata") or {}),
        )
