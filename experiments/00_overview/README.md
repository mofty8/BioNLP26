# PhenoDP + Gemma 3 Candidate Ranking for Rare Disease Diagnosis

## Project Summary

This project investigates **LLM-based reranking of rare disease candidate diagnoses** retrieved by a phenotype-similarity model (PhenoDP). The core question: can a local LLM (Gemma 3 27B) improve the ranking of disease candidates beyond what a well-calibrated retriever already provides?

### System Architecture

```
Patient Phenopacket (HPO terms, negated HPO, genes, demographics)
        |
        v
   PhenoDP Retriever (phenotype similarity, top-50 candidates)
        |
        v
   LLM Reranker (Gemma 3 27B / Llama 3.3 70B via vLLM)
        |
        v
   Reranked Candidate List (top-3/5/10)
```

### Key Components

1. **PhenoDP** -- A phenotype-driven retriever that scores disease candidates using IC-weighted phenotype overlap and a pre-trained HPO encoder (PCL_HPOEncoder). Retrieves top-50 candidates per patient.

2. **Gemma 3 27B-IT** -- A local instruction-tuned LLM used as a clinical reranker. Given patient phenotypes + candidate list, it produces a reranked ordering with clinical reasoning.

3. **Prompt Engineering** -- Six iterations of reranking prompts (v2-v6 + HPO annotation variant), each addressing specific failure modes discovered through error analysis.

4. **Learned Fusion** -- An MLP-based score fusion approach that combines decomposed PhenoDP signals (phi scores, embedding similarity, IC weights) to learn an improved ranking.

5. **Contrastive Encoder Fine-tuning** -- Fine-tuning PhenoDP's HPO encoder with subtype-aware contrastive loss to better separate phenotypically similar disease subtypes.

### Benchmark

- **Primary benchmark**: 6,901 phenopacket cases derived from published case reports, covering 500 unique OMIM diseases, minimum 3 HPO terms per patient.
- **External benchmarks** (RareBench): HMS (88 cases, 51 diseases), MME (40 cases, 17 diseases), LIRICAL (370 cases, 252 diseases), RAMEDIS (624 cases, 74 diseases).
- **Evaluation metrics**: Hit@1, Hit@3, Hit@5, Hit@10, MRR under three correctness criteria (ID correct, ID+name correct, ID-or-name correct).

### Key Findings

1. **LLM reranking shows marginal to negative impact at scale**: While prompt engineering achieves high accuracy on curated demotion subsets (v3: 92.5% H@1 on 509 cases), full-scale reranking over 6,901 cases yields H@1 = 0.511, essentially matching the retriever baseline (0.512). The LLM cannot improve what it cannot distinguish.

2. **Prompt over-tuning paradox**: More constrained prompts (v5, v6) designed to prevent false demotions also prevent valid promotions. v6 achieves only 14.5% H@1 on the demotion subset -- the strictest prompt is the worst performer on cases that need reranking.

3. **Learned score fusion is the most promising direction**: An MLP trained on decomposed PhenoDP signals achieves H@1 = 59.13% (+6.84% over baseline, p=0.004) in nested 5-fold CV. This is the only approach that consistently improves Hit@1.

4. **However, MLP does not generalize to external benchmarks**: On RareBench (HMS+MME+LIRICAL), MLP H@1 = 44.35% vs baseline 47.28% -- a -2.93% drop, indicating overfitting to the training distribution.

5. **Contrastive encoder fine-tuning helps subtype discrimination** but the improvement doesn't transfer to external benchmarks (Delta H@1 = 0% on HMS, MME, LIRICAL).

6. **Gemma 3 27B outperforms Llama 3.3 70B** on the same reranking task (74% vs 50% H@1 on 100-case demotion+promotion set), suggesting model architecture matters more than parameter count for this structured reasoning task.

### Folder Structure

```
paper_materials/
  00_overview/          -- This file; project context and key findings
  01_pipeline_code/     -- Symlinks to core pipeline modules
  02_prompts/           -- All prompt versions with rendered examples
  03_experiments/       -- Nine experiment groups with results and analysis
  04_external_benchmarks/ -- RareBench evaluation results
  05_dataset_analysis/  -- Benchmark dataset statistics
  06_failure_analysis/  -- Error analysis and failure categorization
  07_results_summary/   -- Consolidated results tables and comparisons
  08_paper_writeup/     -- Draft sections and outline for BioNLP paper
```
