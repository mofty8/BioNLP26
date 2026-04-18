#!/usr/bin/env bash
# Prompt v4 rerank — reuses retriever candidates from the v3 full run.
# Changes vs v3: hard score-gap gate, strict Condition A verification,
# biological-impossibility Condition B, numbered-subtype rule.
set -euo pipefail

PROJECT_ROOT="/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/phenodp_gemma3_candidate_ranking"
PYTHON_BIN="/vol/home-vol3/wbi/elmoftym/.LLMS2/bin/python"

# Reuse the retriever candidates produced by the v3 run
RESUME_RUN_DIR="${PROJECT_ROOT}/runs/phenodp_gemma3_prompt_v3_full_rerank"
BENCHMARK_IDS="${PROJECT_ROOT}/runs/phenodp_gemma3_prompt_v3_full_rerank/benchmark_ids.txt"

RUN_NAME="phenodp_gemma3_prompt_v4_full_rerank"

cd "${PROJECT_ROOT}"

export CUDA_VISIBLE_DEVICES=0,1,2,3
export VLLM_USE_V1=0
export CUDA_DEVICE_ORDER=PCI_BUS_ID

echo "[v4] starting rerank stage (prompt v4, top-3/5/10, no genes, TP=4 across all GPUs)"

"${PYTHON_BIN}" run_phenodp_benchmark.py \
  --stage rerank \
  --resume-run-dir "${RESUME_RUN_DIR}" \
  --run-name "${RUN_NAME}" \
  --benchmark-ids-path "${BENCHMARK_IDS}" \
  --retrieve-k 50 \
  --rerank-cutoffs 3,5,10 \
  --llm-model google/gemma-3-27b-it \
  --phenodp-device cpu \
  --tensor-parallel-size 4 \
  --gpu-memory-utilization 0.21 \
  --max-tokens 600 \
  --llm-batch-size 32 \
  --prompt-no-genes \
  --prompt-include-negative-phenotypes \
  --prompt-include-demographics \
  --prompt-version v4

echo "[v4] done"
