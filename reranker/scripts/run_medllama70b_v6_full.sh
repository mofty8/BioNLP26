#!/usr/bin/env bash
# Rerank the full 6901 PhenoDP candidates using Med42-70B (m42-health/Llama3-Med42-70B)
# served via vLLM API on port 8000, with prompt v6 — matches the gemma3 v6 full rerank setup.
#
# Prereqs:
#   - vLLM API server already running in screen "llm":
#       vllm serve m42-health/Llama3-Med42-70B --tensor-parallel-size 8
#         --host 127.0.0.1 --port 8000 --api-key local-token
#         --gpu-memory-utilization 0.90 --max-model-len 2048
#   - Retrieval candidates exist in: runs/phenodp_gemma3_v6_full_rerank/candidate_sets/
#
# Saves to: runs/phenodp_medllama70b_v6_full_rerank_<timestamp>  (new dir, no overwrites)

set -euo pipefail

PYTHON_BIN="/vol/home-vol3/wbi/elmoftym/.LLMS2/bin/python"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RESUME_RUN_DIR="runs/phenodp_gemma3_v6_full_rerank"

cd "${SCRIPT_DIR}"

"${PYTHON_BIN}" run_phenodp_api_rerank.py \
  --run-name "phenodp_medllama70b_v6_full_rerank" \
  --resume-run-dir "${RESUME_RUN_DIR}" \
  --benchmark-ids-path "${RESUME_RUN_DIR}/benchmark_ids.txt" \
  --api-base "http://127.0.0.1:8000/v1" \
  --api-key "local-token" \
  --api-model "m42-health/Llama3-Med42-70B" \
  --max-tokens 400 \
  --temperature 0.0 \
  --top-p 1.0 \
  --retrieve-k 50 \
  --rerank-cutoffs 3,5,10 \
  --llm-batch-size 8 \
  --max-api-workers 8 \
  --prompt-version v6 \
  --prompt-no-genes \
  --prompt-include-negative-phenotypes \
  --prompt-include-demographics \
  --method-prefix "reranker_medllama70b" \
  --qualitative-examples 5 \
  2>&1 | tee pr_medllama70b_v6_rerank.log
