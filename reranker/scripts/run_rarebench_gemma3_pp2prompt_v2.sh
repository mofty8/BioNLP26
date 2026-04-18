#!/usr/bin/env bash
# PhenoDP retrieve + Gemma-3-27B pp2prompt_v2 rerank on RareBench (HMS, MME, RAMEDIS, LIRICAL).
# Uses pre-generated PP2Prompt narratives as the base prompt with conservative reranking guidance.
# Prereq: vLLM API server running in screen "llm" (google/gemma-3-27b-it on port 8000).
# Always writes to a NEW timestamped run dir — never overwrites existing results.

set -euo pipefail

PYTHON_BIN="/vol/home-vol3/wbi/elmoftym/.LLMS2/bin/python"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PP2PROMPT_DIR="/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/PP2Prompt/prompts/rarebench_merged_en"

cd "${SCRIPT_DIR}"

"${PYTHON_BIN}" run_rarebench_api_rerank.py \
  --run-name "phenodp_gemma3_rarebench_pp2prompt_v2" \
  --subsets "HMS,MME,RAMEDIS,LIRICAL" \
  --api-base "http://127.0.0.1:8000/v1" \
  --api-key "local-token" \
  --api-model "google/gemma-3-27b-it" \
  --max-tokens 400 \
  --retrieve-k 50 \
  --rerank-cutoffs 3,5,10 \
  --max-api-workers 16 \
  --prompt-version pp2prompt_v2 \
  --pp2prompt-dir "${PP2PROMPT_DIR}" \
  --method-prefix "reranker_gemma3" \
  --phenodp-device cpu \
  --use-completions \
  --tokenizer google/gemma-3-27b-it \
  2>&1 | tee rarebench_gemma3_pp2prompt_v2.log
