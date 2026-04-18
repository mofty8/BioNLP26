#!/usr/bin/env bash
# Rerank-only run with prompt v5 (reuses v3 retriever candidates).
# Saves results to a NEW run dir: runs/phenodp_gemma3_prompt_v5_full_rerank
# Does NOT touch v3 or v4 results.

set -euo pipefail

PYTHON_BIN="/vol/home-vol3/wbi/elmoftym/.LLMS2/bin/python"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RESUME_RUN_DIR="runs/phenodp_gemma3_prompt_v3_full_rerank"   # reuse v3 retriever candidates

export CUDA_VISIBLE_DEVICES=0,1
export VLLM_USE_V1=0
export CUDA_DEVICE_ORDER=PCI_BUS_ID

cd "${SCRIPT_DIR}"

"${PYTHON_BIN}" run_phenodp_benchmark.py \
  --stage rerank \
  --resume-run-dir "${RESUME_RUN_DIR}" \
  --run-name "phenodp_gemma3_prompt_v5_full_rerank" \
  --benchmark-ids-path "${RESUME_RUN_DIR}/benchmark_ids.txt" \
  --retrieve-k 50 \
  --rerank-cutoffs 3,5,10 \
  --llm-model google/gemma-3-27b-it \
  --phenodp-device cpu \
  --tensor-parallel-size 2 \
  --gpu-memory-utilization 0.85 \
  --max-tokens 700 \
  --llm-batch-size 64 \
  --prompt-no-genes \
  --prompt-include-negative-phenotypes \
  --prompt-include-demographics \
  --prompt-version v5
