# Paper Materials: PhenoDP + LLM Reranking for Rare Disease Diagnosis

Organized materials for a 4-page BioNLP Workshop paper (co-located with ACL).

## Quick Navigation

| Section | What's Inside |
|---------|--------------|
| [00_overview/](00_overview/) | Project summary, architecture, key findings |
| [01_pipeline_code/](01_pipeline_code/) | Core Python modules (symlinks) |
| [02_prompts/](02_prompts/) | Prompt evolution writeup + rendered examples + source code |
| [03_experiments/](03_experiments/) | Nine experiment groups with results and analysis |
| [04_external_benchmarks/](04_external_benchmarks/) | RareBench evaluation (HMS, MME, LIRICAL, RAMEDIS) |
| [05_dataset_analysis/](05_dataset_analysis/) | Benchmark statistics |
| [06_failure_analysis/](06_failure_analysis/) | Error categorization and interpretation |
| [07_results_summary/](07_results_summary/) | Consolidated results tables |
| [08_paper_writeup/](08_paper_writeup/) | Paper outline with section-by-section plan |

## Experiment Index

| # | Experiment | Key Result | Section |
|---|-----------|------------|---------|
| 1 | Baseline Retriever (PhenoDP) | H@1 = 51.24% | [exp1](03_experiments/exp1_baseline_retriever/) |
| 2 | Prompt Evolution (v2-v6) on Demotions | v3 best (92.5%), v6 worst (14.5%) | [exp2](03_experiments/exp2_prompt_evolution_demotions/) |
| 3 | Full-Scale Reranking (v3, v6) | v6 = baseline, v3 = +6.4% on partial | [exp3](03_experiments/exp3_full_rerank_runs/) |
| 4 | HPO Annotation Variant | -10.4% below baseline | [exp4](03_experiments/exp4_hpo_annotation_variant/) |
| 5 | Gemma 3 vs Llama 3.3 70B | Gemma +24% over Llama | [exp5](03_experiments/exp5_model_comparison_llama70b/) |
| 6 | Z-score PR Rescoring | +6.4% H@1, p=0.017 | [exp6](03_experiments/exp6_score_rescoring/) |
| 7 | MLP Signal Fusion | +6.8% H@1, p=0.004 (best) | [exp7](03_experiments/exp7_learned_fusion_mlp/) |
| 8 | Contrastive Encoder Fine-tuning | +6% embedding H@1, 0% external | [exp8](03_experiments/exp8_contrastive_encoder/) |
| 9 | Pool Size Ablation | K=20 captures most benefit | [exp9](03_experiments/exp9_pool_size_ablation/) |

## One-Line Summary

**A well-calibrated retriever is hard to beat: LLM reranking helps on curated cases but shows no net gain at scale, while simple score normalization (+6.4%) and learned fusion (+6.8%) improve in-distribution but fail to generalize to external benchmarks.**

## For the Paper-Writing LLM

Start with:
1. [Paper outline](08_paper_writeup/paper_outline.md) -- section-by-section structure
2. [Consolidated results](07_results_summary/consolidated_results.md) -- all numbers in one place
3. [Project overview](00_overview/README.md) -- architecture and key findings
4. Then dive into individual experiments as needed for details
