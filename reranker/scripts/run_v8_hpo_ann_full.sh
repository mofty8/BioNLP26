#!/bin/bash
source /vol/home-vol3/wbi/elmoftym/.LLMS2/bin/activate
export CUDA_VISIBLE_DEVICES=0

cd /vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/phenodp_gemma3_candidate_ranking

python run_phenodp_benchmark.py \
  --run-name "phenodp_gemma3_v8_hpo_ann_full" \
  --stage rerank \
  --resume-run-dir "runs/phenodp_gemma3_v8_hpo_ann_full_20260323_034805" \
  --benchmark-ids-path "runs/phenodp_gemma3_v8_hpo_ann_full_20260323_034805/benchmark_ids.txt" \
  --rerank-cutoffs "3,5" \
  --tensor-parallel-size 1 \
  --gpu-memory-utilization 0.85 \
  --max-tokens 500 \
  --llm-batch-size 64 \
  --prompt-no-genes \
  --include-hpo-annotations \
  --max-annotations-per-candidate 10

echo "=== V8 HPO ANN FULL RUN COMPLETED ==="
