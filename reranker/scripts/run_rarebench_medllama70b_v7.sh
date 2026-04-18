#!/usr/bin/env bash
# Full PhenoDP retrieve + MedLlama70B v7 rerank on RareBench (HMS, MME, RAMEDIS, LIRICAL).
# Prereq: vLLM API server running in screen "llm" on this machine
#   (m42-health/Llama3-Med42-70B on port 8000).
# Always writes to a NEW timestamped run dir — never overwrites existing results.

set -euo pipefail

PYTHON_BIN="/vol/home-vol3/wbi/elmoftym/.LLMS2/bin/python"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cd "${SCRIPT_DIR}"

"${PYTHON_BIN}" run_rarebench_api_rerank.py \
  --run-name "phenodp_medllama70b_rarebench_v7" \
  --subsets "HMS,MME,RAMEDIS,LIRICAL" \
  --api-base "http://127.0.0.1:8000/v1" \
  --api-key "local-token" \
  --api-model "m42-health/Llama3-Med42-70B" \
  --max-tokens 200 \
  --retrieve-k 50 \
  --rerank-cutoffs 3,5,10 \
  --max-api-workers 16 \
  --prompt-version v7 \
  --method-prefix "reranker_medllama70b" \
  --phenodp-device cpu \
  2>&1 | tee rarebench_medllama70b_v7.log
