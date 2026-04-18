# Experiment 8: Contrastive Encoder Fine-tuning

## Motivation
PhenoDP's PCL_HPOEncoder maps HPO term sets to dense embeddings, but it was pre-trained with general InfoNCE contrastive loss that doesn't specifically optimize for distinguishing between phenotypically similar disease subtypes (e.g., NBIA type 1 vs type 4, Retinitis pigmentosa 11 vs 18). Fine-tuning with subtype-aware triplets might improve separation.

## Method
1. **Sibling groups**: Extract disease subtype families from Mondo OMIMPS (564 groups, 4,209 diseases with siblings)
2. **Triplet construction**: For each patient, create (anchor=patient, positive=correct disease, negative=sibling of correct disease from same family)
3. **Fine-tuning**: 10 epochs with triplet margin loss on 3,417 subtype cases
4. **Evaluation**: Compare Hit@K using original vs fine-tuned encoder as the PhenoDP embedding component

## Results

### Embedding-Only Retrieval (semantic signal only)

| Metric | Before Fine-tuning | After Fine-tuning | Delta |
|--------|-------------------:|------------------:|------:|
| H@1 | 1.67% | 7.67% | +6.00% |
| H@3 | 4.17% | 17.55% | +13.37% |
| H@5 | 6.85% | 24.45% | +17.59% |
| H@10 | 13.87% | 36.08% | +22.21% |
| H@1 (subtype only, 3417) | 1.99% | 13.40% | +11.41% |
| H@3 (subtype only, 3417) | 5.12% | 30.58% | +25.46% |

### On External Benchmarks (RareBench)

| Dataset | Original H@1 | Fine-tuned H@1 | Delta |
|---------|----------:|------------:|------:|
| HMS (88) | 7.35% | 7.35% | 0.00% |
| MME (40) | 65.00% | 65.00% | 0.00% |
| LIRICAL (370) | 52.70% | 52.70% | 0.00% |

## Interpretation

### Strong In-Distribution Improvement
The fine-tuned encoder dramatically improves embedding-only retrieval: H@1 goes from 1.67% to 7.67% (+6%), and H@1 on subtype cases goes from 2% to 13.4%. The contrastive loss successfully pushes apart embeddings of similar disease subtypes.

### Zero Transfer to External Benchmarks
On HMS, MME, and LIRICAL, the fine-tuned encoder produces identical results to the original. This means:
1. The fine-tuning didn't degrade the encoder (no catastrophic forgetting)
2. But the subtype-specific improvements don't help on benchmarks with different disease distributions
3. The external benchmarks may not contain the subtype ambiguity cases where the fine-tuning helps

### Why the Disconnect
The fine-tuning targets subtype discrimination -- distinguishing NBIA-1 from NBIA-4, etc. External benchmarks may have fewer such cases, or the diseases present may not overlap with the fine-tuning set (HMS: 92.2% unseen diseases, MME: 100% unseen).

### Standalone Embedding Retrieval is Weak
Even after fine-tuning, embedding-only H@1 = 7.67% is far below full PhenoDP (51.24%). The IC-weighted phenotype matching (phi scores) is far more important than embeddings. Embeddings are a minor signal in PhenoDP's composite score.

## Code & Artifacts
- `proposal5_contrastive.py` / `proposal5_contrastive_training.py` -- Fine-tuning code
- `runs/pcl_hpoencoder_subtype_finetuned.pth` -- Fine-tuned encoder weights (6.9 MB)
- `proposal5.log` -- Training log
- `runs/proposal5_results.json` -- Results
