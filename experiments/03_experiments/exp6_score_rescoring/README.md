# Experiment 6: Precision-Recall Score Rescoring

## Motivation
PhenoDP's default scoring combines IC-weighted phenotype matching with embedding similarity, but treats precision and recall symmetrically. In rare disease diagnosis, recall (covering the patient's phenotypes) may be more important than precision (not having extra phenotypes). This experiment introduces asymmetric rescoring.

## Setup
- **Method**: Decompose PhenoDP scores into precision and recall components, then rescore as: `score = recall - alpha * precision_penalty`
- **Z-score normalization**: Normalize phi scores and embedding similarities per-patient using z-scores before combining
- **Benchmark**: 6,901 cases, nested 5-fold CV (PMID-grouped)

## Results (Nested 5-fold CV)

| Method | H@1 | H@3 | H@5 | H@10 | MRR |
|--------|----:|----:|----:|-----:|----:|
| Baseline (PhenoDP) | 52.29% (+-5.33) | 64.27% | 68.17% | 72.89% | 0.596 |
| Z-score PR rescoring | 57.63% (+-6.43) | 66.63% | 69.54% | 72.87% | 0.633 |
| Delta | **+5.34%** | +2.36% | +1.37% | -0.02% | +0.036 |

## Pool Size Ablation

How does the rescoring pool size K affect results?

| Pool K | H@1 | H@3 | H@5 | H@10 | Delta H@1 |
|--------|----:|----:|----:|-----:|----------:|
| BL (50) | 51.24% | 63.27% | 67.19% | 71.92% | -- |
| K=10 | 56.50% | 65.48% | 68.15% | 71.92% | +5.26% |
| K=20 | 57.63% | 65.74% | 68.58% | 72.32% | +6.39% |
| K=30 | 57.64% | 65.74% | 68.69% | 72.24% | +6.40% |
| K=50 | 57.73% | 65.82% | 68.80% | 72.40% | +6.49% |

### With 200-pool (extended retrieval)

Expanding retrieval to 200 candidates then rescoring within various pool sizes:

| Pool K | H@1 | Delta H@1 |
|--------|----:|----------:|
| K=50 | 57.47% | +6.17% |
| K=100 | 57.47% | +6.17% |
| K=200 | 57.47% | +6.17% |

Beyond K=50, no additional benefit from larger pools.

### Statistical Significance (PMID-grouped 5-fold CV)

| Pool K | Mean H@1 | Std | p-value | Sig |
|--------|------:|----:|--------:|:---:|
| BL (50) | 52.29% | 5.33% | -- | -- |
| K=20 | 58.51% | 6.39% | 0.024 | * |
| K=30 | 58.54% | 6.28% | 0.021 | * |
| K=50 | 58.67% | 6.34% | 0.017 | * |

All improvements are statistically significant (p < 0.05).

## Interpretation

Z-score precision-recall rescoring is a simple, effective baseline that improves H@1 by ~6% without any LLM. The improvement comes from two sources:
1. **Z-score normalization** corrects for per-patient score scale differences
2. **Asymmetric weighting** penalizes candidates with many unmatched features (low precision for the patient)

This is purely a retriever-side improvement and is orthogonal to LLM reranking.

## Code
- `run_pool_size_ablation.py`
- `run_ablation.py`
- `phenodp_gemma3_pipeline/phenodp_retriever.py` (rescoring logic)

## Log Files
- `pool_size_ablation.log`
- `zscore_pr_run.log`
