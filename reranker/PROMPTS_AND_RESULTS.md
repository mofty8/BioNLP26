# Prompt Catalog And Results

## Baseline

Baseline retriever for the main 6,901-case benchmark:

- [retriever top50 summary](/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/phenodp_gemma3_candidate_ranking/runs/phenodp_gemma3_6901_no_genes_twostage_20260319_054012_20260319_044040/methods/retriever_phenodp_top50/summary.json)
- Exact-ID metrics: Hit@1 `0.5124`, Hit@3 `0.6327`, Hit@5 `0.6719`, Hit@10 `0.7192`

## Current Code-Defined Prompts

These are the prompt templates that currently exist in code.

| Prompt | Canonical source | Notes |
|---|---|---|
| `v3` | [build_prompt_text fallback](/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/phenodp_gemma3_candidate_ranking/phenodp_gemma3_pipeline/prompting.py#L536) | Default non-HPO-annotation prompt. No separate `_build_prompt_v3_text()` function exists. |
| `v4` | [_build_prompt_v4_text](/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/phenodp_gemma3_candidate_ranking/phenodp_gemma3_pipeline/prompting.py#L30) | Adds hard score-gap gate, strict Condition A, biological-impossibility Condition B, numbered-subtype rule. |
| `v5` | [_build_prompt_v5_text](/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/phenodp_gemma3_candidate_ranking/phenodp_gemma3_pipeline/prompting.py#L181) | Tightens v4, adds stronger name-inference rule and incomplete-record / age-dependent caveat. |
| `v6` | [_build_prompt_v6_text](/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/phenodp_gemma3_candidate_ranking/phenodp_gemma3_pipeline/prompting.py#L348) | Adds same-gene spectrum rule, tighter gap threshold, demotion self-check. |
| `HPO annotation variant` | [same fallback builder, annotation branch](/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/phenodp_gemma3_candidate_ranking/phenodp_gemma3_pipeline/prompting.py#L536) | Activated by `include_hpo_annotations=true`; uses HPO frequencies in prompt. |

## Archived Prompt Snapshots

These are rendered prompts preserved in run artifacts. They are the easiest files to read directly.

| Prompt snapshot | Read here |
|---|---|
| `v2` demotions prompt | [qualitative_examples.md](/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/phenodp_gemma3_candidate_ranking/runs/phenodp_gemma3_prompt_v2_demotions_rerank/methods/reranker_gemma3_top3/qualitative_examples.md) |
| `v3` demotions prompt | [qualitative_examples.md](/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/phenodp_gemma3_candidate_ranking/runs/phenodp_gemma3_prompt_v3_demotions_rerank/methods/reranker_gemma3_top3/qualitative_examples.md) |
| `v4` demotions prompt | [qualitative_examples.md](/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/phenodp_gemma3_candidate_ranking/runs/phenodp_gemma3_prompt_v4_demotions_rerank/methods/reranker_gemma3_top3/qualitative_examples.md) |
| `v5` demotions prompt | [qualitative_examples.md](/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/phenodp_gemma3_candidate_ranking/runs/phenodp_gemma3_prompt_v5_demotions_rerank/methods/reranker_gemma3_top3/qualitative_examples.md) |
| `v6` demotions prompt | [qualitative_examples.md](/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/phenodp_gemma3_candidate_ranking/runs/phenodp_gemma3_prompt_v6_demotions_rerank/methods/reranker_gemma3_top3/qualitative_examples.md) |
| `HPO annotation` prompt | [qualitative_examples.md](/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/phenodp_gemma3_candidate_ranking/runs/phenodp_gemma3_v8_hpo_ann_full_20260323_034805/methods/reranker_gemma3_top3/qualitative_examples.md) |
| `v6` full prompt examples | [qualitative_examples.md](/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/phenodp_gemma3_candidate_ranking/runs/phenodp_gemma3_v6_full_rerank/methods/reranker_gemma3_top10/qualitative_examples.md) |

## Prompt Deltas

- `v2`: protect retrieval rank-1; only two demotion reasons: exclusion or superior coverage.
- `v3` snapshot: adds retrieval score-gap rule and stricter definition of obligatory absent features.
- `v4` snapshot: makes gap thresholds explicit and increases resistance to reranking when gap is large.
- `v5` snapshot: changes flow to coverage-first, then exclusion check.
- `v6` code: reframes `B` as coverage gap, adds same-gene spectrum rule and demotion self-check.
- `HPO annotation`: replaces free reasoning about penetrance with annotation-driven reasoning from `phenotype.hpoa`.

## Results

### Small Targeted Sets

These are curated demotion or demotion/promotion subsets, not the full benchmark.

| Run | Cases | Method | Exact-ID H@1 | H@3 | H@5 | H@10 | Result file |
|---|---:|---|---:|---:|---:|---:|---|
| `v2 demotions` | 509 | `top3` | 0.4735 | 1.0000 | 1.0000 | 1.0000 | [benchmark_summary.json](/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/phenodp_gemma3_candidate_ranking/runs/phenodp_gemma3_prompt_v2_demotions_rerank/benchmark_summary.json) |
| `v3 demotions` | 509 | `top3` | 0.9253 | 1.0000 | 1.0000 | 1.0000 | [benchmark_summary.json](/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/phenodp_gemma3_candidate_ranking/runs/phenodp_gemma3_prompt_v3_demotions_rerank/benchmark_summary.json) |
| `v4 demotions` | 509 | `top3` | 0.7289 | 1.0000 | 1.0000 | 1.0000 | [benchmark_summary.json](/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/phenodp_gemma3_candidate_ranking/runs/phenodp_gemma3_prompt_v4_demotions_rerank/benchmark_summary.json) |
| `v5 demotions` | 509 | `top3` | 0.4578 | 1.0000 | 1.0000 | 1.0000 | [benchmark_summary.json](/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/phenodp_gemma3_candidate_ranking/runs/phenodp_gemma3_prompt_v5_demotions_rerank/benchmark_summary.json) |
| `v6 demotions` | 509 | `top3` | 0.1454 | 1.0000 | 1.0000 | 1.0000 | [benchmark_summary.json](/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/phenodp_gemma3_candidate_ranking/runs/phenodp_gemma3_prompt_v6_demotions_rerank/benchmark_summary.json) |
| `Gemma v6 demotions+promotions` | 100 | `top3` | 0.7400 | 0.9900 | 0.9900 | 0.9900 | [benchmark_summary.json](/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/phenodp_gemma3_candidate_ranking/runs/phenodp_gemma3_v6_demotions_promotions/benchmark_summary.json) |
| `Gemma v6 demotions+promotions` | 100 | `top5` | 0.7700 | 0.9900 | 1.0000 | 1.0000 | [benchmark_summary.json](/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/phenodp_gemma3_candidate_ranking/runs/phenodp_gemma3_v6_demotions_promotions/benchmark_summary.json) |
| `Llama70B v5 demotions+promotions` | 100 | `top3` | 0.5000 | 0.9900 | 0.9900 | 0.9900 | [benchmark_summary.json](/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/phenodp_gemma3_candidate_ranking/runs/phenodp_llama70b_v5_demotions_promotions/benchmark_summary.json) |
| `Llama70B v5 demotions+promotions` | 100 | `top5` | 0.4900 | 0.9700 | 1.0000 | 1.0000 | [benchmark_summary.json](/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/phenodp_gemma3_candidate_ranking/runs/phenodp_llama70b_v5_demotions_promotions/benchmark_summary.json) |

### Larger Full Rerank Runs

| Run | Cases | Method | Exact-ID H@1 | H@3 | H@5 | H@10 | Result file |
|---|---:|---|---:|---:|---:|---:|---|
| `v3 full rerank` | 3451 | `top3` | 0.5766 | 0.7291 | 0.7291 | 0.7291 | [benchmark_summary.json](/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/phenodp_gemma3_candidate_ranking/runs/phenodp_gemma3_prompt_v3_full_rerank/benchmark_summary.json) |
| `v3 full rerank` | 3451 | `top5` | 0.5766 | 0.7291 | 0.7728 | 0.7728 | [benchmark_summary.json](/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/phenodp_gemma3_candidate_ranking/runs/phenodp_gemma3_prompt_v3_full_rerank/benchmark_summary.json) |
| `v3 full rerank` | 3451 | `top10` | 0.5793 | 0.7291 | 0.7728 | 0.8108 | [benchmark_summary.json](/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/phenodp_gemma3_candidate_ranking/runs/phenodp_gemma3_prompt_v3_full_rerank/benchmark_summary.json) |
| `v6 full rerank` | 6901 | `top3` | 0.5118 | 0.6327 | 0.6327 | 0.6327 | [benchmark_summary.json](/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/phenodp_gemma3_candidate_ranking/runs/phenodp_gemma3_v6_full_rerank/benchmark_summary.json) |
| `v6 full rerank` | 6901 | `top5` | 0.5118 | 0.6327 | 0.6719 | 0.6719 | [benchmark_summary.json](/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/phenodp_gemma3_candidate_ranking/runs/phenodp_gemma3_v6_full_rerank/benchmark_summary.json) |
| `v6 full rerank` | 6901 | `top10` | 0.5112 | 0.6327 | 0.6719 | 0.7190 | [benchmark_summary.json](/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/phenodp_gemma3_candidate_ranking/runs/phenodp_gemma3_v6_full_rerank/benchmark_summary.json) |
| `HPO annotation full` | 6901 | `top3` | 0.4081 | 0.6327 | 0.6327 | 0.6327 | [benchmark_summary.json](/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/phenodp_gemma3_candidate_ranking/runs/phenodp_gemma3_v8_hpo_ann_full_20260323_034805/benchmark_summary.json) |
| `HPO annotation full` | 6901 | `top5` | 0.3968 | 0.6289 | 0.6719 | 0.6719 | [benchmark_summary.json](/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/phenodp_gemma3_candidate_ranking/runs/phenodp_gemma3_v8_hpo_ann_full_20260323_034805/benchmark_summary.json) |

## Read Order

If you just want to read the prompt evolution quickly:

1. [v2 archived prompt](/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/phenodp_gemma3_candidate_ranking/runs/phenodp_gemma3_prompt_v2_demotions_rerank/methods/reranker_gemma3_top3/qualitative_examples.md)
2. [v3 archived prompt](/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/phenodp_gemma3_candidate_ranking/runs/phenodp_gemma3_prompt_v3_demotions_rerank/methods/reranker_gemma3_top3/qualitative_examples.md)
3. [v4 source](/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/phenodp_gemma3_candidate_ranking/phenodp_gemma3_pipeline/prompting.py#L30)
4. [v5 source](/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/phenodp_gemma3_candidate_ranking/phenodp_gemma3_pipeline/prompting.py#L181)
5. [v6 source](/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/phenodp_gemma3_candidate_ranking/phenodp_gemma3_pipeline/prompting.py#L348)
6. [HPO annotation rendered prompt](/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/phenodp_gemma3_candidate_ranking/runs/phenodp_gemma3_v8_hpo_ann_full_20260323_034805/methods/reranker_gemma3_top3/qualitative_examples.md)

## Caveat

Some early run directories were reused for later rerank passes, so I would treat the dedicated result folders above as the reliable prompt/result pairings, and treat the old reused folders as historical artifacts.
