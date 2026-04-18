#!/usr/bin/env bash
# Full PhenoDP retrieve + Gemma-3-27B v7 rerank on RareBench (HMS, MME, RAMEDIS, LIRICAL).
# Prereq: vLLM API server running in screen "llm" on this machine
#   (google/gemma-3-27b-it on port 8000).
# Always writes to a NEW timestamped run dir — never overwrites existing results.

set -euo pipefail

PYTHON_BIN="/vol/home-vol3/wbi/elmoftym/.LLMS2/bin/python"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cd "${SCRIPT_DIR}"

"${PYTHON_BIN}" run_rarebench_api_rerank.py \
  --run-name "phenodp_gemma3_rarebench_v7" \
  --subsets "HMS,MME,RAMEDIS,LIRICAL" \
  --api-base "http://127.0.0.1:8000/v1" \
  --api-key "local-token" \
  --api-model "google/gemma-3-27b-it" \
  --max-tokens 200 \
  --retrieve-k 50 \
  --rerank-cutoffs 3,5,10 \
  --max-api-workers 16 \
  --prompt-version v7 \
  --method-prefix "reranker_gemma3" \
  --phenodp-device cpu \
  2>&1 | tee rarebench_gemma3_v7.log
