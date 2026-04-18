# Consolidated Results

## Table 1: Primary Benchmark (6,901 cases, ID-correct)

| Method | H@1 | H@3 | H@5 | H@10 | MRR | Notes |
|--------|----:|----:|----:|-----:|----:|-------|
| PhenoDP Baseline (top-50) | 51.24% | 63.27% | 67.19% | 71.92% | 0.585 | Retriever only |
| Z-score PR Rescoring | 57.63% | 66.63% | 69.54% | 72.87% | 0.633 | +6.39% H@1, p=0.017* |
| MLP Signal Fusion | **59.13%** | **67.53%** | **70.15%** | **73.31%** | **0.645** | **+6.84% H@1, p=0.004** |
| Gemma 3 Reranker (v3, top-3) | 57.66% | 72.91% | -- | -- | 0.645 | 3,451 cases only |
| Gemma 3 Reranker (v6, top-3) | 51.18% | 63.27% | 63.27% | 63.27% | 0.565 | 6,901 cases |
| HPO Annotation Reranker (top-3) | 40.81% | 63.27% | 63.27% | 63.27% | 0.511 | Below baseline |

## Table 2: Prompt Demotion Subset (509 cases, ID-correct, top-3)

| Prompt | H@1 | Interpretation |
|--------|----:|----------------|
| v2 | 47.35% | Too permissive |
| **v3** | **92.53%** | **Best -- simple score-gap rule works** |
| v4 | 72.89% | Over-specified verification |
| v5 | 45.78% | Analysis paralysis |
| v6 | 14.54% | Complete over-constraint |

## Table 3: Model Comparison (100 cases, demotion+promotion, ID-correct)

| Model | Params | Prompt | H@1 (top-3) | H@1 (top-5) |
|-------|-------:|--------|----:|----:|
| **Gemma 3 27B-IT** | 27B | v6 | **74.00%** | **77.00%** |
| Llama 3.3 70B-Instruct | 70B | v5 | 50.00% | 49.00% |

## Table 4: External Benchmarks / RareBench (H@1, ID-correct)

| Method | HMS (88) | MME (40) | LIRICAL (370) | RAMEDIS (624) |
|--------|------:|------:|----------:|----------:|
| PhenoDP Baseline | 7.35% | **65.00%** | **52.70%** | 10.26% |
| Z-score PR | 1.47% | **65.00%** | 53.78% | **11.86%** |
| MLP Fusion | **10.29%** | **65.00%** | 48.38% | -- |
| Fine-tuned Encoder | 7.35% | **65.00%** | **52.70%** | -- |

## Table 5: Contrastive Encoder (Embedding-Only Signal)

| Metric | Before FT | After FT | Delta |
|--------|----------:|---------:|------:|
| H@1 (all 6,901) | 1.67% | 7.67% | +6.00% |
| H@1 (subtypes, 3,417) | 1.99% | 13.40% | +11.41% |

## Key Takeaways for Paper

### What works:
1. **Z-score PR rescoring** (+6.4% H@1, significant, simple, no LLM needed)
2. **MLP signal fusion** (+6.8% H@1, significant, best in-distribution)
3. **Prompt v3** (best LLM prompt, +6.4% H@1 on partial benchmark)

### What doesn't work:
1. **Complex prompts** (v4-v6): more constraints = worse results
2. **HPO annotations in prompt**: -10.4% H@1, information overload
3. **LLM reranking at full scale**: v6 on 6,901 cases = baseline

### What doesn't generalize:
1. **MLP fusion**: -2.93% on RareBench combined
2. **Fine-tuned encoder**: 0% delta on external benchmarks
3. **Z-score PR**: Mixed (-5.88% on HMS, +1.08% on LIRICAL)

### The core finding:
A well-calibrated retriever is hard to beat. LLM reranking adds value only when targeted at specific failure modes (subtype confusion, score-gap ambiguity) with simple rules. Complex reasoning chains and learned models overfit. The most robust improvement is the simplest: z-score normalization of retriever scores.
