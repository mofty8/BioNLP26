#!/usr/bin/env bash
# PhenoDP retrieve + Gemma-4-31B pp2prompt_v2 rerank on leftover allG2P cases.
#
# Input: datasets/RareBench_min/data/ALLG2P_LEFTOVER.jsonl
#   - 294 cases remaining from the augmented 2248-case allG2P universe
#   - excludes cases already covered by ALLG2P.jsonl (1771) and ALLG2P_REM.jsonl (183)
#
# PP2Prompt narratives: PP2Prompt/prompts/archive2_merged_en/ALLG2P_LEFTOVER_XXXX_en-prompt.txt
# Writes into runs/final_runs to keep these leftovers grouped with the previous final runs.

set -euo pipefail

PYTHON_BIN="/vol/home-vol3/wbi/elmoftym/.llmg4/bin/python"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_ROOT="/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/phenodp_gemma3_candidate_ranking/runs/final_runs"
PP2PROMPT_DIR="/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/PP2Prompt/prompts/archive2_merged_en"
TOKENIZER_PATH="/vol/home-vol3/wbi/elmoftym/.cache/huggingface/hub/models--google--gemma-4-31B-it/snapshots/439edf5652646a0d1bd8b46bfdc1d3645761a445"

cd "${SCRIPT_DIR}"

"${PYTHON_BIN}" run_rarebench_api_rerank.py \
  --run-name "phenodp_gemma4_allg2p_leftover_pp2prompt_v2" \
  --data-dir "/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/datasets/RareBench_min/data" \
  --subsets "ALLG2P_LEFTOVER" \
  --output-root "${OUTPUT_ROOT}" \
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
  2>&1 | tee pr_gemma4_allg2p_leftover_pp2prompt_v2.log
