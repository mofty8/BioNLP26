#!/usr/bin/env bash
# V5 part B — GPU 1 only, TP=1, second half of cases
# Uses isolated run dir to avoid colliding with part_a's results.
# Candidates are symlinked from the v3 full rerank dir.
set -euo pipefail
PYTHON_BIN="/vol/home-vol3/wbi/elmoftym/.LLMS2/bin/python"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

export CUDA_VISIBLE_DEVICES=1
export VLLM_USE_V1=0
export CUDA_DEVICE_ORDER=PCI_BUS_ID

"${PYTHON_BIN}" run_phenodp_benchmark.py \
  --stage rerank \
  --resume-run-dir runs/phenodp_gemma3_prompt_v5_part_b_isolated \
  --run-name "phenodp_gemma3_prompt_v5_part_b" \
  --benchmark-ids-path runs/v5_ids_part_b.txt \
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
