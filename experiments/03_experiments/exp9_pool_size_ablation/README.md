# Experiment 9: Pool Size Ablation

## Question
How many retriever candidates should the rescoring operate on? Is there a sweet spot, or does performance plateau?

## Setup
- **Method**: Z-score PR rescoring applied to different pool sizes K from PhenoDP's top-50 and top-200 candidate lists
- **Benchmark**: 6,901 cases

## Results

### Part 1: Rescoring within PhenoDP's top-50

| Pool K | H@1 | H@3 | H@5 | H@10 | Delta H@1 |
|--------|----:|----:|----:|-----:|----------:|
| BL (50) | 51.24% | 63.27% | 67.19% | 71.92% | -- |
| K=10 | 56.50% | 65.48% | 68.15% | 71.92% | +5.26% |
| K=15 | 57.25% | 65.67% | 68.31% | 72.11% | +6.01% |
| K=20 | 57.63% | 65.74% | 68.58% | 72.32% | +6.39% |
| K=25 | 57.60% | 65.79% | 68.61% | 72.19% | +6.36% |
| K=30 | 57.64% | 65.74% | 68.69% | 72.24% | +6.40% |
| K=50 | 57.73% | 65.82% | 68.80% | 72.40% | +6.49% |

### Part 2: Rescoring within PhenoDP's top-200

| Pool K | H@1 | Delta H@1 |
|--------|----:|----------:|
| K=50 | 57.47% | +6.17% |
| K=75 to K=200 | 57.47% | +6.17% |

### Part 3: Statistical Significance (PMID-grouped 5-fold CV)

| Pool K | Mean H@1 | p-value | Sig |
|--------|------:|--------:|:---:|
| K=20 | 58.51% | 0.024 | * |
| K=30 | 58.54% | 0.021 | * |
| K=50 | 58.67% | 0.017 | * |

## Key Findings

1. **K=20 captures most of the benefit**: Going from K=10 to K=20 adds 1.13%, but K=20 to K=50 adds only 0.10%
2. **Expanding beyond top-50 provides no benefit**: The top-200 pool rescoring maxes out at the same H@1 as top-50
3. **All improvements are significant**: p < 0.025 for all tested pool sizes
4. **The improvement comes from local reordering**: Shuffling within a small window (top-20) is sufficient; the correct answer is almost always within 20 positions of rank-1 if it's retrievable at all

## Log File
- `pool_size_ablation.log`
- `run_pool_size_ablation.py`
