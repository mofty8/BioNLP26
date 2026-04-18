"""Results I/O: JSONL streaming output, manifest, and metrics files."""

from __future__ import annotations

import hashlib
import json
import logging
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import uuid4

from dx_bench.config import RunConfig
from dx_bench.data.schema import AggregateMetrics, CaseResult, RunManifest

logger = logging.getLogger(__name__)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _git_hash() -> Optional[str]:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


class ResultWriter:
    """Streams CaseResult objects to JSONL and writes summary files."""

    def __init__(self, config: RunConfig) -> None:
        self._config = config
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        model_short = config.model_name.split("/")[-1]
        self._run_id = f"{model_short}_{timestamp}_{uuid4().hex[:8]}"
        self._run_dir = config.output_dir / self._run_id
        self._run_dir.mkdir(parents=True, exist_ok=True)

        self._results_path = self._run_dir / "results.jsonl"
        self._errors_path = self._run_dir / "errors.jsonl"
        self._review_path = self._run_dir / "fuzzy_review.jsonl"

        self._n_written = 0
        logger.info("Results directory: %s", self._run_dir)

    @property
    def run_id(self) -> str:
        return self._run_id

    @property
    def run_dir(self) -> Path:
        return self._run_dir

    def count_existing(self) -> int:
        """Count existing results for resumption."""
        if not self._results_path.exists():
            return 0
        count = 0
        with open(self._results_path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    count += 1
        logger.info("Found %d existing results (resumption)", count)
        return count

    def write_result(self, result: CaseResult) -> None:
        """Append a single case result to JSONL."""
        line = result.model_dump_json() + "\n"
        with open(self._results_path, "a", encoding="utf-8") as f:
            f.write(line)

        # Also write to errors file if applicable
        if result.error:
            with open(self._errors_path, "a", encoding="utf-8") as f:
                f.write(line)

        # Write fuzzy review candidates
        for dx in result.diagnoses:
            if dx.fuzzy_score is not None and 85 <= dx.fuzzy_score < 100:
                review_entry = {
                    "case_id": result.case_id,
                    "rank": dx.rank,
                    "disease_name": dx.disease_name,
                    "resolved_name": dx.resolved_name,
                    "resolved_id": dx.resolved_id,
                    "fuzzy_score": dx.fuzzy_score,
                }
                with open(self._review_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(review_entry) + "\n")

        self._n_written += 1

    def write_metrics(self, metrics: AggregateMetrics) -> None:
        """Write aggregate metrics JSON."""
        path = self._run_dir / "metrics.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(metrics.model_dump(), f, indent=2)
        logger.info("Metrics written to %s", path)

    def write_manifest(self, total_cases: int, started_at: str) -> None:
        """Write run manifest for reproducibility."""
        manifest = RunManifest(
            run_id=self._run_id,
            model_name=self._config.model_name,
            model_revision=self._config.model_revision,
            backend=self._config.backend,
            model_params={
                "max_tokens": self._config.max_tokens,
                "temperature": self._config.temperature,
                "top_p": self._config.top_p,
                "seed": self._config.seed,
                "max_diagnoses": self._config.max_diagnoses,
            },
            prompt_dir=str(self._config.prompt_dir),
            ground_truth_file=str(self._config.ground_truth_file),
            benchmark_ids_file=str(self._config.benchmark_ids_file),
            ground_truth_sha256=_sha256(self._config.ground_truth_file),
            benchmark_ids_sha256=_sha256(self._config.benchmark_ids_file),
            total_cases=total_cases,
            started_at=started_at,
            finished_at=datetime.now(timezone.utc).isoformat(),
            git_hash=_git_hash(),
            config=self._config.to_dict(),
        )
        path = self._run_dir / "manifest.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(manifest.model_dump(), f, indent=2)
        logger.info("Manifest written to %s", path)
