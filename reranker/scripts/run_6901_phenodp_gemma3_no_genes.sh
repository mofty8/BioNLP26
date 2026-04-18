#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/phenodp_gemma3_candidate_ranking"
PYTHON_BIN="/vol/home-vol3/wbi/elmoftym/.LLMS2/bin/python"
BENCH_IDS="$PROJECT_ROOT/benchmark_ids_6901_phenodp_compatible_min3hpo.txt"

cd "$PROJECT_ROOT"

"$PYTHON_BIN" run_phenodp_benchmark.py \
  --run-name "phenodp_gemma3_6901_no_genes" \
  --benchmark-ids-path "$BENCH_IDS" \
  --retrieve-k 50 \
  --rerank-cutoffs 3,5,10 \
  --llm-model "google/gemma-3-27b-it" \
  --phenodp-device cpu \
  --tensor-parallel-size 1 \
  --gpu-memory-utilization 0.80 \
  --llm-batch-size 8 \
  --prompt-no-genes \
  --prompt-include-negative-phenotypes \
  --prompt-include-demographics
