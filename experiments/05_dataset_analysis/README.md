# Dataset Analysis

## Primary Benchmark: 6,901 Publication Cases

| Statistic | Value |
|-----------|------:|
| Total cases | 6,901 |
| Unique diseases | 500 |
| HPO terms per patient (mean) | 9.4 |
| HPO terms per patient (median) | 8.0 |
| HPO terms per patient (std) | 5.8 |
| HPO terms (min-max) | 3-66 |
| HPO terms (P10-P90) | 4.0 - 17.0 |

### Top 5 Most Frequent Diseases
| OMIM ID | Cases | Percentage |
|---------|------:|-----------:|
| OMIM:612164 | 430 | 6.2% |
| OMIM:148050 | 304 | 4.4% |
| OMIM:613721 | 260 | 3.8% |
| OMIM:162200 | 204 | 3.0% |
| OMIM:612313 | 147 | 2.1% |

## External Benchmarks

### HMS (88 cases)
- Median HPO terms: 17.5 (nearly 2x the training set)
- Unique diseases: 51 (92.2% NOT seen during training)
- HPO term overlap with training: 56.2%

### MME (40 cases)
- Median HPO terms: 10.5
- Unique diseases: 17 (100% NOT seen during training)
- HPO term overlap with training: 80.6%

### LIRICAL (370 cases)
- Median HPO terms: 11.5
- Unique diseases: 252 (91.3% seen during training, only 22 unseen)
- HPO term overlap with training: 80.4%

## Key Observations for Paper

1. **Distribution skew**: The primary benchmark is heavily skewed -- the top 5 diseases account for 19.5% of all cases. This means methods optimized on this benchmark disproportionately learn to rank these frequent diseases.

2. **HMS is the hardest external benchmark**: Fewest overlapping diseases (7.8%), highest phenotype complexity (median 17.5 HPO terms), and the most novel HPO vocabulary (only 56.2% overlap). This explains why all methods perform worst on HMS.

3. **LIRICAL is the most similar to training**: 91.3% disease overlap, suggesting that methods should transfer well. When they don't (MLP drops), it indicates genuine overfitting rather than distribution shift.

4. **MME is deceptively easy**: Despite 100% unseen diseases, baseline H@1 = 65%. This may reflect that MME diseases are phenotypically distinctive (few confusable subtypes) or that the 40-case sample is too small for reliable estimation.

## Source Files
- `dataset_analysis.log`
- `hms_analysis.log`
- `run_dataset_analysis.py`
- `run_hms_analysis.py`
