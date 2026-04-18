#!/usr/bin/env bash
# V5 part A — GPU 0 only, TP=1, first half of cases
set -euo pipefail
PYTHON_BIN="/vol/home-vol3/wbi/elmoftym/.LLMS2/bin/python"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

export CUDA_VISIBLE_DEVICES=0
export VLLM_USE_V1=0
export CUDA_DEVICE_ORDER=PCI_BUS_ID

"${PYTHON_BIN}" run_phenodp_benchmark.py \
  --stage rerank \
  --resume-run-dir runs/phenodp_gemma3_prompt_v3_full_rerank \
  --run-name "phenodp_gemma3_prompt_v5_part_a" \
  --benchmark-ids-path runs/v5_ids_part_a.txt \
  --retrieve-k 50 \
  --rerank-cutoffs 3,5,10 \
  --llm-model google/gemma-3-27b-it \
  --phenodp-device cpu \
  --tensor-parallel-size 1 \
  --gpu-memory-utilization 0.75 \
  --max-tokens 700 \
  --llm-batch-size 64 \
  --prompt-no-genes \
  --prompt-include-negative-phenotypes \
  --prompt-include-demographics \
  --prompt-version v5
