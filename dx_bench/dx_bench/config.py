"""Run configuration for dx-bench pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml


@dataclass
class RunConfig:
    # ── Data ──────────────────────────────────────────────────────────────
    prompt_dir: Path
    ground_truth_file: Path
    benchmark_ids_file: Path
    output_dir: Path

    # ── Model ─────────────────────────────────────────────────────────────
    backend: str = "vllm"
    model_name: str = "google/gemma-3-27b-it"
    model_revision: Optional[str] = None
    api_base_url: str = "http://127.0.0.1:8000/v1"
    api_key: Optional[str] = None
    tokenizer_name: Optional[str] = None  # for completions_chat backend; defaults to model_name
    request_timeout_s: int = 600
    empty_completion_retries: int = 2

    # ── Generation ────────────────────────────────────────────────────────
    max_tokens: int = 512
    temperature: float = 0.0
    top_p: float = 1.0
    seed: int = 42
    max_diagnoses: int = 10

    # ── Execution ─────────────────────────────────────────────────────────
    batch_size: int = 256
    gpu_ids: list[int] = field(default_factory=lambda: [0])
    tensor_parallel_size: int = 1
    gpu_memory_utilization: float = 0.90

    # ── Normalization ─────────────────────────────────────────────────────
    fuzzy_auto_threshold: int = 100
    fuzzy_review_threshold: int = 85
    use_mondo: bool = True
    mondo_db_path: Optional[str] = None

    # ── Run control ───────────────────────────────────────────────────────
    limit: Optional[int] = None
    offset: int = 0
    resume: bool = True

    # ── Prompt override (to request N ranked diagnoses + OMIM IDs) ───────
    prompt_suffix: str = (
        "\n\nProvide your top 10 candidate diagnoses. "
        "For each candidate, include the OMIM identifier and disease name.\n"
        "Format each line as: rank. OMIM:XXXXXX - Disease name\n"
        "For example:\n"
        "1. OMIM:113620 - Branchiooculofacial syndrome\n"
        "2. OMIM:219700 - Cystic fibrosis\n"
    )

    def __post_init__(self) -> None:
        self.prompt_dir = Path(self.prompt_dir)
        self.ground_truth_file = Path(self.ground_truth_file)
        self.benchmark_ids_file = Path(self.benchmark_ids_file)
        self.output_dir = Path(self.output_dir)

    @classmethod
    def from_yaml(cls, path: str | Path) -> RunConfig:
        with open(path) as f:
            raw = yaml.safe_load(f)
        return cls(**raw)

    def to_dict(self) -> dict:
        d = {}
        for k, v in self.__dict__.items():
            if isinstance(v, Path):
                d[k] = str(v)
            else:
                d[k] = v
        return d
