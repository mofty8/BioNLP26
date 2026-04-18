#!/usr/bin/env bash
# Rerank-only run with prompt v3 using Gemma3-27B, negative HPOs excluded.
# Reuses retrieval candidates from runs/phenodp_gemma3_prompt_v3_full_rerank
# Uses the FULL 6901-case benchmark_ids from the v7 full rerank run.
# Saves to a NEW run dir: runs/phenodp_gemma3_v3_no_neg_hpo_<timestamp>
# Does NOT touch any previous results.

set -euo pipefail

PYTHON_BIN="/vol/home-vol3/wbi/elmoftym/.LLMS2/bin/python"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RESUME_RUN_DIR="runs/phenodp_gemma3_prompt_v3_full_rerank"
FULL_IDS="runs/phenodp_gemma3_v7_full_rerank_20260407_192822/benchmark_ids.txt"

export CUDA_VISIBLE_DEVICES=1,2
export VLLM_USE_V1=0
export CUDA_DEVICE_ORDER=PCI_BUS_ID

cd "${SCRIPT_DIR}"

TIMESTAMP=$(date -u +%Y%m%d_%H%M%S)
NEW_RUN_DIR="runs/phenodp_gemma3_v3_no_neg_hpo_${TIMESTAMP}"
mkdir -p "${NEW_RUN_DIR}/candidate_sets"
cp "${RESUME_RUN_DIR}/candidate_sets/phenodp_candidates_top50.jsonl" "${NEW_RUN_DIR}/candidate_sets/"
cp "${FULL_IDS}" "${NEW_RUN_DIR}/benchmark_ids.txt"
echo "Run dir: ${NEW_RUN_DIR}"

"${PYTHON_BIN}" run_phenodp_benchmark.py \
  --stage rerank \
  --resume-run-dir "${NEW_RUN_DIR}" \
  --run-name "phenodp_gemma3_v3_no_neg_hpo" \
  --benchmark-ids-path "${NEW_RUN_DIR}/benchmark_ids.txt" \
  --retrieve-k 50 \
  --rerank-cutoffs 3,5,10 \
  --llm-model google/gemma-3-27b-it \
  --phenodp-device cpu \
  --tensor-parallel-size 2 \
  --gpu-memory-utilization 0.85 \
  --max-tokens 700 \
  --llm-batch-size 64 \
  --prompt-no-genes \
  --prompt-include-demographics \
  --prompt-version v3 \
  2>&1 | tee pr_gemma3_v3_no_neg_hpo.log
