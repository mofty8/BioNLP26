#!/usr/bin/env bash
# PhenoDP retrieve + Gemma-4-31B v7 rerank on archive2 datasets (MyGene2 + AllG2P).
#
# Inputs (pre-filtered, in datasets/RareBench_min/data/):
#   MYGENE2.jsonl  — 131 cases (from 146 raw; filter: >=3 HPO, PhenoDP-compatible)
#   ALLG2P.jsonl   — 1771 cases (from 3829 raw; filter: >=3 HPO, PhenoDP-compatible,
#                    definitive/strong confidence only)
#
# Uses v7 prompt (HPO-term-based) — no PP2Prompt narratives exist for these cases.
# Prereq: vLLM API server running in screen "llm2" (google/gemma-4-31B-it on port 8000).
# Always writes to a NEW timestamped run dir — never overwrites existing results.

set -euo pipefail

PYTHON_BIN="/vol/home-vol3/wbi/elmoftym/.llmg4/bin/python"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOKENIZER_PATH="/vol/home-vol3/wbi/elmoftym/.cache/huggingface/hub/models--google--gemma-4-31B-it/snapshots/439edf5652646a0d1bd8b46bfdc1d3645761a445"

cd "${SCRIPT_DIR}"

"${PYTHON_BIN}" run_rarebench_api_rerank.py \
  --run-name "phenodp_gemma4_archive2_v7" \
  --data-dir "/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/datasets/RareBench_min/data" \
  --subsets "MYGENE2,ALLG2P" \
  --api-base "http://127.0.0.1:8000/v1" \
  --api-key "local-token" \
  --api-model "google/gemma-4-31B-it" \
  --max-tokens 400 \
  --retrieve-k 50 \
  --rerank-cutoffs 3,5,10 \
  --max-api-workers 16 \
  --prompt-version v7 \
  --method-prefix "reranker_gemma4" \
  --phenodp-device cpu \
  --use-completions \
  --tokenizer "${TOKENIZER_PATH}" \
  2>&1 | tee pr_gemma4_archive2_v7.log
