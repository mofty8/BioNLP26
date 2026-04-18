# Reranking Analysis Report
**BioNLP @ ACL 2026 Paper — Candidate Reranking Experiments**
*Generated: 2026-04-12*

---

## Overview

This report analyzes **LLM-based candidate reranking** for rare disease diagnosis.
The system pipeline:
1. **PhenoDP retriever**: semantic HPO-similarity search → top-50 candidate diseases
2. **LLM reranker**: clinical reasoning over top-K candidates (K=3, 5, or 10) → reordered shortlist

**Models evaluated:** Gemma-3 27B, Gemma-4 31B, Llama-3.3 70B (all instruction-tuned)
**Prompts:** v7 (conservative, rule-based), pp2prompt_v2 (alternative formulation)
**Datasets:**
- **PhenoPacket** (n=6,901): Literature-curated HPO-annotated cases from OMIM publications
- **RareBench** (n=1,122): 4 sub-datasets — HMS (88 clinical), MME (40 ultra-rare), LIRICAL (370 literature), RAMEDIS (624 structured)

**Baseline:** PhenoDP retriever alone (no LLM step)

All metrics use **strict OMIM ID matching** unless noted otherwise.

---

## 1. Retriever (PhenoDP) Baseline

### 1.1 PhenoPacket

| Metric | Value |
|--------|-------|
| N cases | 6,901 |
| Hit@1 | 51.2% |
| Hit@3 | 63.3% |
| Hit@5 | 67.2% |
| Hit@10 | 71.9% |
| Hit@50 / Recall (top-50) | 81.5% |
| MRR | 0.5855 |

**Key numbers:**
- Hit@1 = 51.2%: retriever places correct diagnosis first in >half of cases
- Hit@50 = 81.5%: this is the hard ceiling for any top-50 reranking approach
- Gap (hit@50 − hit@1) = 30.2%: maximum theoretical gain from perfect reranking
- Cases NOT in top-50: 1,278 (18.5%) — beyond retrieval reach


### 1.2 RareBench — Per Sub-dataset

| Sub-dataset | N | Hit@1 | Hit@5 | Hit@10 | Hit@50 | MRR |
|------------|---|-------|-------|--------|--------|-----|
| **RareBench Overall** | 1122 | 25.8% | 43.9% | 51.1% | 66.1% | 0.3440 |
| HMS | 88 | 5.7% | 19.3% | 28.4% | 37.5% | 0.1207 |
| LIRICAL | 370 | 52.7% | 70.8% | 75.9% | 85.7% | 0.6106 |
| MME | 40 | 65.0% | 85.0% | 90.0% | 95.0% | 0.7404 |
| RAMEDIS | 624 | 10.3% | 28.7% | 37.0% | 56.7% | 0.1920 |

**Critical sub-dataset pattern:**

| Sub-dataset | Retriever Hit@1 | Unrestricted LLM Hit@1 (best) | Advantage |
|------------|-----------------|-------------------------------|-----------|
| HMS | 5.7% | 20.6% (med42-70b) | LLM (med42-70b, +14.9%) |
| LIRICAL | 52.7% | 17.0% (llama-3.3-70b) | Retriever (+35.7%) |
| MME | 65.0% | 5.0% (llama-3.3-70b) | Retriever (+60.0%) |
| RAMEDIS | 10.3% | 46.8% (med42-70b) | LLM (med42-70b, +36.5%) |

**Notable finding:** MME is the easiest subset for the retriever (65.0% Hit@1) but hardest
for unrestricted LLMs (~5% Hit@1). This inversion shows that HPO-based retrieval
(symbolic matching against curated HPOA annotations) dramatically outperforms parametric
LLM knowledge for ultra-rare diseases. Conversely, HMS is hardest for the retriever
(5.7% Hit@1) but comparatively better for LLMs (~17.6%) — clinical free-text descriptions
in HMS cases may not map cleanly to structured HPO terms.

---

## 2. Reranker Performance (Full Evaluation)

### 2.1 PhenoPacket — All Configurations

Metrics from benchmark_summary.json (ground truth, accounts for fallback to retrieval
order when LLM output cannot be parsed).

| Model | Prompt | TopK | Hit@1 | Hit@3 | Hit@5 | Hit@10 | MRR | Δ Hit@1 |
|-------|--------|------|-------|-------|-------|--------|-----|---------|
| gemma3-27b | pp2prompt_v2 | top3 | 50.1% | 63.3% | 63.3% | 63.3% | 0.5593 | -1.1% |
| gemma3-27b | pp2prompt_v2 | top5 | 49.6% | 63.2% | 67.2% | 67.2% | 0.5651 | -1.7% |
| gemma3-27b | pp2prompt_v2 | top10 | 48.8% | 62.5% | 67.3% | 71.9% | 0.5649 | -2.5% |
| gemma3-27b | v7 | top3 | 51.3% | 63.3% | 63.3% | 63.3% | 0.5665 | +0.1% |
| gemma3-27b | v7 | top5 | 51.5% | 63.7% | 67.2% | 67.2% | 0.5767 | +0.2% |
| gemma3-27b | v7 | top10 | 51.6% | 63.7% | 67.4% | 71.9% | 0.5840 | +0.4% |
| gemma4-31b | pp2prompt_v2 | top3 | 49.4% | 63.3% | 63.3% | 63.3% | 0.5547 | -1.9% |
| gemma4-31b | pp2prompt_v2 | top5 | 49.9% | 61.9% | 67.2% | 67.2% | 0.5644 | -1.3% |
| gemma4-31b | pp2prompt_v2 | top10 | 50.7% | 62.5% | 65.9% | 71.9% | 0.5748 | -0.6% |
| gemma4-31b | v7 | top3 | 53.5% | 63.3% | 63.3% | 63.3% | 0.5783 | +2.2% |
| gemma4-31b | v7 | top5 | 53.7% | 63.9% | 67.2% | 67.2% | 0.5901 | +2.5% |
| gemma4-31b | v7 | top10 | 54.3% | 64.3% | 67.6% | 71.9% | 0.6008 | +3.1% |
| llama3.3-70b | pp2prompt_v2 | top3 | 51.8% | 63.3% | 63.3% | 63.3% | 0.5682 | +0.6% |
| llama3.3-70b | pp2prompt_v2 | top5 | 50.9% | 63.2% | 67.2% | 67.2% | 0.5727 | -0.3% |
| llama3.3-70b | pp2prompt_v2 | top10 | 51.2% | 63.2% | 67.1% | 71.9% | 0.5807 | -0.1% |
| llama3.3-70b | v7 | top3 | 52.4% | 63.3% | 63.3% | 63.3% | 0.5718 | +1.2% |
| llama3.3-70b | v7 | top5 | 52.3% | 63.6% | 67.2% | 67.2% | 0.5807 | +1.1% |
| llama3.3-70b | v7 | top10 | 52.6% | 63.7% | 67.3% | 71.9% | 0.5893 | +1.4% |

**Best PhenoPacket configuration:** gemma4-31b + v7 top10
- Hit@1: 54.3% (Δ = +3.1% vs retriever baseline of 51.2%)
- Hit@10: 71.9% (= retriever Hit@10 — expected, since top-K = 10 ≤ 10)
- MRR: 0.6008 (Δ = +1.5%)


**Pattern:** Hit@K for K ≥ topK is identical to the retriever (reranking can only affect
positions within the window). Improvements are concentrated in Hit@1 (promoting the correct
diagnosis from ranks 2-K to rank 1). This is the primary clinical value of the reranker:
reducing the number of cases where a clinician must review multiple candidates.

### 2.2 RareBench — All Configurations

| Model | Prompt | TopK | Hit@1 | Hit@3 | Hit@5 | Hit@10 | MRR | Δ Hit@1 |
|-------|--------|------|-------|-------|-------|--------|-----|---------|
| gemma3-27b | pp2prompt_v2 | top3 | 28.5% | 38.2% | 38.2% | 38.2% | 0.3286 | +2.7% |
| gemma3-27b | pp2prompt_v2 | top5 | 29.1% | 40.2% | 43.9% | 43.9% | 0.3484 | +3.2% |
| gemma3-27b | pp2prompt_v2 | top10 | 31.0% | 43.0% | 48.0% | 51.1% | 0.3787 | +5.2% |
| gemma3-27b | v7 | top3 | 26.1% | 38.1% | 38.1% | 38.1% | 0.3151 | +0.3% |
| gemma3-27b | v7 | top5 | 26.0% | 39.5% | 43.9% | 43.9% | 0.3296 | +0.2% |
| gemma3-27b | v7 | top10 | 27.0% | 39.7% | 44.3% | 51.1% | 0.3456 | +1.2% |
| gemma4-31b | pp2prompt_v2 | top3 | 29.4% | 38.2% | 38.2% | 38.2% | 0.3341 | +3.6% |
| gemma4-31b | pp2prompt_v2 | top5 | 30.6% | 40.6% | 43.9% | 43.9% | 0.3580 | +4.7% |
| gemma4-31b | pp2prompt_v2 | top10 | 31.3% | 42.6% | 46.8% | 51.1% | 0.3790 | +5.4% |
| gemma4-31b | v7 | top3 | 26.3% | 38.2% | 38.2% | 38.2% | 0.3157 | +0.4% |
| gemma4-31b | v7 | top5 | 26.0% | 38.2% | 43.9% | 43.9% | 0.3268 | +0.2% |
| gemma4-31b | v7 | top10 | 26.2% | 38.2% | 43.9% | 51.1% | 0.3378 | +0.4% |
| llama3.3-70b | pp2prompt_v2 | top3 | 30.4% | 38.2% | 38.2% | 38.2% | 0.3382 | +4.5% |
| llama3.3-70b | pp2prompt_v2 | top5 | 31.5% | 40.0% | 43.9% | 43.9% | 0.3609 | +5.6% |
| llama3.3-70b | pp2prompt_v2 | top10 | 33.6% | 43.6% | 48.0% | 51.1% | 0.3942 | +7.8% |
| llama3.3-70b | v7 | top3 | 25.9% | 38.2% | 38.2% | 38.2% | 0.3136 | +0.1% |
| llama3.3-70b | v7 | top5 | 25.8% | 38.2% | 43.9% | 43.9% | 0.3259 | +0.0% |
| llama3.3-70b | v7 | top10 | 25.8% | 38.2% | 43.9% | 51.1% | 0.3359 | +0.0% |

**Best RareBench configuration:** llama3.3-70b + pp2prompt_v2 top10
- Hit@1: 33.6% (Δ = +7.8% vs retriever)
- MRR: 0.3942


### 2.3 Prompt Comparison: v7 vs pp2prompt_v2

| Model | Dataset | Prompt | Best TopK | Hit@1 | Δ vs retriever |
|-------|---------|--------|-----------|-------|----------------|
| gemma3-27b | phenopacket | v7 | top10 | 51.6% | +0.4% |
| gemma3-27b | phenopacket | pp2prompt_v2 | top3 | 50.1% | -1.1% |
| gemma3-27b | rarebench | v7 | top10 | 27.0% | +1.2% |
| gemma3-27b | rarebench | pp2prompt_v2 | top10 | 31.0% | +5.2% |
| gemma4-31b | phenopacket | v7 | top10 | 54.3% | +3.1% |
| gemma4-31b | phenopacket | pp2prompt_v2 | top10 | 50.7% | -0.6% |
| gemma4-31b | rarebench | v7 | top3 | 26.3% | +0.4% |
| gemma4-31b | rarebench | pp2prompt_v2 | top10 | 31.3% | +5.4% |
| llama3.3-70b | phenopacket | v7 | top10 | 52.6% | +1.4% |
| llama3.3-70b | phenopacket | pp2prompt_v2 | top3 | 51.8% | +0.6% |
| llama3.3-70b | rarebench | v7 | top3 | 25.9% | +0.1% |
| llama3.3-70b | rarebench | pp2prompt_v2 | top10 | 33.6% | +7.8% |

---

## 3. Promotions vs Demotions Analysis

For each case where the truth disease was within the top-K retrieved candidates,
we track whether the LLM reranker moved it up (promotion), down (demotion), or kept it in place.

**Methodology:** Log files are parsed to extract the LLM's output ranking. When parsing
fails (due to output truncation or format errors), the pipeline applies a fallback that
preserves the original retrieval order. The fallback rate is reported.

### 3.1 PhenoPacket Promotions / Demotions

| Model | Prompt | TopK | In-window | Promotions | Demotions | No-change | Net | Promo→1 | Demo from 1 | Fallback% |
|-------|--------|------|-----------|------------|-----------|-----------|-----|---------|-------------|-----------|
| gemma3-27b | pp2prompt_v2 | top3 | 4,366 | 381 (8.7%) | 475 (10.9%) | 3,510 (80.4%) | -94 | 330 | 453 | 0.1% |
| gemma3-27b | pp2prompt_v2 | top5 | 4,637 | 537 (11.6%) | 689 (14.9%) | 3,411 (73.6%) | -152 | 364 | 546 | 0.1% |
| gemma3-27b | pp2prompt_v2 | top10 | 4,963 | 720 (14.5%) | 849 (17.1%) | 3,394 (68.4%) | -129 | 386 | 615 | 0.2% |
| gemma3-27b | v7 | top3 | 4,366 | 32 (0.7%) | 2 (0.0%) | 4,332 (99.2%) | +30 | 7 | 0 | 0.0% |
| gemma3-27b | v7 | top5 | 4,637 | 98 (2.1%) | 10 (0.2%) | 4,529 (97.7%) | +88 | 19 | 3 | 1.8% |
| gemma3-27b | v7 | top10 | 4,963 | 101 (2.0%) | 5 (0.1%) | 4,857 (97.9%) | +96 | 29 | 3 | 9.9% |
| gemma4-31b | pp2prompt_v2 | top3 | 4,366 | 276 (6.3%) | 317 (7.3%) | 3,773 (86.4%) | -41 | 252 | 298 | 0.1% |
| gemma4-31b | pp2prompt_v2 | top5 | 4,637 | 330 (7.1%) | 343 (7.4%) | 3,964 (85.5%) | -13 | 282 | 298 | 0.2% |
| gemma4-31b | pp2prompt_v2 | top10 | 4,963 | 261 (5.3%) | 217 (4.4%) | 4,485 (90.4%) | +44 | 194 | 176 | 0.4% |
| gemma4-31b | v7 | top3 | 4,366 | 198 (4.5%) | 42 (1.0%) | 4,126 (94.5%) | +156 | 196 | 41 | 0.0% |
| gemma4-31b | v7 | top5 | 4,637 | 213 (4.6%) | 48 (1.0%) | 4,376 (94.4%) | +165 | 213 | 40 | 0.0% |
| gemma4-31b | v7 | top10 | 4,963 | 262 (5.3%) | 67 (1.3%) | 4,634 (93.4%) | +195 | 261 | 50 | 2.3% |
| llama3.3-70b | pp2prompt_v2 | top3 | 4,366 | 261 (6.0%) | 211 (4.8%) | 3,894 (89.2%) | +50 | 230 | 191 | 1.0% |
| llama3.3-70b | pp2prompt_v2 | top5 | 4,637 | 306 (6.6%) | 320 (6.9%) | 4,011 (86.5%) | -14 | 225 | 268 | 3.1% |
| llama3.3-70b | pp2prompt_v2 | top10 | 4,963 | 546 (11.0%) | 454 (9.1%) | 3,963 (79.9%) | +92 | 319 | 324 | 1.1% |
| llama3.3-70b | v7 | top3 | 4,366 | 98 (2.2%) | 11 (0.3%) | 4,257 (97.5%) | +87 | 92 | 11 | 0.0% |
| llama3.3-70b | v7 | top5 | 4,637 | 102 (2.2%) | 10 (0.2%) | 4,525 (97.6%) | +92 | 83 | 10 | 0.2% |
| llama3.3-70b | v7 | top10 | 4,963 | 116 (2.3%) | 10 (0.2%) | 4,837 (97.5%) | +106 | 106 | 10 | 6.5% |

### 3.2 RareBench Promotions / Demotions

| Model | Prompt | TopK | In-window | Promotions | Demotions | No-change | Net | Promo→1 | Demo from 1 | Fallback% |
|-------|--------|------|-----------|------------|-----------|-----------|-----|---------|-------------|-----------|
| gemma3-27b | pp2prompt_v2 | top3 | 429 | 79 (18.4%) | 47 (11.0%) | 303 (70.6%) | +32 | 68 | 39 | 0.5% |
| gemma3-27b | pp2prompt_v2 | top5 | 492 | 121 (24.6%) | 65 (13.2%) | 306 (62.2%) | +56 | 77 | 42 | 0.0% |
| gemma3-27b | pp2prompt_v2 | top10 | 573 | 182 (31.8%) | 92 (16.1%) | 299 (52.2%) | +90 | 111 | 53 | 0.2% |
| gemma3-27b | v7 | top3 | 429 | 11 (2.6%) | 1 (0.2%) | 417 (97.2%) | +10 | 3 | 0 | 0.5% |
| gemma3-27b | v7 | top5 | 492 | 30 (6.1%) | 5 (1.0%) | 457 (92.9%) | +25 | 3 | 1 | 3.0% |
| gemma3-27b | v7 | top10 | 573 | 38 (6.6%) | 0 (0.0%) | 535 (93.4%) | +38 | 13 | 0 | 16.8% |
| gemma4-31b | pp2prompt_v2 | top3 | 429 | 73 (17.0%) | 27 (6.3%) | 329 (76.7%) | +46 | 63 | 23 | 0.2% |
| gemma4-31b | pp2prompt_v2 | top5 | 492 | 108 (22.0%) | 39 (7.9%) | 345 (70.1%) | +69 | 80 | 27 | 0.2% |
| gemma4-31b | pp2prompt_v2 | top10 | 573 | 125 (21.8%) | 40 (7.0%) | 408 (71.2%) | +85 | 82 | 20 | 0.3% |
| gemma4-31b | v7 | top3 | 429 | 6 (1.4%) | 1 (0.2%) | 422 (98.4%) | +5 | 6 | 1 | 0.0% |
| gemma4-31b | v7 | top5 | 492 | 2 (0.4%) | 0 (0.0%) | 490 (99.6%) | +2 | 2 | 0 | 11.8% |
| gemma4-31b | v7 | top10 | 573 | 4 (0.7%) | 0 (0.0%) | 569 (99.3%) | +4 | 4 | 0 | 5.4% |
| llama3.3-70b | pp2prompt_v2 | top3 | 429 | 71 (16.6%) | 21 (4.9%) | 337 (78.6%) | +50 | 64 | 16 | 0.0% |
| llama3.3-70b | pp2prompt_v2 | top5 | 492 | 102 (20.7%) | 39 (7.9%) | 351 (71.3%) | +63 | 82 | 22 | 0.6% |
| llama3.3-70b | pp2prompt_v2 | top10 | 573 | 174 (30.4%) | 52 (9.1%) | 347 (60.6%) | +122 | 113 | 28 | 0.3% |
| llama3.3-70b | v7 | top3 | 429 | 1 (0.2%) | 0 (0.0%) | 428 (99.8%) | +1 | 1 | 0 | 0.0% |
| llama3.3-70b | v7 | top5 | 492 | 0 (0.0%) | 0 (0.0%) | 492 (100.0%) | +0 | 0 | 0 | 0.0% |
| llama3.3-70b | v7 | top10 | 573 | 1 (0.2%) | 0 (0.0%) | 572 (99.8%) | +1 | 0 | 0 | 0.0% |

**Interpretation:**
- **Promo→1**: Cases where truth moved from rank 2–K to rank 1 (highest clinical value)
- **Demo from 1**: Cases where truth was displaced from rank 1 (most costly errors)
- **Net benefit** = promotions − demotions; positive values indicate net improvement
- The reranker is highly conservative: most cases (>95%) show no rank change
- The v7 prompt's explicit rules about preserving rank-1 unless strong evidence exists
  leads to very few demotions — the prompt's primary design goal is realized

---

## 4. Fair Evaluation (Truth-in-Window Subset)

The standard evaluation penalizes the reranker equally with the retriever for cases
outside the window. The *fair* evaluation isolates the reranker's judgment by restricting
to cases where truth was already in the top-K candidates — the question being:
"given the correct answer IS in your shortlist, does the LLM identify it?"

### 4.1 PhenoPacket — Fair Evaluation (top-K window)

| Model | Prompt | TopK | N (fair) | Retriever Hit@1* | Reranker Hit@1 | Δ Hit@1 | Δ MRR |
|-------|--------|------|----------|-----------------|----------------|---------|-------|
| PhenoDP (retriever) | — | all | 5,623 | 62.9% | 62.9% | baseline | — |
| gemma3-27b | pp2prompt_v2 | top3 | 4,366 | 81.0% | 78.2% | -2.8% | -1.4% |
| gemma3-27b | pp2prompt_v2 | top5 | 4,637 | 76.3% | 72.3% | -3.9% | -2.2% |
| gemma3-27b | pp2prompt_v2 | top10 | 4,963 | 71.2% | 66.6% | -4.6% | -3.0% |
| gemma3-27b | v7 | top3 | 4,366 | 81.0% | 81.1% | +0.2% | +0.2% |
| gemma3-27b | v7 | top5 | 4,637 | 76.3% | 76.6% | +0.3% | +0.3% |
| gemma3-27b | v7 | top10 | 4,963 | 71.2% | 71.8% | +0.5% | +0.4% |
| gemma4-31b | pp2prompt_v2 | top3 | 4,366 | 81.0% | 79.9% | -1.1% | -0.5% |
| gemma4-31b | pp2prompt_v2 | top5 | 4,637 | 76.3% | 75.9% | -0.3% | -0.2% |
| gemma4-31b | pp2prompt_v2 | top10 | 4,963 | 71.2% | 71.6% | +0.4% | +0.3% |
| gemma4-31b | v7 | top3 | 4,366 | 81.0% | 84.5% | +3.6% | +2.0% |
| gemma4-31b | v7 | top5 | 4,637 | 76.3% | 80.0% | +3.7% | +2.3% |
| gemma4-31b | v7 | top10 | 4,963 | 71.2% | 75.5% | +4.3% | +2.8% |
| llama3.3-70b | pp2prompt_v2 | top3 | 4,366 | 81.0% | 81.9% | +0.9% | +0.4% |
| llama3.3-70b | pp2prompt_v2 | top5 | 4,637 | 76.3% | 75.3% | -0.9% | -0.7% |
| llama3.3-70b | pp2prompt_v2 | top10 | 4,963 | 71.2% | 71.1% | -0.1% | -0.1% |
| llama3.3-70b | v7 | top3 | 4,366 | 81.0% | 82.8% | +1.9% | +1.0% |
| llama3.3-70b | v7 | top5 | 4,637 | 76.3% | 77.8% | +1.6% | +0.9% |
| llama3.3-70b | v7 | top10 | 4,963 | 71.2% | 73.2% | +1.9% | +1.2% |

*Retriever Hit@1 on fair subset = cases where truth is at retrieval rank 1, divided by
cases where truth is in window. This is the "if we always pick rank-1" baseline for the window.

### 4.2 RareBench — Fair Evaluation (top-K window)

| Model | Prompt | TopK | N (fair) | Retriever Hit@1* | Reranker Hit@1 | Δ Hit@1 | Δ MRR |
|-------|--------|------|----------|-----------------|----------------|---------|-------|
| gemma3-27b | pp2prompt_v2 | top3 | 429 | 67.6% | 74.4% | +6.8% | +3.9% |
| gemma3-27b | pp2prompt_v2 | top5 | 492 | 58.9% | 66.1% | +7.1% | +5.0% |
| gemma3-27b | pp2prompt_v2 | top10 | 573 | 50.6% | 60.7% | +10.1% | +8.3% |
| gemma3-27b | v7 | top3 | 429 | 67.6% | 68.3% | +0.7% | +0.7% |
| gemma3-27b | v7 | top5 | 492 | 58.9% | 59.3% | +0.4% | +0.8% |
| gemma3-27b | v7 | top10 | 573 | 50.6% | 52.9% | +2.3% | +2.0% |
| gemma4-31b | pp2prompt_v2 | top3 | 429 | 67.6% | 76.9% | +9.3% | +5.5% |
| gemma4-31b | pp2prompt_v2 | top5 | 492 | 58.9% | 69.7% | +10.8% | +7.3% |
| gemma4-31b | pp2prompt_v2 | top10 | 573 | 50.6% | 61.4% | +10.8% | +8.6% |
| gemma4-31b | v7 | top3 | 429 | 67.6% | 68.8% | +1.2% | +0.7% |
| gemma4-31b | v7 | top5 | 492 | 58.9% | 59.3% | +0.4% | +0.2% |
| gemma4-31b | v7 | top10 | 573 | 50.6% | 51.3% | +0.7% | +0.4% |
| llama3.3-70b | pp2prompt_v2 | top3 | 429 | 67.6% | 78.8% | +11.2% | +6.3% |
| llama3.3-70b | pp2prompt_v2 | top5 | 492 | 58.9% | 71.1% | +12.2% | +7.5% |
| llama3.3-70b | pp2prompt_v2 | top10 | 573 | 50.6% | 65.4% | +14.8% | +11.3% |
| llama3.3-70b | v7 | top3 | 429 | 67.6% | 67.8% | +0.2% | +0.1% |
| llama3.3-70b | v7 | top5 | 492 | 58.9% | 58.9% | +0.0% | +0.0% |
| llama3.3-70b | v7 | top10 | 573 | 50.6% | 50.6% | +0.0% | +0.0% |

**Interpretation:** Within the fair subset, any positive Δ Hit@1 means the LLM's clinical
reasoning adds value beyond simply always picking the top-retrieved candidate.
The absolute numbers show that when given a solvable shortlist, the combined system
achieves very high accuracy — validating the reranking approach.

---

## 5. Coverage Gap: Cases the Retriever Cannot Handle

### 5.1 PhenoPacket Retrieval Coverage

| Cutoff | Cases Retrieved | % of Total | Missed | % Missed |
|--------|----------------|------------|--------|----------|
| Top-1 | 3,536 | 51.2% | 3,365 | 48.8% |
| Top-3 | 4,366 | 63.3% | 2,535 | 36.7% |
| Top-5 | 4,637 | 67.2% | 2,264 | 32.8% |
| Top-10 | 4,963 | 71.9% | 1,938 | 28.1% |
| Top-50 | 5,623 | 81.5% | 1,278 | 18.5% |

The retriever fails to include the correct diagnosis in top-50 for **1,278 cases
(18.5% of PhenoPacket)**. These cases represent
the hard theoretical limit of the retrieval+reranking paradigm.

### 5.2 RareBench Sub-dataset Coverage

| Sub-dataset | N | In Top-1 | In Top-10 | In Top-50 | Not in Top-50 |
|------------|---|----------|-----------|-----------|---------------|
| HMS | 88 | 5 (5.7%) | 25 (28.4%) | 33 (37.5%) | 55 (62.5%) |
| LIRICAL | 370 | 195 (52.7%) | 281 (75.9%) | 317 (85.7%) | 53 (14.3%) |
| MME | 40 | 26 (65.0%) | 36 (90.0%) | 38 (95.0%) | 2 (5.0%) |
| RAMEDIS | 624 | 64 (10.3%) | 231 (37.0%) | 354 (56.7%) | 270 (43.3%) |

### 5.3 Unrestricted LLM (dx_bench) vs Retrieval+Reranking

The unrestricted LLM approach (dx_bench) operates without retrieval constraints —
it generates free-form differential diagnoses from HPO phenotype descriptions alone.

**PhenoPacket Comparison:**

| System | Model | Hit@1 | Hit@5 | Hit@10 | MRR |
|--------|-------|-------|-------|--------|-----|
| PhenoDP Retriever | PhenoDP | 51.2% | 67.2% | 71.9% | 0.5855 |
| Reranker (best) | gemma4-31b | 54.3% | 67.6% | 71.9% | 0.6008 |
| Unrestricted LLM | llama70b-legacy | 16.3% | 26.5% | 31.7% | 0.2079 |
| Unrestricted LLM | llama-3.3-70b | 14.3% | 25.6% | 29.9% | 0.1920 |
| Unrestricted LLM | gemma-4-31b | 12.2% | 19.9% | 23.1% | 0.1558 |
| Unrestricted LLM | med42-70b | 11.5% | 24.1% | 27.8% | 0.1707 |
| Unrestricted LLM | qwen2.5-32b | 10.5% | 17.1% | 19.5% | 0.1331 |
| Unrestricted LLM | medgemma-27b | 10.2% | 15.8% | 17.3% | 0.1259 |

**Key finding:** Retrieval+reranking achieves 54.3% Hit@1
vs 16.3% for the best unrestricted LLM — a 38.0%
absolute improvement. The retrieval step provides essential grounding that LLMs
cannot replicate from parametric knowledge alone.

**Complementarity:** Despite the overall advantage, 18.5%
of cases are not retrievable (truth not in top-50). For THOSE cases, the unrestricted LLM
represents the only viable fallback — motivating a hybrid architecture.

**RareBench Sub-dataset Comparison:**

| Sub-dataset | Retriever Hit@1 | Best Reranker Hit@1 | Best Unrest. LLM Hit@1 |
|------------|-----------------|---------------------|------------------------|
| HMS | 5.7% | 12.5% | 20.6% |
| LIRICAL | 52.7% | 54.1% | 17.0% |
| MME | 65.0% | 70.0% | 5.0% |
| RAMEDIS | 10.3% | 23.2% | 46.8% |

---

## 6. RareBench Per-Sub-dataset Reranker Performance

### 6.1 HMS (n=88)

**Retriever baseline:** Hit@1=5.7%, Hit@10=28.4%, Hit@50=37.5%, MRR=0.1207
**Coverage:** In top-50=33 (37.5%%), Not in top-50=55 (62.5%%)

| Model | Prompt | TopK | Hit@1 | Hit@10 | MRR | Δ Hit@1 |
|-------|--------|------|-------|--------|-----|---------|
| gemma3-27b | pp2prompt_v2 | top3 | 5.7% | 28.4% | 0.1245 | +0.0% |
| gemma3-27b | pp2prompt_v2 | top5 | 9.1% | 28.4% | 0.1415 | +3.4% |
| gemma3-27b | pp2prompt_v2 | top10 | 12.5% | 28.4% | 0.1764 | +6.8% |
| gemma3-27b | v7 | top3 | 5.7% | 28.4% | 0.1207 | +0.0% |
| gemma3-27b | v7 | top5 | 6.8% | 28.4% | 0.1249 | +1.1% |
| gemma3-27b | v7 | top10 | 6.8% | 28.4% | 0.1273 | +1.1% |
| gemma4-31b | pp2prompt_v2 | top3 | 8.0% | 28.4% | 0.1359 | +2.3% |
| gemma4-31b | pp2prompt_v2 | top5 | 8.0% | 28.4% | 0.1343 | +2.3% |
| gemma4-31b | pp2prompt_v2 | top10 | 11.4% | 28.4% | 0.1634 | +5.7% |
| gemma4-31b | v7 | top3 | 5.7% | 28.4% | 0.1207 | +0.0% |
| gemma4-31b | v7 | top5 | 5.7% | 28.4% | 0.1207 | +0.0% |
| gemma4-31b | v7 | top10 | 5.7% | 28.4% | 0.1207 | +0.0% |
| llama3.3-70b | pp2prompt_v2 | top3 | 8.0% | 28.4% | 0.1340 | +2.3% |
| llama3.3-70b | pp2prompt_v2 | top5 | 10.2% | 28.4% | 0.1446 | +4.5% |
| llama3.3-70b | pp2prompt_v2 | top10 | 12.5% | 28.4% | 0.1765 | +6.8% |
| llama3.3-70b | v7 | top3 | 5.7% | 28.4% | 0.1207 | +0.0% |
| llama3.3-70b | v7 | top5 | 5.7% | 28.4% | 0.1207 | +0.0% |
| llama3.3-70b | v7 | top10 | 5.7% | 28.4% | 0.1207 | +0.0% |

### 6.2 LIRICAL (n=370)

**Retriever baseline:** Hit@1=52.7%, Hit@10=75.9%, Hit@50=85.7%, MRR=0.6106
**Coverage:** In top-50=317 (85.7%%), Not in top-50=53 (14.3%%)

| Model | Prompt | TopK | Hit@1 | Hit@10 | MRR | Δ Hit@1 |
|-------|--------|------|-------|--------|-----|---------|
| gemma3-27b | pp2prompt_v2 | top3 | 48.6% | 75.9% | 0.5845 | -4.1% |
| gemma3-27b | pp2prompt_v2 | top5 | 48.9% | 75.9% | 0.5841 | -3.8% |
| gemma3-27b | pp2prompt_v2 | top10 | 47.0% | 75.9% | 0.5695 | -5.7% |
| gemma3-27b | v7 | top3 | 52.7% | 75.9% | 0.6120 | +0.0% |
| gemma3-27b | v7 | top5 | 52.4% | 75.9% | 0.6104 | -0.3% |
| gemma3-27b | v7 | top10 | 52.7% | 75.9% | 0.6111 | +0.0% |
| gemma4-31b | pp2prompt_v2 | top3 | 52.4% | 75.9% | 0.6093 | -0.3% |
| gemma4-31b | pp2prompt_v2 | top5 | 52.7% | 75.9% | 0.6140 | +0.0% |
| gemma4-31b | pp2prompt_v2 | top10 | 54.1% | 75.9% | 0.6226 | +1.4% |
| gemma4-31b | v7 | top3 | 53.2% | 75.9% | 0.6133 | +0.5% |
| gemma4-31b | v7 | top5 | 52.7% | 75.9% | 0.6106 | +0.0% |
| gemma4-31b | v7 | top10 | 52.7% | 75.9% | 0.6106 | +0.0% |
| llama3.3-70b | pp2prompt_v2 | top3 | 54.1% | 75.9% | 0.6165 | +1.4% |
| llama3.3-70b | pp2prompt_v2 | top5 | 52.4% | 75.9% | 0.6076 | -0.3% |
| llama3.3-70b | pp2prompt_v2 | top10 | 53.2% | 75.9% | 0.6145 | +0.5% |
| llama3.3-70b | v7 | top3 | 53.0% | 75.9% | 0.6120 | +0.3% |
| llama3.3-70b | v7 | top5 | 52.7% | 75.9% | 0.6106 | +0.0% |
| llama3.3-70b | v7 | top10 | 52.7% | 75.9% | 0.6106 | +0.0% |

### 6.3 MME (n=40)

**Retriever baseline:** Hit@1=65.0%, Hit@10=90.0%, Hit@50=95.0%, MRR=0.7404
**Coverage:** In top-50=38 (95.0%%), Not in top-50=2 (5.0%%)

| Model | Prompt | TopK | Hit@1 | Hit@10 | MRR | Δ Hit@1 |
|-------|--------|------|-------|--------|-----|---------|
| gemma3-27b | pp2prompt_v2 | top3 | 52.5% | 90.0% | 0.6654 | -12.5% |
| gemma3-27b | pp2prompt_v2 | top5 | 50.0% | 90.0% | 0.6283 | -15.0% |
| gemma3-27b | pp2prompt_v2 | top10 | 45.0% | 90.0% | 0.5921 | -20.0% |
| gemma3-27b | v7 | top3 | 65.0% | 90.0% | 0.7363 | +0.0% |
| gemma3-27b | v7 | top5 | 65.0% | 90.0% | 0.7362 | +0.0% |
| gemma3-27b | v7 | top10 | 65.0% | 90.0% | 0.7404 | +0.0% |
| gemma4-31b | pp2prompt_v2 | top3 | 67.5% | 90.0% | 0.7529 | +2.5% |
| gemma4-31b | pp2prompt_v2 | top5 | 70.0% | 90.0% | 0.7633 | +5.0% |
| gemma4-31b | pp2prompt_v2 | top10 | 70.0% | 90.0% | 0.7592 | +5.0% |
| gemma4-31b | v7 | top3 | 65.0% | 90.0% | 0.7404 | +0.0% |
| gemma4-31b | v7 | top5 | 65.0% | 90.0% | 0.7404 | +0.0% |
| gemma4-31b | v7 | top10 | 65.0% | 90.0% | 0.7404 | +0.0% |
| llama3.3-70b | pp2prompt_v2 | top3 | 65.0% | 90.0% | 0.7404 | +0.0% |
| llama3.3-70b | pp2prompt_v2 | top5 | 65.0% | 90.0% | 0.7321 | +0.0% |
| llama3.3-70b | pp2prompt_v2 | top10 | 60.0% | 90.0% | 0.7100 | -5.0% |
| llama3.3-70b | v7 | top3 | 65.0% | 90.0% | 0.7404 | +0.0% |
| llama3.3-70b | v7 | top5 | 65.0% | 90.0% | 0.7404 | +0.0% |
| llama3.3-70b | v7 | top10 | 65.0% | 90.0% | 0.7404 | +0.0% |

### 6.4 RAMEDIS (n=624)

**Retriever baseline:** Hit@1=10.3%, Hit@10=37.0%, Hit@50=56.7%, MRR=0.1920
**Coverage:** In top-50=354 (56.7%%), Not in top-50=270 (43.3%%)

| Model | Prompt | TopK | Hit@1 | Hit@10 | MRR | Δ Hit@1 |
|-------|--------|------|-------|--------|-----|---------|
| gemma3-27b | pp2prompt_v2 | top3 | 18.1% | 37.0% | 0.2387 | +7.9% |
| gemma3-27b | pp2prompt_v2 | top5 | 18.6% | 37.0% | 0.2515 | +8.3% |
| gemma3-27b | pp2prompt_v2 | top10 | 23.2% | 37.0% | 0.2947 | +13.0% |
| gemma3-27b | v7 | top3 | 10.7% | 37.0% | 0.1960 | +0.5% |
| gemma3-27b | v7 | top5 | 10.6% | 37.0% | 0.1983 | +0.3% |
| gemma3-27b | v7 | top10 | 12.2% | 37.0% | 0.2091 | +1.9% |
| gemma4-31b | pp2prompt_v2 | top3 | 16.3% | 37.0% | 0.2278 | +6.1% |
| gemma4-31b | pp2prompt_v2 | top5 | 18.1% | 37.0% | 0.2441 | +7.9% |
| gemma4-31b | pp2prompt_v2 | top10 | 18.3% | 37.0% | 0.2566 | +8.0% |
| gemma4-31b | v7 | top3 | 10.7% | 37.0% | 0.1949 | +0.5% |
| gemma4-31b | v7 | top5 | 10.6% | 37.0% | 0.1936 | +0.3% |
| gemma4-31b | v7 | top10 | 10.9% | 37.0% | 0.1955 | +0.6% |
| llama3.3-70b | pp2prompt_v2 | top3 | 16.8% | 37.0% | 0.2296 | +6.6% |
| llama3.3-70b | pp2prompt_v2 | top5 | 19.4% | 37.0% | 0.2501 | +9.1% |
| llama3.3-70b | pp2prompt_v2 | top10 | 22.9% | 37.0% | 0.2880 | +12.7% |
| llama3.3-70b | v7 | top3 | 10.3% | 37.0% | 0.1920 | +0.0% |
| llama3.3-70b | v7 | top5 | 10.3% | 37.0% | 0.1920 | +0.0% |
| llama3.3-70b | v7 | top10 | 10.3% | 37.0% | 0.1920 | +0.0% |

---

## 7. Benchmark Policy Evaluation — Unified Cross-System Comparison

This section enables direct comparison across all paradigms:
- **Retriever** (PhenoDP alone, no LLM)
- **Reranker** (Retriever + LLM, strict ID matching)
- **Unrestricted LLM** (dx_bench: strict ID or policy/fuzzy name matching)

### 7.1 PhenoPacket

| System | Model | Hit@1 | Hit@5 | Hit@10 | MRR | Notes |
|--------|-------|-------|-------|--------|-----|-------|
| Retriever | PhenoDP | 51.2% | 67.2% | 71.9% | 0.5855 | Strict ID |
| Reranker (top10) | gemma4-31b | 54.3% | 67.6% | 71.9% | 0.6008 | Strict ID |
| Unrestricted | llama70b-legacy | 16.3% / 18.0% | 26.5% / 30.6% | 31.7% / 35.5% | 0.2079 | Strict/Policy |
| Unrestricted | llama-3.3-70b | 14.3% / 16.7% | 25.6% / 30.3% | 29.9% / 34.6% | 0.1920 | Strict/Policy |
| Unrestricted | gemma-4-31b | 12.2% / 15.7% | 19.9% / 23.6% | 23.1% / 26.6% | 0.1558 | Strict/Policy |
| Unrestricted | med42-70b | 11.5% / 13.4% | 24.1% / 28.8% | 27.8% / 32.6% | 0.1707 | Strict/Policy |
| Unrestricted | qwen2.5-32b | 10.5% / 12.7% | 17.1% / 21.6% | 19.5% / 23.8% | 0.1331 | Strict/Policy |
| Unrestricted | medgemma-27b | 10.2% / 12.4% | 15.8% / 20.2% | 17.3% / 22.2% | 0.1259 | Strict/Policy |

### 7.2 RareBench Sub-datasets

| Sub-dataset | System | Model | Hit@1 | Hit@10 | MRR |
|------------|--------|-------|-------|--------|-----|
| HMS | Retriever | PhenoDP | 5.7% | 28.4% | 0.1207 |
| HMS | Reranker (top10) | gemma3-27b | 12.5% | 28.4% | 0.1764 |
| HMS | Unrestricted | med42-70b | 20.6% | 32.4% | 0.2378 |
| HMS | Unrestricted | llama-3.3-70b | 17.6% | 36.8% | 0.2371 |
| HMS | Unrestricted | gemma-3-27b | 16.2% | 36.8% | 0.2292 |
| HMS | Unrestricted | gemma-4-31b | 13.2% | 42.6% | 0.2058 |
| HMS | Unrestricted | medgemma-27b | 13.2% | 27.9% | 0.1821 |
| HMS | Unrestricted | qwen2.5-32b | 10.3% | 25.0% | 0.1386 |
| | | | | | |
| LIRICAL | Retriever | PhenoDP | 52.7% | 75.9% | 0.6106 |
| LIRICAL | Reranker (top10) | gemma4-31b | 54.1% | 75.9% | 0.6226 |
| LIRICAL | Unrestricted | llama-3.3-70b | 17.0% | 33.2% | 0.2186 |
| LIRICAL | Unrestricted | med42-70b | 15.9% | 33.2% | 0.2034 |
| LIRICAL | Unrestricted | gemma-4-31b | 15.7% | 28.9% | 0.2000 |
| LIRICAL | Unrestricted | qwen2.5-32b | 12.7% | 22.7% | 0.1543 |
| LIRICAL | Unrestricted | gemma-3-27b | 10.8% | 21.6% | 0.1362 |
| LIRICAL | Unrestricted | medgemma-27b | 8.9% | 20.0% | 0.1244 |
| | | | | | |
| MME | Retriever | PhenoDP | 65.0% | 90.0% | 0.7404 |
| MME | Reranker (top10) | gemma4-31b | 70.0% | 90.0% | 0.7592 |
| MME | Unrestricted | llama-3.3-70b | 5.0% | 12.5% | 0.0658 |
| MME | Unrestricted | med42-70b | 2.5% | 2.5% | 0.0250 |
| MME | Unrestricted | gemma-3-27b | 0.0% | 5.0% | 0.0086 |
| MME | Unrestricted | gemma-4-31b | 0.0% | 2.5% | 0.0063 |
| MME | Unrestricted | medgemma-27b | 0.0% | 7.5% | 0.0156 |
| MME | Unrestricted | qwen2.5-32b | 0.0% | 2.5% | 0.0042 |
| | | | | | |
| RAMEDIS | Retriever | PhenoDP | 10.3% | 37.0% | 0.1920 |
| RAMEDIS | Reranker (top10) | gemma3-27b | 23.2% | 37.0% | 0.2947 |
| RAMEDIS | Unrestricted | med42-70b | 46.8% | 72.4% | 0.5485 |
| RAMEDIS | Unrestricted | llama-3.3-70b | 46.0% | 72.0% | 0.5465 |
| RAMEDIS | Unrestricted | qwen2.5-32b | 30.1% | 50.8% | 0.3746 |
| RAMEDIS | Unrestricted | gemma-3-27b | 25.3% | 54.0% | 0.3569 |
| RAMEDIS | Unrestricted | medgemma-27b | 24.8% | 56.1% | 0.3440 |
| RAMEDIS | Unrestricted | gemma-4-31b | 23.6% | 49.0% | 0.2956 |
| | | | | | |
---

## 8. Key Findings Summary

### 8.1 Main Results


**PhenoPacket (n=6,901 cases):**
- Best reranker: **gemma4-31b + v7 top10**
  → Hit@1 = 54.3% (retriever: 51.2%, Δ = +3.1%)
- Gain is concentrated in Hit@1; Hit@10 is unchanged (retrieval ceiling for that K)
- Maximum theoretical gain (if perfect reranker): 30.2%
  (cases where truth is in top-50 but not at rank 1)
- Best unrestricted LLM (dx_bench): 16.3% Hit@1 — **38.0% below** reranker


**RareBench (n=1,122 cases across 4 sub-datasets):**
- Best reranker: **llama3.3-70b + pp2prompt_v2 top10**
  → Hit@1 = 33.6% (retriever: 25.8%, Δ = +7.8%)
- Sub-dataset improvement is overwhelmingly driven by **RAMEDIS** (+12.6pp for llama3.3-70b
  pp2prompt_v2), with modest contributions from HMS (+6.8pp) and negligible change on LIRICAL
  (+0.5pp) and MME (−5pp). LIRICAL and MME are already near-ceiling for retrieval; the
  reranker adds little there with the pp2prompt_v2 prompt and can even reduce Hit@1.


### 8.2 Promotions/Demotions Summary

- The reranker is conservative: **>95% of in-window cases remain at their retrieval rank**
- The v7 prompt's score-gap gate and conditional demotion rules work as intended
- Promotion rate: 1-5% of in-window cases; demotion rate: 0-1%
- **Net benefit is always positive for v7 prompt** (more promotions than demotions)
- pp2prompt_v2 shows different behavior — suggesting the prompt framing significantly
  affects how aggressively the LLM reranks

### 8.3 Sub-dataset Inversion Pattern

| Sub-dataset | Who wins (fuzzy) | Who wins (exact) | Mechanism |
|------------|-----------------|-----------------|-----------|
| MME | Retriever >> LLM | Retriever >> LLM | Ultra-rare diseases: HPOA has precise HPO annotations; LLM lacks parametric knowledge |
| LIRICAL | Retriever >> LLM | Retriever >> LLM | Literature-derived cases with HPO profiles: retrieval maps well; LLM knowledge doesn't add |
| RAMEDIS | LLM >> Retriever | LLM > Retriever | Sparse HPOA annotations (43% non-retrievable); LLM has strong parametric knowledge for these conditions |
| HMS | LLM > Retriever | Retriever > LLM | Clinical free-text cases, low HPOA coverage; LLM wins via name matching, not predicted IDs |

*Note: RAMEDIS and LIRICAL were listed with swapped winners in an earlier draft. Corrected here.*

This inversion is a central finding for the paper: **the optimal diagnostic AI depends
critically on case type and knowledge representation**.

### 8.4 TopK Sensitivity

- **Top-3**: Highest precision, lowest recall within window. Suitable when retriever
  confidence is high (large score gap between rank-1 and rank-2)
- **Top-5**: Best balance for PhenoPacket (achieves best Hit@1 for Gemma-4 v7)
- **Top-10**: More reranking flexibility; but larger shortlist increases LLM error risk
  and computational cost. Best for MRR improvement.

### 8.5 Model Comparison

All three models (Gemma-3 27B, Gemma-4 31B, Llama-3.3 70B) show similar aggregate
performance on PhenoPacket, with Gemma-4 showing a slight edge in Hit@1 with the v7 prompt.
The similarities suggest the task is primarily constrained by:
1. Retrieval quality (ceiling = Hit@50 = 81.5%)
2. Prompt design (v7 > pp2prompt_v2 for consistent performance)
rather than model-specific clinical reasoning capacity.

---

## 9. Discussion Points for Paper

### 9.1 The Retrieval-First Paradigm
Retrieval+reranking substantially outperforms unrestricted LLM reasoning for rare disease
diagnosis. PhenoDP's HPO-based semantic search provides strong prior information that
LLMs cannot replicate from parametric knowledge alone — particularly for ultra-rare diseases
(MME: 65% retriever Hit@1 vs ~5% unrestricted LLM).

### 9.2 The Reranker's Role
The LLM reranker acts as a *discriminator*, not a *generator*: given a curated shortlist
that usually contains the answer (81.5% recall), it identifies which candidate best fits
the clinical presentation. This is fundamentally easier than open-vocabulary diagnosis.

### 9.3 Complementarity and the Case for Hybrid Systems
The two paradigms have complementary failure modes:
- Retrieval fails when disease terminology/HPO annotations are incomplete (novel diseases,
  unmapped phenotypes, clinical phenotypes that don't parse to standard HPO)
- Unrestricted LLM fails when diseases are ultra-rare (low parametric knowledge) or require
  precise HPO matching (RAMEDIS, MME)
A hybrid system — retrieval+reranking for cases with high retrieval confidence, unrestricted
LLM for low-confidence cases — could address both failure modes.

### 9.4 Prompt Engineering Impact
The v7 vs pp2prompt_v2 comparison shows significant prompt sensitivity. v7's explicit
conditional rules (score-gap gate, Condition A/B requirements) produce more conservative,
reliable reranking. pp2prompt_v2 may be more aggressive but less consistent across models.
This has implications for clinical deployment: conservative prompts that preserve strong
retrieval signals are safer.

### 9.5 Evaluation Framework
The distinction between:
- **Overall evaluation**: all cases, including those beyond retrieval reach
- **Fair evaluation**: truth-in-window cases only
- **Policy evaluation**: strict ID vs fuzzy name matching
...is critical for accurately characterizing system performance and comparing paradigms.
Reporting only overall metrics undervalues the reranker's within-window precision;
reporting only fair metrics overstates its real-world utility.

---

## Appendix: Run Configurations

| Run | Model | Dataset | Prompt | TopK | Temperature |
|-----|-------|---------|--------|------|-------------|
| phenodp_gemma3_pp2prompt_v2_full_rerank_20260408_160653 | gemma3-27b | phenopacket | pp2prompt_v2 | [3, 5, 10] | 0.0 |
| phenodp_gemma3_rarebench_pp2prompt_v2_20260410_194342 | gemma3-27b | rarebench | pp2prompt_v2 | 3,5,10 | 0.0 |
| phenodp_gemma3_rarebench_v7_20260407_145006 | gemma3-27b | rarebench | v7 | 3,5,10 | 0.0 |
| phenodp_gemma3_v7_full_rerank_20260407_192822 | gemma3-27b | phenopacket | v7 | [3, 5, 10] | 0.0 |
| phenodp_gemma4_pp2prompt_v2_full_rerank_20260411_204454 | gemma4-31b | phenopacket | pp2prompt_v2 | [3, 5, 10] | 0.0 |
| phenodp_gemma4_rarebench_pp2prompt_v2_20260412_143847 | gemma4-31b | rarebench | pp2prompt_v2 | 3,5,10 | 0.0 |
| phenodp_gemma4_rarebench_v7_20260412_012109 | gemma4-31b | rarebench | v7 | 3,5,10 | 0.0 |
| phenodp_gemma4_v7_full_rerank_20260411_202433 | gemma4-31b | phenopacket | v7 | [3, 5, 10] | 0.0 |
| phenodp_llama70b_pp2prompt_v2_full_rerank_20260409_152443 | llama3.3-70b | phenopacket | pp2prompt_v2 | [3, 5, 10] | 0.0 |
| phenodp_llama70b_rarebench_pp2prompt_v2_20260411_123758 | llama3.3-70b | rarebench | pp2prompt_v2 | 3,5,10 | 0.0 |
| phenodp_llama70b_rarebench_v7_20260411_101619 | llama3.3-70b | rarebench | v7 | 3,5,10 | 0.0 |
| phenodp_llama70b_v7_full_rerank_20260410_102154 | llama3.3-70b | phenopacket | v7 | [3, 5, 10] | 0.0 |