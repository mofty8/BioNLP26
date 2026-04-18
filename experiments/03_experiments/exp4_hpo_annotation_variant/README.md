# Experiment 4: HPO Annotation-Augmented Prompting

## Motivation
A key failure mode of LLM reranking is that the model hallucinates phenotype-disease associations. For example, it might claim a feature is "obligatory" for a disease when it actually has low penetrance. By injecting real HPO annotation frequencies from `phenotype.hpoa`, we hypothesized the model could make evidence-based rather than knowledge-based decisions.

## Setup
- **Prompt**: HPO annotation variant (activated by `include_hpo_annotations=true`)
- **Data source**: `phenotype.hpoa` -- HPO phenotype-disease annotations with frequency modifiers
- **Annotation format**: For each candidate, list matching/mismatching HPO terms with their annotated frequencies
- **Benchmark**: 6,901 cases
- **Cutoffs**: top-3, top-5

## Results (ID-correct, 6,901 cases)

| Cutoff | H@1 | H@3 | H@5 | H@10 | MRR |
|--------|----:|----:|----:|-----:|----:|
| top-3 | 40.81% | 63.27% | 63.27% | 63.27% | 0.511 |
| top-5 | 39.68% | 62.89% | 67.19% | 67.19% | 0.517 |
| Baseline | 51.24% | 63.27% | 67.19% | 71.92% | 0.585 |

## Analysis

### 10% Below Baseline -- Information Overload
The annotation-augmented prompt **hurts** performance significantly: H@1 drops from 51.24% to 40.81%, a 10.4% decrease.

### Why More Information Hurts
1. **Context length**: Adding HPO annotations for each candidate dramatically increases prompt length. The model may struggle to attend to the most relevant signals amid the noise.
2. **Annotation noise**: HPO annotations are not patient-specific. A disease may have 50+ annotated phenotypes, most irrelevant to a given patient. The LLM gets distracted by matching low-relevance features.
3. **False confidence**: Seeing explicit frequency numbers (e.g., "HP:0001249 - Intellectual disability: Very frequent (80-99%)") makes the model more willing to demote rank-1 based on a single feature mismatch, even when the overall phenotype profile strongly favors rank-1.
4. **Annotation completeness**: HPO annotations are incomplete. Absence of an annotation does not mean the phenotype is absent in the disease.

### Implication for Paper
This is a strong negative result worth reporting: **giving the LLM more structured clinical evidence does not help and actively hurts performance**. This challenges the assumption that LLM reranking failures are due to knowledge gaps -- even with perfect disease-phenotype frequency data, the LLM makes worse decisions.

## Run Directory
`runs/phenodp_gemma3_v8_hpo_ann_full_20260323_034805/`
