# External Benchmark Evaluation (RareBench)

## Overview
All methods trained/tuned on the 6,901-case primary benchmark are evaluated on four external datasets from RareBench to assess generalization. This is critical for a fair evaluation -- methods that only improve on the training distribution are not clinically useful.

## Datasets

| Dataset | Cases | Unique Diseases | HPO terms/case (median) | Disease Overlap with Training |
|---------|------:|----------------:|------------------------:|------------------------------:|
| HMS | 88 | 51 | 17.5 | 7.8% (47/51 unseen) |
| MME | 40 | 17 | 10.5 | 0.0% (all unseen) |
| LIRICAL | 370 | 252 | 11.5 | 91.3% (22 unseen) |
| RAMEDIS | 624 | 74 | 9.0 | -- |

## Results Summary (H@1, ID-correct)

| Method | HMS (88) | MME (40) | LIRICAL (370) | Combined |
|--------|------:|------:|----------:|--------:|
| **PhenoDP Baseline** | 7.35% | **65.00%** | **52.70%** | **47.28%** |
| Z-score PR | 1.47% | **65.00%** | **53.78%** | 47.28% |
| MLP fusion | 10.29% | **65.00%** | 48.38% | 44.35% |
| Fine-tuned encoder | 7.35% | **65.00%** | **52.70%** | -- |

### RAMEDIS-specific (from validation log)

| Method | RAMEDIS (624) |
|--------|----------:|
| Baseline | 10.26% |
| Z-score PR | 11.86% |

## Key Findings

### MLP Does Not Generalize
The MLP, which achieved +6.84% on the primary benchmark, drops -2.93% on RareBench combined. The most dramatic failure is LIRICAL: 48.38% vs 52.70% baseline. The learned weights are specific to the training distribution's disease mix.

### Z-score PR Rescoring is Mixed
- **HMS**: Catastrophic drop (7.35% -> 1.47%), possibly because HMS has very different score distributions (more complex cases with more HPO terms)
- **MME**: No change (65% stays at 65%)
- **LIRICAL**: Slight improvement (+1.08%)
- **RAMEDIS**: Slight improvement (+1.60%)

### Fine-tuned Encoder Changes Nothing
Zero delta on all external benchmarks. The subtype-aware contrastive training helps within the training distribution but doesn't transfer.

### The Generalization Problem
Methods that "learn from the data" (MLP, fine-tuned encoder) fail to generalize because:
1. **Disease distribution shift**: HMS has 92% unseen diseases, MME has 100% unseen
2. **Score distribution shift**: Different datasets have different phenotype richness (HMS: median 17.5 HPO terms vs training: median 8.0)
3. **Overfitting to the easy cases**: The training set has many cases from high-frequency diseases; external benchmarks test the long tail

## Implication for Paper
This is arguably the most important section for a fair evaluation. **Any method that only reports in-distribution results is misleading.** The RareBench results show that none of our methods consistently improve over the PhenoDP baseline on unseen data.

## Source Files
- `rarebench_mlp.log` -- MLP evaluation on RareBench
- `rarebench_finetuned_encoder.log` -- Fine-tuned encoder evaluation
- `rarebench_validation.log` -- Z-score PR rescoring validation
- `run_rarebench_mlp.py`, `run_rarebench_finetuned_encoder.py`, `run_rarebench_validation.py`
