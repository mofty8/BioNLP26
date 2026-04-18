#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path

from phenodp_gemma3_pipeline import LLMOptions, PromptOptions, RunConfig, run_pipeline


DEFAULT_DATA_DIR = "/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/PP_LLM/phenopackets_extracted/0.1.25"
DEFAULT_PROJECT_ROOT = "/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/phenodp_gemma3_candidate_ranking"
DEFAULT_PHENODP_REPO_ROOT = "/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/PehnoPacketPhenoDP/PhenoDP"
DEFAULT_PHENODP_DATA_DIR = "/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/PehnoPacketPhenoDP/PhenoDP/data"
DEFAULT_PHENODP_HPO_DIR = "/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/PehnoPacketPhenoDP/PhenoDP/data/hpo_latest"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PhenoDP retrieval + Gemma 3 reranking benchmark.")
    parser.add_argument("--run-name", default="phenodp_gemma3_candidate_ranking")
    parser.add_argument("--data-dir", default=DEFAULT_DATA_DIR)
    parser.add_argument("--output-root", default=str(Path(DEFAULT_PROJECT_ROOT) / "runs"))
    parser.add_argument("--phenodp-repo-root", default=DEFAULT_PHENODP_REPO_ROOT)
    parser.add_argument("--phenodp-data-dir", default=DEFAULT_PHENODP_DATA_DIR)
    parser.add_argument("--phenodp-hpo-dir", default=DEFAULT_PHENODP_HPO_DIR)
    parser.add_argument("--phenodp-ic-type", default="omim", choices=["omim", "orpha"])
    parser.add_argument("--phenodp-device", default="cpu", choices=["cpu", "cuda"])
    parser.add_argument("--stage", default="all", choices=["all", "retrieve", "rerank"])
    parser.add_argument("--resume-run-dir", default="")
    parser.add_argument("--retrieve-k", type=int, default=50)
    parser.add_argument("--rerank-cutoffs", default="3,5,10")
    parser.add_argument("--llm-model", default="google/gemma-3-27b-it")
    parser.add_argument("--tensor-parallel-size", type=int, default=2)
    parser.add_argument("--gpu-memory-utilization", type=float, default=0.90)
    parser.add_argument("--dtype", default="bfloat16")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--top-p", type=float, default=1.0)
    parser.add_argument("--max-tokens", type=int, default=400)
    parser.add_argument("--llm-batch-size", type=int, default=64)
    parser.add_argument("--max-cases", type=int, default=0, help="0 means all cases.")
    parser.add_argument("--benchmark-ids-path", default="")
    parser.add_argument("--min-phenotypes", type=int, default=1)
    parser.add_argument("--include-excluded-phenotypes", action="store_true")
    parser.add_argument("--skip-rerank", action="store_true")
    parser.add_argument("--max-phenotypes-in-prompt", type=int, default=30)
    parser.add_argument("--max-negative-phenotypes-in-prompt", type=int, default=20)
    parser.add_argument("--max-genes-in-prompt", type=int, default=20)
    parser.add_argument("--prompt-no-genes", action="store_true")
    parser.add_argument("--prompt-no-negative-phenotypes", action="store_true")
    parser.add_argument("--prompt-no-demographics", action="store_true")
    parser.add_argument("--prompt-include-negative-phenotypes", action="store_true")
    parser.add_argument("--prompt-include-demographics", action="store_true")
    parser.add_argument("--qualitative-examples", type=int, default=5)
    parser.add_argument("--prompt-version", default="v3", choices=["v3", "v4", "v5", "v6", "v7", "pp2prompt", "pp2prompt_v2"])
    parser.add_argument("--pp2prompt-dir", default=None,
                        help="Directory of pre-generated PP2Prompt .txt files (required for --prompt-version pp2prompt).")
    parser.add_argument("--max-model-len", type=int, default=None,
                        help="vLLM max_model_len (prompt+output tokens). Set explicitly to cap KV cache usage.")
    parser.add_argument("--retrieval-pr-rescoring", action="store_true",
                        help="Rescore retrieval candidates using HPO annotation recall/precision.")
    parser.add_argument("--retrieval-recall-weight", type=float, default=1.0,
                        help="Weight for z-scored recall in precision-recall rescoring (default: 1.0).")
    parser.add_argument("--retrieval-precision-penalty", type=float, default=0.5,
                        help="Weight for z-scored precision penalty in rescoring (default: 0.5).")
    parser.add_argument("--include-hpo-annotations", action="store_true",
                        help="Include HPO phenotype-frequency annotations per candidate in the prompt.")
    parser.add_argument("--max-annotations-per-candidate", type=int, default=10,
                        help="Max HPO annotations shown per candidate disease.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    cutoffs = [int(value) for value in args.rerank_cutoffs.split(",") if value.strip()]

    prompt_options = PromptOptions(
        max_phenotypes=args.max_phenotypes_in_prompt,
        max_negative_phenotypes=args.max_negative_phenotypes_in_prompt,
        max_genes=args.max_genes_in_prompt,
        include_genes=not args.prompt_no_genes,
        include_negative_phenotypes=(not args.prompt_no_negative_phenotypes) or args.prompt_include_negative_phenotypes,
        include_demographics=(not args.prompt_no_demographics) or args.prompt_include_demographics,
        include_hpo_annotations=args.include_hpo_annotations,
        max_annotations_per_candidate=args.max_annotations_per_candidate,
        prompt_version=args.prompt_version,
        pp2prompt_dir=args.pp2prompt_dir,
    )
    llm_options = LLMOptions(
        model=args.llm_model,
        tensor_parallel_size=args.tensor_parallel_size,
        gpu_memory_utilization=args.gpu_memory_utilization,
        dtype=args.dtype,
        temperature=args.temperature,
        top_p=args.top_p,
        max_tokens=args.max_tokens,
        max_model_len=args.max_model_len,
    )
    cfg = RunConfig(
        run_name=args.run_name,
        data_dir=args.data_dir,
        output_root=args.output_root,
        phenodp_repo_root=args.phenodp_repo_root,
        phenodp_data_dir=args.phenodp_data_dir,
        phenodp_hpo_dir=args.phenodp_hpo_dir,
        llm_options=llm_options,
        prompt_options=prompt_options,
        retrieve_k=args.retrieve_k,
        rerank_cutoffs=cutoffs,
        llm_batch_size=args.llm_batch_size,
        max_cases=(None if args.max_cases <= 0 else args.max_cases),
        benchmark_ids_path=(args.benchmark_ids_path or None),
        min_phenotypes=args.min_phenotypes,
        include_excluded_phenotypes=args.include_excluded_phenotypes,
        skip_rerank=args.skip_rerank,
        qualitative_examples_n=args.qualitative_examples,
        phenodp_ic_type=args.phenodp_ic_type,
        phenodp_device=args.phenodp_device,
        stage=args.stage,
        resume_run_dir=(args.resume_run_dir or None),
        retrieval_precision_recall_rescoring=args.retrieval_pr_rescoring,
        retrieval_recall_weight=args.retrieval_recall_weight,
        retrieval_precision_penalty_weight=args.retrieval_precision_penalty,
    )
    run_dir = run_pipeline(cfg, verbose=True)
    print(run_dir)


if __name__ == "__main__":
    main()
