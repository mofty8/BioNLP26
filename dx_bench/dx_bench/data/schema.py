"""Core data types for the dx-bench pipeline."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class Case(BaseModel):
    """A single benchmark case: prompt + ground truth."""

    case_id: str
    prompt_file: str
    prompt_text: str
    gold_disease_label: str
    gold_disease_id: str  # OMIM:XXXXXX


class Diagnosis(BaseModel):
    """A single disease in the ranked output list."""

    rank: int
    raw_text: str
    disease_name: str
    predicted_id: Optional[str] = None       # OMIM ID from LLM output
    resolved_id: Optional[str] = None        # OMIM ID from fuzzy name matching
    resolved_name: Optional[str] = None      # matched reference name
    mondo_id: Optional[str] = None           # Mondo ID (if resolved)
    fuzzy_score: Optional[float] = None      # rapidfuzz score for name match
    id_source: str = "none"                  # "predicted" | "resolved" | "both" | "none"


class CaseResult(BaseModel):
    """Full result for one case after inference + evaluation."""

    case_id: str
    prompt_file: str
    gold_disease_id: str
    gold_disease_label: str
    gold_mondo_id: Optional[str] = None

    raw_response: str = ""
    diagnoses: list[Diagnosis] = Field(default_factory=list)
    parse_warnings: list[str] = Field(default_factory=list)

    # Per-case evaluation
    gold_rank_by_id: Optional[int] = None
    gold_rank_by_name: Optional[int] = None
    gold_rank_by_id_or_name: Optional[int] = None
    gold_rank_by_mondo: Optional[int] = None

    reciprocal_rank_id: float = 0.0
    reciprocal_rank_name: float = 0.0
    reciprocal_rank_id_or_name: float = 0.0
    reciprocal_rank_mondo: float = 0.0

    error: Optional[str] = None
    latency_s: float = 0.0
    timestamp: str = ""


class AggregateMetrics(BaseModel):
    """Aggregate evaluation over all cases in a run."""

    n_cases: int = 0
    n_errors: int = 0
    error_rate: float = 0.0

    # By criterion: id, name, id_or_name, mondo
    mrr_id: float = 0.0
    mrr_name: float = 0.0
    mrr_id_or_name: float = 0.0
    mrr_mondo: float = 0.0

    recall_at_1_id: float = 0.0
    recall_at_3_id: float = 0.0
    recall_at_5_id: float = 0.0
    recall_at_10_id: float = 0.0

    recall_at_1_name: float = 0.0
    recall_at_3_name: float = 0.0
    recall_at_5_name: float = 0.0
    recall_at_10_name: float = 0.0

    recall_at_1_id_or_name: float = 0.0
    recall_at_3_id_or_name: float = 0.0
    recall_at_5_id_or_name: float = 0.0
    recall_at_10_id_or_name: float = 0.0

    recall_at_1_mondo: float = 0.0
    recall_at_3_mondo: float = 0.0
    recall_at_5_mondo: float = 0.0
    recall_at_10_mondo: float = 0.0

    found_rate_id: float = 0.0
    found_rate_name: float = 0.0
    found_rate_id_or_name: float = 0.0
    found_rate_mondo: float = 0.0

    mean_rank_id: float = 0.0
    mean_rank_name: float = 0.0
    mean_rank_id_or_name: float = 0.0
    mean_rank_mondo: float = 0.0

    # Fuzzy match review band
    n_fuzzy_auto_correct: int = 0   # score == 100
    n_fuzzy_review: int = 0         # 85 <= score < 100
    n_fuzzy_rejected: int = 0       # score < 85


class RunManifest(BaseModel):
    """Complete record of a pipeline run for reproducibility."""

    run_id: str
    model_name: str
    model_revision: Optional[str] = None
    backend: str
    model_params: dict = Field(default_factory=dict)
    prompt_dir: str
    ground_truth_file: str
    benchmark_ids_file: str
    ground_truth_sha256: str = ""
    benchmark_ids_sha256: str = ""
    total_cases: int = 0
    started_at: str = ""
    finished_at: str = ""
    git_hash: Optional[str] = None
    pipeline_version: str = "0.1.0"
    config: dict = Field(default_factory=dict)
