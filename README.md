# Phenotype Retrieval Outperforms LLM Reasoning for Rare Disease Diagnosis

Code and results for the BioNLP @ ACL 2026 paper.

**Core finding:** On a 6,901-case rare-disease benchmark, phenotype-based retrieval (PhenoDP) substantially outperforms open-ended LLM diagnosis on exact-ID Hit@1. LLM reranking over retrieved candidates does not improve over the retriever alone.

---

## Repository Structure

```
BioNLP26/
├── reranker/               PhenoDP + LLM candidate reranking pipeline
│   ├── phenodp_gemma3_pipeline/   Python package
│   ├── run_phenodp_benchmark.py   Main entrypoint
│   ├── scripts/            Bash run scripts for all experiments
│   └── data/               Benchmark IDs, dataset audit
│
├── dx_bench/               Direct LLM diagnosis evaluation pipeline
│   ├── dx_bench/           Python package
│   └── scripts/            Run scripts
│
├── results/
│   ├── reranker/
│   │   ├── phenopacket_6901/  Benchmark summaries for main dataset
│   │   ├── rarebench/         Benchmark summaries for RareBench subsets
│   │   └── archive2/          Archive2 dataset results (MyGene2, allG2P)
│   └── dx_bench/
│       └── selected_runs/     Per-model × dataset metrics.json
│
├── analysis/
│   ├── reranking_analysis/    Promotion/demotion, bootstrap CI, error analysis
│   └── datasets_analysis/     Dataset characterization figures and tables
│
└── experiments/               Paper experiment packages (numbered)
    ├── 01_pipeline_code/
    ├── 02_prompts/
    ├── 03_experiments/        exp1–exp9 with code, logs, and results
    ├── 04_external_benchmarks/
    ├── 05_dataset_analysis/
    ├── 06_failure_analysis/
    ├── 07_results_summary/
    └── 08_paper_writeup/
```

---

## Paradigms Compared

| Paradigm | Description |
|---|---|
| Phenotype retrieval | PhenoDP IC-weighted retrieval, no LLM |
| Candidate reranking | PhenoDP top-k → Gemma3/Gemma4/Llama70b reranks |
| Direct LLM diagnosis | Open-ended generation from HPO prompt (dx_bench) |

---

## Datasets

- **Phenopacket** (6,901 cases, min 3 HPO terms) — main benchmark
- **RareBench**: HMS (~68), LIRICAL (370), MME (40), RAMEDIS (624)
- **Archive2**: MyGene2, allG2P (supplementary, out of main paper scope)

---

## Reproducing the Main Benchmark

### Reranker (PhenoDP + LLM)
```bash
cd reranker/
pip install -e .
# Baseline retriever (no LLM)
python run_phenodp_benchmark.py --retriever-only \
    --benchmark-ids data/benchmark_ids_6901_phenodp_compatible_min3hpo.txt

# Full rerank with Gemma3 (v7 prompt)
bash scripts/run_gemma3_v7_full.sh
```

### Direct LLM Diagnosis
```bash
cd dx_bench/
pip install -e .
python scripts/run_dataset_suite.py --config config.yaml --dataset phenopacket
```

---

## Key Results

See `results/reranker/phenopacket_6901/` for benchmark summaries.  
See `results/dx_bench/selected_runs/` for direct LLM diagnosis metrics.  
See `analysis/reranking_analysis/tables/` for paper tables.
