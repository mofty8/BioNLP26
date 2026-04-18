# PhenoDP Gemma 3 Candidate Ranking

Separate benchmark project for phenotype candidate ranking with:

- `PhenoDP` as the retriever
- `Gemma 3` as the reranker
- persisted candidate sets, predictions, logs, and evaluation summaries

## Environment

Use the existing Python environment at:

- `/vol/home-vol3/wbi/elmoftym/.LLMS2`

## Default data sources

- Phenopackets: `/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/PP_LLM/phenopackets_extracted/0.1.25`
- PhenoDP repo: `/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/PehnoPacketPhenoDP/PhenoDP`
- PhenoDP data: `/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/PehnoPacketPhenoDP/PhenoDP/data`
- PhenoDP HPO data: `/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/PehnoPacketPhenoDP/PhenoDP/data/hpo_latest`

## Run

Retrieval-only sanity check:

```bash
/vol/home-vol3/wbi/elmoftym/.LLMS2/bin/python run_phenodp_benchmark.py \
  --skip-rerank \
  --max-cases 5
```

Full retrieval + Gemma 3 reranking:

```bash
/vol/home-vol3/wbi/elmoftym/.LLMS2/bin/python run_phenodp_benchmark.py \
  --llm-model google/gemma-3-27b-it \
  --retrieve-k 50 \
  --rerank-cutoffs 3,5,10 \
  --phenodp-device cuda \
  --tensor-parallel-size 1
```

## Outputs

Each run writes a self-contained folder under `runs/` with:

- `run_config.json`
- `environment.json`
- `benchmark_ids.txt`
- `run.log`
- `candidate_sets/`
- `methods/retriever_phenodp_topK/results.csv`
- `methods/retriever_phenodp_topK/summary.json`
- `methods/reranker_gemma3_top3|top5|top10/results.csv`
- `methods/reranker_gemma3_top3|top5|top10/summary.json`
- `methods/reranker_gemma3_top*/logs/*.txt`
- `methods/reranker_gemma3_top*/qualitative_examples.md`
- `benchmark_summary.csv`
- `benchmark_summary.json`

## Evaluation

Retriever and reranker are both evaluated at:

- `Hit@1`
- `Hit@3`
- `Hit@5`
- `Hit@10`

Under three correctness criteria:

- `ID correct`
- `ID + name correct`
- `ID or name correct`

Name matching uses normalized exact matching with a high-confidence fuzzy fallback (`rapidfuzz >= 95`).
