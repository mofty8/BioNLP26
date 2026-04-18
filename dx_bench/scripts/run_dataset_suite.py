"""Run dx-bench sequentially over a predefined dataset suite."""

from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path("/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket")
DX_BENCH_ROOT = REPO_ROOT / "dx_bench"
PROMPTS_ROOT = REPO_ROOT / "PP2Prompt" / "prompts"


@dataclass(frozen=True)
class DatasetSpec:
    name: str
    prompt_dir: Path
    ground_truth: Path
    benchmark_ids: Path
    output_subdir: str


DATASETS: dict[str, DatasetSpec] = {
    "phenopacket": DatasetSpec(
        name="phenopacket",
        prompt_dir=PROMPTS_ROOT / "en",
        ground_truth=PROMPTS_ROOT / "correct_results.tsv",
        benchmark_ids=REPO_ROOT
        / "phenodp_gemma3_candidate_ranking"
        / "benchmark_ids_6901_phenodp_compatible_min3hpo.txt",
        output_subdir="phenopacket",
    ),
    "rarebench_hms": DatasetSpec(
        name="rarebench_hms",
        prompt_dir=PROMPTS_ROOT / "rarebench" / "HMS" / "en",
        ground_truth=PROMPTS_ROOT / "rarebench" / "HMS" / "correct_results.tsv",
        benchmark_ids=PROMPTS_ROOT / "rarebench" / "HMS" / "benchmark_ids.txt",
        output_subdir="rarebench/HMS",
    ),
    "rarebench_lirical": DatasetSpec(
        name="rarebench_lirical",
        prompt_dir=PROMPTS_ROOT / "rarebench" / "LIRICAL" / "en",
        ground_truth=PROMPTS_ROOT / "rarebench" / "LIRICAL" / "correct_results.tsv",
        benchmark_ids=PROMPTS_ROOT / "rarebench" / "LIRICAL" / "benchmark_ids.txt",
        output_subdir="rarebench/LIRICAL",
    ),
    "rarebench_mme": DatasetSpec(
        name="rarebench_mme",
        prompt_dir=PROMPTS_ROOT / "rarebench" / "MME" / "en",
        ground_truth=PROMPTS_ROOT / "rarebench" / "MME" / "correct_results.tsv",
        benchmark_ids=PROMPTS_ROOT / "rarebench" / "MME" / "benchmark_ids.txt",
        output_subdir="rarebench/MME",
    ),
    "rarebench_ramedis": DatasetSpec(
        name="rarebench_ramedis",
        prompt_dir=PROMPTS_ROOT / "rarebench" / "RAMEDIS" / "en",
        ground_truth=PROMPTS_ROOT / "rarebench" / "RAMEDIS" / "correct_results.tsv",
        benchmark_ids=PROMPTS_ROOT / "rarebench" / "RAMEDIS" / "benchmark_ids.txt",
        output_subdir="rarebench/RAMEDIS",
    ),
    "mygene2": DatasetSpec(
        name="mygene2",
        prompt_dir=PROMPTS_ROOT / "archive2" / "mygene2" / "en",
        ground_truth=PROMPTS_ROOT / "archive2" / "mygene2" / "correct_results.tsv",
        benchmark_ids=PROMPTS_ROOT / "archive2" / "mygene2" / "benchmark_ids.txt",
        output_subdir="archive2/mygene2",
    ),
    "allg2p": DatasetSpec(
        name="allg2p",
        prompt_dir=PROMPTS_ROOT / "archive2" / "allG2P" / "en",
        ground_truth=PROMPTS_ROOT / "archive2" / "allG2P" / "correct_results.tsv",
        benchmark_ids=PROMPTS_ROOT / "archive2" / "allG2P" / "benchmark_ids.txt",
        output_subdir="archive2/allG2P",
    ),
    # allg2p_2248: same 2248-case benchmark used by the reranker pipeline.
    # Prompts: PP2Prompt narrative (pp2prompt_v2) in archive2_merged_en/ (ALLG2P_XXXX naming).
    # GT and benchmark_ids derived from the allg2p_full_2248 reranker result bundle.
    "allg2p_2248": DatasetSpec(
        name="allg2p_2248",
        prompt_dir=PROMPTS_ROOT / "archive2_merged_en",
        ground_truth=PROMPTS_ROOT / "archive2_merged_en" / "correct_results_allg2p_2248.tsv",
        benchmark_ids=PROMPTS_ROOT / "archive2_merged_en" / "benchmark_ids_allg2p_2248.txt",
        output_subdir="archive2/allG2P_2248",
    ),
}

DEFAULT_DATASET_ORDER = [
    "phenopacket",
    "rarebench_hms",
    "rarebench_lirical",
    "rarebench_mme",
    "rarebench_ramedis",
    "mygene2",
    "allg2p",
    "allg2p_2248",
]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run dx-bench sequentially across prepared datasets."
    )
    parser.add_argument(
        "--model",
        required=True,
        help="Model identifier passed to dx_bench.runner and the HTTP server.",
    )
    parser.add_argument(
        "--config",
        default=str(DX_BENCH_ROOT / "config.yaml"),
        help="Base dx-bench config file.",
    )
    parser.add_argument(
        "--api-base-url",
        default="http://127.0.0.1:8000/v1",
        help="OpenAI-compatible server base URL.",
    )
    parser.add_argument(
        "--api-key",
        default="local-token",
        help="API key used for the HTTP backend.",
    )
    parser.add_argument(
        "--backend",
        default="openai_http",
        help="Inference backend to use for each dataset run.",
    )
    parser.add_argument(
        "--results-root",
        default=None,
        help=(
            "Parent directory under which per-dataset result folders are created. "
            "Defaults to dx_bench/results/<model-name>_http."
        ),
    )
    parser.add_argument(
        "--datasets",
        nargs="+",
        default=["all"],
        help=(
            "Dataset keys to run. Use 'all' for the full suite. "
            f"Choices: {', '.join(DEFAULT_DATASET_ORDER)}"
        ),
    )
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--request-timeout-s", type=int, default=600)
    parser.add_argument("--empty-completion-retries", type=int, default=2)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--offset", type=int)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--use-mondo", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument(
        "--tokenizer-name",
        type=str,
        default=None,
        help="HuggingFace tokenizer for completions_chat backend (defaults to --model).",
    )
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Continue with the remaining datasets if one dataset run fails.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the commands that would be executed without running them.",
    )
    return parser.parse_args()


def _default_results_root(model_name: str) -> Path:
    model_short = model_name.split("/")[-1].strip().lower().replace("/", "-")
    return DX_BENCH_ROOT / "results" / f"{model_short}_http"


def _select_datasets(raw_names: list[str]) -> list[DatasetSpec]:
    if raw_names == ["all"]:
        return [DATASETS[name] for name in DEFAULT_DATASET_ORDER]

    selected = []
    for name in raw_names:
        key = name.lower()
        if key not in DATASETS:
            raise SystemExit(
                f"Unknown dataset '{name}'. Valid choices: "
                + ", ".join(DEFAULT_DATASET_ORDER)
            )
        selected.append(DATASETS[key])
    return selected


def _build_command(args: argparse.Namespace, dataset: DatasetSpec) -> list[str]:
    output_dir = Path(args.results_root) / dataset.output_subdir
    cmd = [
        sys.executable,
        "-m",
        "dx_bench.runner",
        "--config",
        str(args.config),
        "--backend",
        args.backend,
        "--model",
        args.model,
        "--api-base-url",
        args.api_base_url,
        "--api-key",
        args.api_key,
        "--prompt-dir",
        str(dataset.prompt_dir),
        "--ground-truth",
        str(dataset.ground_truth),
        "--benchmark-ids",
        str(dataset.benchmark_ids),
        "--output-dir",
        str(output_dir),
        "--batch-size",
        str(args.batch_size),
        "--request-timeout-s",
        str(args.request_timeout_s),
        "--empty-completion-retries",
        str(args.empty_completion_retries),
    ]

    if args.limit is not None:
        cmd.extend(["--limit", str(args.limit)])
    if args.offset is not None:
        cmd.extend(["--offset", str(args.offset)])
    if args.seed is not None:
        cmd.extend(["--seed", str(args.seed)])
    if not args.use_mondo:
        cmd.append("--no-mondo")
    if not args.resume:
        cmd.append("--no-resume")
    if args.tokenizer_name:
        cmd.extend(["--tokenizer-name", args.tokenizer_name])

    return cmd


def main() -> None:
    args = _parse_args()
    if args.results_root is None:
        args.results_root = str(_default_results_root(args.model))
    datasets = _select_datasets(args.datasets)

    failures: list[str] = []

    for dataset in datasets:
        cmd = _build_command(args, dataset)
        print(f"\n=== Running {dataset.name} ===")
        print(shlex.join(cmd))

        if args.dry_run:
            continue

        result = subprocess.run(cmd, cwd=DX_BENCH_ROOT)
        if result.returncode != 0:
            failures.append(dataset.name)
            if not args.continue_on_error:
                raise SystemExit(result.returncode)

    if failures:
        raise SystemExit(
            "Suite finished with failures in: " + ", ".join(failures)
        )

    print("\nSuite finished successfully.")


if __name__ == "__main__":
    main()
