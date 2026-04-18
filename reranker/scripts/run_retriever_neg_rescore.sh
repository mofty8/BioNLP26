#!/bin/bash
source /vol/home-vol3/wbi/elmoftym/.LLMS2/bin/activate

cd /vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/phenodp_gemma3_candidate_ranking

python run_phenodp_benchmark.py \
  --run-name "phenodp_retriever_neg_rescore" \
  --stage retrieve \
  --retrieve-k 50 \
  --retrieval-neg-rescoring \
  --retrieval-neg-penalty-weight 0.15 \
  --phenodp-device cpu \
  --skip-rerank

echo "=== RETRIEVER NEG RESCORE RUN COMPLETED ==="
