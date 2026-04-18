#!/usr/bin/env bash
# Rerank-only run with pp2prompt_v2 using Gemma3-27B on the full 6901 phenopacket benchmark.
# Reuses retrieval candidates from runs/phenodp_gemma3_v6_full_rerank.
# Uses completions API (chat template applied client-side) + name_match fallback parser.
# Prereq: vLLM API server running in screen "llm" (google/gemma-3-27b-it on port 8000).
# Always writes to a NEW timestamped run dir — never overwrites existing results.

set -euo pipefail

PYTHON_BIN="/vol/home-vol3/wbi/elmoftym/.LLMS2/bin/python"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RESUME_RUN_DIR="runs/phenodp_gemma3_v6_full_rerank"
PP2PROMPT_DIR="/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/PP2Prompt/prompts/en"

cd "${SCRIPT_DIR}"

"${PYTHON_BIN}" run_phenodp_api_rerank.py \
  --run-name "phenodp_gemma3_pp2prompt_v2_full_rerank" \
  --resume-run-dir "${RESUME_RUN_DIR}" \
  --api-base "http://127.0.0.1:8000/v1" \
  --api-key "local-token" \
  --api-model "google/gemma-3-27b-it" \
  --max-tokens 400 \
  --retrieve-k 50 \
  --rerank-cutoffs 3,5,10 \
  --llm-batch-size 8 \
  --max-api-workers 16 \
  --prompt-version pp2prompt_v2 \
  --pp2prompt-dir "${PP2PROMPT_DIR}" \
  --method-prefix "reranker_gemma3" \
  --use-completions \
  --tokenizer google/gemma-3-27b-it \
  2>&1 | tee pr_gemma3_pp2prompt_v2_rerank.log
