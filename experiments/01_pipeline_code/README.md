# Pipeline Code

Symlinks to the core pipeline modules. The actual code lives in `../phenodp_gemma3_pipeline/`.

## Key Files

| File | Purpose |
|------|---------|
| `prompting.py` | All prompt templates (v3 fallback, v4, v5, v6, HPO annotation variant) |
| `rerankers.py` | vLLM-based LLM reranker (Gemma 3, Llama 3.3 70B) |
| `experiment.py` | End-to-end experiment runner (retrieval + reranking + evaluation) |
| `metrics.py` | Hit@K, MRR computation under three correctness criteria |
| `models.py` | Data classes: PatientCase, DiseaseCandidate, Truth |
| `data_loader.py` | Phenopacket JSON loader |
| `hpo_annotations.py` | HPO annotation store for phenotype.hpoa integration |
| `phenodp_retriever.py` | PhenoDP wrapper with precision-recall rescoring |
| `run_phenodp_benchmark.py` | CLI entry point for running benchmarks |

## Environment

- Python environment: `/vol/home-vol3/wbi/elmoftym/.LLMS2`
- LLM inference: vLLM with bfloat16, tensor parallelism
- PhenoDP: custom fork at `../PehnoPacketPhenoDP/PhenoDP`
