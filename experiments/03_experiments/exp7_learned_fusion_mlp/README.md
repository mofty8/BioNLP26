# Experiment 7: Learned Signal Fusion (MLP)

## Motivation
Instead of using the LLM to reason about candidates, decompose PhenoDP's internal scoring signals and learn an optimal combination using a small MLP. This replaces natural language reasoning with a direct learned mapping from features to ranking scores.

## Method
1. **Signal decomposition**: For each (patient, candidate) pair, extract:
   - Phi scores (IC-weighted phenotype overlap)
   - Embedding similarities (PCL_HPOEncoder cosine similarity)
   - IC weights
   - Retrieval rank, retrieval score
   - HPO annotation match features
2. **MLP architecture**: Small feedforward network trained with pairwise ranking loss
3. **Training**: Pairwise samples -- (patient, correct_candidate, incorrect_candidate) -- trained to rank correct higher
4. **Evaluation**: Nested 5-fold CV with PMID-grouped splits (no data leakage from same publication)

## Phase 1: Signal Decomposition
- Extracted decomposed signals for all 6,901 patients x 50 candidates
- Output: `runs/phenodp_decomposed_signals.jsonl` (214 MB)

## Phase 2: MLP Training & Evaluation

### Nested 5-fold CV Results

| Fold | Baseline H@1 | Z-score PR H@1 | MLP H@1 | MLP Delta |
|------|----------:|------------:|--------:|----------:|
| 0 | 48.77% | 50.32% | 51.75% | +2.98% |
| 1 | 50.55% | 53.56% | 56.09% | +5.54% |
| 2 | 54.81% | 58.45% | 62.55% | +7.73% |
| 3 | 46.04% | 56.59% | 55.60% | +9.57% |
| 4 | 61.29% | 69.25% | 69.67% | +8.38% |

### Summary (Unbiased Estimates)

| Method | H@1 | H@3 | H@5 | H@10 | MRR |
|--------|----:|----:|----:|-----:|----:|
| Baseline | 52.29% (+-5.33) | 64.27% (+-6.19) | 68.17% (+-6.14) | 72.89% (+-5.98) | 0.596 |
| Z-score PR | 57.63% (+-6.43) | 66.63% (+-7.18) | 69.54% (+-6.95) | 72.87% (+-6.18) | 0.633 |
| **MLP** | **59.13% (+-6.31)** | **67.53% (+-6.26)** | **70.15% (+-5.86)** | **73.31% (+-5.62)** | **0.645** |

### Deltas vs Baseline

| Metric | MLP Delta | p-value | Sig |
|--------|----------:|--------:|:---:|
| H@1 | **+6.84%** | 0.004 | ** |
| H@3 | +3.26% | -- | -- |
| H@5 | +1.98% | -- | -- |
| H@10 | +0.42% | -- | -- |

### MLP vs Z-score PR
| Metric | Delta | p-value | Sig |
|--------|------:|--------:|:---:|
| H@1 | +1.50% | 0.160 | ns |

## Interpretation

### Best Single-Benchmark Result
The MLP achieves the largest H@1 improvement (+6.84%) of any method, and it is highly statistically significant (p=0.004). It outperforms z-score PR rescoring by 1.5%, though this difference is not statistically significant (p=0.16).

### Why MLP Works Better Than LLM Reranking
1. **Direct signal access**: The MLP sees the actual decomposed scores (phi, embedding similarity, IC weights) rather than natural language descriptions
2. **Learned asymmetry**: It automatically discovers the right precision/recall trade-off from data
3. **No hallucination**: Unlike the LLM, the MLP cannot invent clinical reasoning or hallucinate disease-phenotype associations
4. **Consistent**: Same features always produce the same score; no prompt sensitivity

### Limitation: Does Not Generalize (See Experiment in 04_external_benchmarks)
On RareBench, the MLP drops below baseline (H@1 = 44.35% vs 47.28%). The learned weights overfit to the training distribution's specific disease mix and score characteristics.

## Code & Artifacts
- `proposal1_learned_fusion.py` -- MLP training and evaluation
- `runs/phenodp_decomposed_signals.jsonl` -- Decomposed signals (214 MB)
- `runs/proposal1_final_mlp.pth` -- Trained MLP weights
- `proposal1_phase2.log` -- Training and CV results
