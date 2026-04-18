# Experiment 1: Baseline Retriever (PhenoDP top-50)

## Setup
- **Retriever**: PhenoDP with IC-weighted phenotype matching + PCL_HPOEncoder embeddings
- **Candidates**: Top-50 per patient
- **Benchmark**: 6,901 phenopacket cases (500 unique OMIM diseases, min 3 HPO terms)
- **No genes used** in retrieval (phenotype-only)

## Results (ID-correct)

| Metric | Value |
|--------|------:|
| Hit@1 | 51.24% |
| Hit@3 | 63.27% |
| Hit@5 | 67.19% |
| Hit@10 | 71.92% |
| Found in top-50 | 81.48% |
| MRR | 0.5855 |

## Interpretation

The retriever establishes a strong baseline: rank-1 is correct more than half the time, and the true diagnosis is within the top-50 candidates 81.5% of the time. This is the ceiling for any reranking approach -- if the correct answer isn't retrieved, no reranker can find it.

The gap between Hit@1 (51.2%) and Found (81.5%) represents the 30.3% of cases where the correct answer is retrieved but not at rank-1. This is the theoretical maximum improvement a perfect reranker could achieve.

## Run Directory
`runs/phenodp_gemma3_6901_no_genes_twostage_20260319_054012_20260319_044040/`

## Result Files
- `methods/retriever_phenodp_top50/summary.json`
- `benchmark_summary.json`
