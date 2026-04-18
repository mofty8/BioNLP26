#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/phenodp_gemma3_candidate_ranking"
PYTHON_BIN="/vol/home-vol3/wbi/elmoftym/.LLMS2/bin/python"
BENCHMARK_IDS="${PROJECT_ROOT}/benchmark_ids_6901_phenodp_compatible_min3hpo.txt"
RUN_NAME="${1:-phenodp_gemma3_6901_pos_hpo_only_twostage}"

cd "${PROJECT_ROOT}"

COMMON_ARGS=(
  --run-name "${RUN_NAME}"
  --benchmark-ids-path "${BENCHMARK_IDS}"
  --retrieve-k 50
  --rerank-cutoffs 3,5,10
  --llm-model google/gemma-3-27b-it
  --phenodp-device cpu
  --tensor-parallel-size 1
  --gpu-memory-utilization 0.80
  --llm-batch-size 8
  --prompt-no-genes
  --prompt-no-negative-phenotypes
  --prompt-no-demographics
)

RETRIEVE_CMD=(
  "${PYTHON_BIN}" run_phenodp_benchmark.py
  --stage retrieve
  "${COMMON_ARGS[@]}"
)

echo "[two-stage] starting retrieval stage for run name: ${RUN_NAME}"
RUN_DIR="$(${RETRIEVE_CMD[@]} | tail -n 1)"
echo "[two-stage] retrieval run dir: ${RUN_DIR}"

export CUDA_VISIBLE_DEVICES=0
export VLLM_USE_V1=0

RERANK_CMD=(
  "${PYTHON_BIN}" run_phenodp_benchmark.py
  --stage rerank
  --resume-run-dir "${RUN_DIR}"
  "${COMMON_ARGS[@]}"
)

echo "[two-stage] starting rerank stage on GPU 0"
"${RERANK_CMD[@]}"
