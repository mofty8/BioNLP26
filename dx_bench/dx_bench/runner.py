"""CLI entrypoint: orchestrates the full dx-bench pipeline."""

from __future__ import annotations

import argparse
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from dx_bench.config import RunConfig
from dx_bench.data.loader import load_cases
from dx_bench.data.schema import CaseResult, Diagnosis
from dx_bench.evaluation.metrics import compute_aggregate, evaluate_case
from dx_bench.io.writer import ResultWriter
from dx_bench.models.base import InferenceBackend
from dx_bench.normalization.disease_matcher import DiseaseMatcher
from dx_bench.normalization.mondo_resolver import MondoResolver
from dx_bench.parsing.response_parser import parse_response

logger = logging.getLogger(__name__)


def _setup_logging(run_dir: Path) -> None:
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    # Console: INFO+
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
    root.addHandler(ch)

    # File: DEBUG+
    fh = logging.FileHandler(run_dir / "run.log")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    )
    root.addHandler(fh)


def _build_backend(config: RunConfig) -> InferenceBackend:
    if config.backend == "vllm":
        from dx_bench.models.vllm_backend import VLLMBackend

        return VLLMBackend(
            model_name=config.model_name,
            max_tokens=config.max_tokens,
            temperature=config.temperature,
            top_p=config.top_p,
            seed=config.seed,
            tensor_parallel_size=config.tensor_parallel_size,
            gpu_memory_utilization=config.gpu_memory_utilization,
            revision=config.model_revision,
            gpu_ids=config.gpu_ids if config.gpu_ids else None,
        )
    if config.backend == "openai_http":
        from dx_bench.models.openai_http_backend import OpenAIHTTPBackend

        return OpenAIHTTPBackend(
            model_name=config.model_name,
            api_base_url=config.api_base_url,
            api_key=config.api_key,
            max_tokens=config.max_tokens,
            temperature=config.temperature,
            top_p=config.top_p,
            seed=config.seed,
            request_timeout_s=config.request_timeout_s,
            empty_completion_retries=config.empty_completion_retries,
        )
    if config.backend == "chat_http":
        from dx_bench.models.chat_http_backend import ChatHTTPBackend

        return ChatHTTPBackend(
            model_name=config.model_name,
            api_base_url=config.api_base_url,
            api_key=config.api_key,
            max_tokens=config.max_tokens,
            temperature=config.temperature,
            top_p=config.top_p,
            seed=config.seed,
            request_timeout_s=config.request_timeout_s,
            empty_completion_retries=config.empty_completion_retries,
        )
    if config.backend == "completions_chat":
        from dx_bench.models.completions_chat_backend import CompletionsChatBackend

        return CompletionsChatBackend(
            model_name=config.model_name,
            api_base_url=config.api_base_url,
            api_key=config.api_key,
            max_tokens=config.max_tokens,
            temperature=config.temperature,
            top_p=config.top_p,
            seed=config.seed,
            request_timeout_s=config.request_timeout_s,
            empty_completion_retries=config.empty_completion_retries,
            tokenizer_name=config.tokenizer_name,
        )
    raise ValueError(f"Unknown backend: {config.backend}")


def _process_batch(
    cases: list,
    prompts: list[str],
    completions: list[str],
    matcher: DiseaseMatcher,
    mondo: Optional[MondoResolver],
) -> list[CaseResult]:
    """Parse, normalize, and evaluate a batch of completions."""
    results = []

    for case, raw_response in zip(cases, completions):
        t0 = time.monotonic()

        # Parse
        diagnoses, parse_warnings = parse_response(raw_response)

        # Normalize each diagnosis
        for dx in diagnoses:
            # Fuzzy name matching
            omim_id, ref_name, score, band = matcher.match(dx.disease_name)
            dx.resolved_id = omim_id
            dx.resolved_name = ref_name
            dx.fuzzy_score = score

            # Determine id_source
            has_predicted = dx.predicted_id is not None
            has_resolved = dx.resolved_id is not None
            if has_predicted and has_resolved:
                dx.id_source = "both"
            elif has_predicted:
                dx.id_source = "predicted"
            elif has_resolved:
                dx.id_source = "resolved"
            else:
                dx.id_source = "none"

            # Mondo resolution
            if mondo:
                dx.mondo_id = mondo.resolve_diagnosis(
                    dx.predicted_id, dx.resolved_id, dx.disease_name
                )

        # Evaluate
        rank_id, rank_name, rank_ior, rank_mondo, gold_mondo = evaluate_case(
            case, diagnoses, matcher, mondo
        )

        latency = time.monotonic() - t0

        result = CaseResult(
            case_id=case.case_id,
            prompt_file=case.prompt_file,
            gold_disease_id=case.gold_disease_id,
            gold_disease_label=case.gold_disease_label,
            gold_mondo_id=gold_mondo,
            raw_response=raw_response,
            diagnoses=diagnoses,
            parse_warnings=parse_warnings,
            gold_rank_by_id=rank_id,
            gold_rank_by_name=rank_name,
            gold_rank_by_id_or_name=rank_ior,
            gold_rank_by_mondo=rank_mondo,
            reciprocal_rank_id=1.0 / rank_id if rank_id else 0.0,
            reciprocal_rank_name=1.0 / rank_name if rank_name else 0.0,
            reciprocal_rank_id_or_name=1.0 / rank_ior if rank_ior else 0.0,
            reciprocal_rank_mondo=1.0 / rank_mondo if rank_mondo else 0.0,
            error="empty_parse" if not diagnoses else None,
            latency_s=latency,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        results.append(result)

    return results


def run(config: RunConfig) -> None:
    """Main pipeline execution."""
    started_at = datetime.now(timezone.utc).isoformat()

    # Initialize writer first (creates run directory)
    writer = ResultWriter(config)
    _setup_logging(writer.run_dir)

    logger.info("=== dx-bench pipeline starting ===")
    logger.info("Run ID: %s", writer.run_id)
    logger.info("Model: %s (backend: %s)", config.model_name, config.backend)

    # Load cases
    cases = load_cases(
        prompt_dir=config.prompt_dir,
        ground_truth_file=config.ground_truth_file,
        benchmark_ids_file=config.benchmark_ids_file,
        limit=config.limit,
        offset=config.offset,
    )
    logger.info("Total cases to process: %d", len(cases))

    # Handle resumption
    n_existing = 0
    if config.resume:
        n_existing = writer.count_existing()
        if n_existing > 0:
            logger.info("Resuming: skipping first %d cases", n_existing)
            cases = cases[n_existing:]

    if not cases:
        logger.info("No cases to process (all done or empty set)")
        return

    # Initialize components
    logger.info("Initializing disease matcher...")
    matcher = DiseaseMatcher(
        ground_truth_file=config.ground_truth_file,
        auto_threshold=config.fuzzy_auto_threshold,
        review_threshold=config.fuzzy_review_threshold,
    )

    mondo: Optional[MondoResolver] = None
    if config.use_mondo:
        logger.info("Initializing Mondo resolver...")
        mondo_path = config.mondo_db_path or str(
            config.ground_truth_file.parent.parent.parent / "mondo.db"
        )
        mondo = MondoResolver(mondo_db_path=mondo_path)

    logger.info("Initializing inference backend...")
    backend = _build_backend(config)

    # Process in batches
    batch_size = config.batch_size
    all_results: list[CaseResult] = []
    n_batches = (len(cases) + batch_size - 1) // batch_size

    for batch_idx in range(n_batches):
        start = batch_idx * batch_size
        end = min(start + batch_size, len(cases))
        batch_cases = cases[start:end]

        logger.info(
            "Processing batch %d/%d (cases %d-%d)",
            batch_idx + 1,
            n_batches,
            start + n_existing + 1,
            end + n_existing,
        )

        # Build prompts with suffix override
        prompts = [c.prompt_text + config.prompt_suffix for c in batch_cases]

        # Inference
        t0 = time.monotonic()
        try:
            completions = backend.generate_batch(prompts)
        except Exception as e:
            logger.error("Batch %d inference failed: %s", batch_idx + 1, e)
            # Try halving batch size
            if len(prompts) > 1:
                logger.info("Retrying with halved batch size...")
                mid = len(prompts) // 2
                try:
                    c1 = backend.generate_batch(prompts[:mid])
                    c2 = backend.generate_batch(prompts[mid:])
                    completions = c1 + c2
                except Exception as e2:
                    logger.error("Retry also failed: %s", e2)
                    # Mark all as errors
                    for case in batch_cases:
                        result = CaseResult(
                            case_id=case.case_id,
                            prompt_file=case.prompt_file,
                            gold_disease_id=case.gold_disease_id,
                            gold_disease_label=case.gold_disease_label,
                            error=f"inference_failed: {e2}",
                            timestamp=datetime.now(timezone.utc).isoformat(),
                        )
                        writer.write_result(result)
                        all_results.append(result)
                    continue
            else:
                for case in batch_cases:
                    result = CaseResult(
                        case_id=case.case_id,
                        prompt_file=case.prompt_file,
                        gold_disease_id=case.gold_disease_id,
                        gold_disease_label=case.gold_disease_label,
                        error=f"inference_failed: {e}",
                        timestamp=datetime.now(timezone.utc).isoformat(),
                    )
                    writer.write_result(result)
                    all_results.append(result)
                continue

        inference_time = time.monotonic() - t0
        logger.info(
            "Batch %d inference done in %.1fs (%.2fs/case)",
            batch_idx + 1,
            inference_time,
            inference_time / len(batch_cases),
        )

        # Post-process
        batch_results = _process_batch(
            batch_cases, prompts, completions, matcher, mondo
        )

        for result in batch_results:
            writer.write_result(result)
            all_results.append(result)

    # Aggregate metrics
    logger.info("Computing aggregate metrics...")
    metrics = compute_aggregate(all_results)
    writer.write_metrics(metrics)
    writer.write_manifest(total_cases=len(all_results) + n_existing, started_at=started_at)

    # Print summary
    logger.info("=== Run complete ===")
    logger.info("Cases processed: %d", len(all_results))
    logger.info("Errors: %d (%.1f%%)", metrics.n_errors, metrics.error_rate * 100)
    logger.info("--- ID-based metrics ---")
    logger.info("  MRR: %.4f", metrics.mrr_id)
    logger.info("  Recall@1: %.4f", metrics.recall_at_1_id)
    logger.info("  Recall@3: %.4f", metrics.recall_at_3_id)
    logger.info("  Recall@5: %.4f", metrics.recall_at_5_id)
    logger.info("  Recall@10: %.4f", metrics.recall_at_10_id)
    logger.info("  Found rate: %.4f", metrics.found_rate_id)
    logger.info("--- Name-based metrics ---")
    logger.info("  MRR: %.4f", metrics.mrr_name)
    logger.info("  Recall@1: %.4f", metrics.recall_at_1_name)
    logger.info("--- ID-or-Name metrics ---")
    logger.info("  MRR: %.4f", metrics.mrr_id_or_name)
    logger.info("  Recall@1: %.4f", metrics.recall_at_1_id_or_name)
    if config.use_mondo:
        logger.info("--- Mondo metrics ---")
        logger.info("  MRR: %.4f", metrics.mrr_mondo)
        logger.info("  Recall@1: %.4f", metrics.recall_at_1_mondo)
    logger.info("--- Fuzzy match bands ---")
    logger.info("  Auto-correct (100): %d", metrics.n_fuzzy_auto_correct)
    logger.info("  Review (85-99): %d", metrics.n_fuzzy_review)
    logger.info("  Rejected (<85): %d", metrics.n_fuzzy_rejected)
    logger.info("Results: %s", writer.run_dir)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="dx-bench: LLM differential diagnosis benchmarking")

    parser.add_argument("--config", type=str, help="Path to YAML config file")

    # Override individual settings
    parser.add_argument("--prompt-dir", type=str)
    parser.add_argument("--ground-truth", type=str)
    parser.add_argument("--benchmark-ids", type=str)
    parser.add_argument("--output-dir", type=str)
    parser.add_argument("--model", type=str)
    parser.add_argument("--backend", type=str)
    parser.add_argument("--api-base-url", type=str)
    parser.add_argument("--api-key", type=str)
    parser.add_argument("--max-tokens", type=int)
    parser.add_argument("--temperature", type=float)
    parser.add_argument("--batch-size", type=int)
    parser.add_argument("--request-timeout-s", type=int)
    parser.add_argument("--empty-completion-retries", type=int)
    parser.add_argument("--tensor-parallel-size", type=int)
    parser.add_argument("--gpu-memory-utilization", type=float)
    parser.add_argument(
        "--gpu-ids",
        type=str,
        help="Comma-separated GPU indices to use, e.g. '0' or '0,1,2'. "
             "Sets CUDA_VISIBLE_DEVICES before vLLM initializes.",
    )
    parser.add_argument("--limit", type=int, help="Process only first N cases")
    parser.add_argument("--offset", type=int)
    parser.add_argument("--no-resume", action="store_true")
    parser.add_argument("--no-mondo", action="store_true")
    parser.add_argument("--mondo-db", type=str)
    parser.add_argument("--seed", type=int)
    parser.add_argument(
        "--tokenizer-name",
        type=str,
        help="HuggingFace tokenizer name for client-side chat template "
             "(completions_chat backend). Defaults to --model.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # Load base config from YAML if provided
    if args.config:
        config = RunConfig.from_yaml(args.config)
    else:
        # Require at least prompt-dir, ground-truth, benchmark-ids, output-dir
        config = RunConfig(
            prompt_dir=args.prompt_dir or "",
            ground_truth_file=args.ground_truth or "",
            benchmark_ids_file=args.benchmark_ids or "",
            output_dir=args.output_dir or "results",
        )

    # Apply CLI overrides
    if args.prompt_dir:
        config.prompt_dir = Path(args.prompt_dir)
    if args.ground_truth:
        config.ground_truth_file = Path(args.ground_truth)
    if args.benchmark_ids:
        config.benchmark_ids_file = Path(args.benchmark_ids)
    if args.output_dir:
        config.output_dir = Path(args.output_dir)
    if args.model:
        config.model_name = args.model
    if args.backend:
        config.backend = args.backend
    if args.api_base_url:
        config.api_base_url = args.api_base_url
    if args.api_key:
        config.api_key = args.api_key
    if args.max_tokens:
        config.max_tokens = args.max_tokens
    if args.temperature is not None:
        config.temperature = args.temperature
    if args.batch_size:
        config.batch_size = args.batch_size
    if args.request_timeout_s:
        config.request_timeout_s = args.request_timeout_s
    if args.empty_completion_retries is not None:
        config.empty_completion_retries = args.empty_completion_retries
    if args.tensor_parallel_size:
        config.tensor_parallel_size = args.tensor_parallel_size
    if args.gpu_memory_utilization:
        config.gpu_memory_utilization = args.gpu_memory_utilization
    if args.limit:
        config.limit = args.limit
    if args.offset:
        config.offset = args.offset
    if args.no_resume:
        config.resume = False
    if args.no_mondo:
        config.use_mondo = False
    if args.mondo_db:
        config.mondo_db_path = args.mondo_db
    if args.seed:
        config.seed = args.seed
    if args.gpu_ids:
        config.gpu_ids = [int(g.strip()) for g in args.gpu_ids.split(",")]
    if args.tokenizer_name:
        config.tokenizer_name = args.tokenizer_name

    run(config)


if __name__ == "__main__":
    main()
