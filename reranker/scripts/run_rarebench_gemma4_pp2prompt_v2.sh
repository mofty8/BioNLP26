#!/usr/bin/env bash
# PhenoDP retrieve + Gemma-4-31B pp2prompt_v2 rerank on RareBench (HMS, MME, RAMEDIS, LIRICAL).
# Uses pre-generated PP2Prompt narratives as the base prompt with conservative reranking guidance.
# Prereq: vLLM API server running in screen "llm" (google/gemma-4-31B-it on port 8000).
# Always writes to a NEW timestamped run dir — never overwrites existing results.

set -euo pipefail

PYTHON_BIN="/vol/home-vol3/wbi/elmoftym/.llmg4/bin/python"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PP2PROMPT_DIR="/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/PP2Prompt/prompts/rarebench_merged_en"
TOKENIZER_PATH="/vol/home-vol3/wbi/elmoftym/.cache/huggingface/hub/models--google--gemma-4-31B-it/snapshots/439edf5652646a0d1bd8b46bfdc1d3645761a445"

cd "${SCRIPT_DIR}"

"${PYTHON_BIN}" run_rarebench_api_rerank.py \
  --run-name "phenodp_gemma4_rarebench_pp2prompt_v2" \
  --subsets "HMS,MME,RAMEDIS,LIRICAL" \
  --api-base "http://127.0.0.1:8000/v1" \
  --api-key "local-token" \
  --api-model "google/gemma-4-31B-it" \
  --max-tokens 400 \
  --retrieve-k 50 \
  --rerank-cutoffs 3,5,10 \
  --max-api-workers 16 \
  --prompt-version pp2prompt_v2 \
  --pp2prompt-dir "${PP2PROMPT_DIR}" \
  --method-prefix "reranker_gemma4" \
  --phenodp-device cpu \
  --use-completions \
  --tokenizer "${TOKENIZER_PATH}" \
  2>&1 | tee pr_gemma4_rarebench_pp2prompt_v2.log
