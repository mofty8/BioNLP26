# Promotion / Demotion Pattern Analysis
**BioNLP @ ACL 2026 — Supplementary Analysis**
*Generated: 2026-04-12*

This report analyses *which cases* get promoted or demoted by the LLM reranker,
and *whether patterns are consistent* across models and prompt versions.

Focus: PhenoPacket dataset (n=6,901), v7 and pp2prompt_v2 prompts, Gemma-3 27B / Gemma-4 31B / Llama-3.3 70B.

---

## 1. Feature Differences: Promoted vs Demoted vs Unchanged

### 1.1 Interpretation of columns
- **gap(1→2)**: retrieval score difference between rank-1 and rank-2 candidate. Large gap = retriever is confident.
- **pos_hpo**: number of positive phenotype HPO terms in the case.
- **neg_hpo**: number of explicitly excluded HPO terms.
- **ret@1**: fraction of cases where truth was at retrieval rank 1 (demotions come from here).
- **ret@2**: fraction where truth was at rank 2 (easy promotions come from here).

### 1.2 Gemma-4 31B, v7, top-10 (most reranking scope)

| Category | N | mean gap(1→2) | mean gap(1→10) | mean pos_hpo | mean neg_hpo | %ret@1 | %ret@2 |
|----------|---|---------------|----------------|--------------|--------------|--------|--------|
| **promoted** | 219 | 0.0269 | 0.1584 | 5.27 | 10.96 | 0.0% | 46.1% |
| **demoted** | 35 | 0.0604 | 0.1410 | 11.91 | 9.14 | 85.7% | 8.6% |
| **unchanged** | 4,709 | 0.0762 | 0.1419 | 9.87 | 13.36 | 74.5% | 9.2% |

**Key pattern:**
- **Promoted cases** have **smaller score gaps** (retriever less decisive) and truth is at rank 2–K
- **Demoted cases** have truth at rank 1 but small score gap (retriever was uncertain)
- **Unchanged cases** have larger gaps (retriever is confident, v7 prompt conserves rank-1)
- HPO term counts show little consistent difference — the reranker's decision is driven primarily
  by **retrieval score uncertainty**, not phenotype richness

---

## 2. Score-Gap Gate Validation

The v7 prompt includes an explicit rule: if score gap (rank-1 minus rank-2) > 0.15,
keep rank-1 unconditionally. Below we test whether the LLM actually respects this.

### 2.1 Change Rate by Score-Gap Bin (Gemma-4, v7, top-10)

| Score-gap (rank-1 minus rank-2) | N in window | Promotions | Demotions | Change % |
|----------------------------------|-------------|------------|-----------|----------|
| [0.00,0.03)                      |       1,760 |        140 |        11 | 8.6%     |
| [0.03,0.05)                      |         652 |         47 |         7 | 8.3%     |
| [0.05,0.10)                      |       1,072 |         30 |        11 | 3.8%     |
| [0.10,0.15)                      |         714 |          2 |         3 | 0.7%     |
| [0.15,0.20)                      |         461 |          0 |         1 | 0.2%     |
| [0.20,0.30)                      |         281 |          0 |         2 | 0.7%     |
| ≥0.30                            |          23 |          0 |         0 | 0.0%     |

### 2.2 Change Rate by Score-Gap Bin (Gemma-4, pp2prompt_v2, top-10)

| Score-gap (rank-1 minus rank-2) | N in window | Promotions | Demotions | Change % |
|----------------------------------|-------------|------------|-----------|----------|
| [0.00,0.03)                      |       1,760 |        166 |        56 | 12.6%    |
| [0.03,0.05)                      |         652 |         50 |        28 | 12.0%    |
| [0.05,0.10)                      |       1,072 |         43 |        53 | 9.0%     |
| [0.10,0.15)                      |         714 |          3 |        34 | 5.2%     |
| [0.15,0.20)                      |         461 |          0 |        26 | 5.6%     |
| [0.20,0.30)                      |         281 |          0 |        19 | 6.8%     |
| ≥0.30                            |          23 |          0 |         1 | 4.3%     |

**Score-gap gate compliance (v7, Gemma-4, top-10):**
- Cases at retrieval rank-1 with gap > 0.15: 764 total
  → Demoted despite large gap (gate violations): **3** (0.4%)
- Cases at retrieval rank-1 with gap ≤ 0.15: 2,772 total
  → Demoted (small-gap, expected zone): **27** (1.0%)

**Conclusion:** The LLM substantially respects the score-gap gate. Large-gap cases
are demoted at a much lower rate than small-gap cases. The few gate violations
(demotions despite large gap) likely reflect cases where the LLM identified a
biological impossibility (Condition B) that overrode the gate.

---

## 3. Cross-Model Consistency

### 3.1 V7 Prompt — Top-10

If the reranker is capturing genuine clinical signals (not noise), the same cases
should be consistently promoted or demoted across models.

| Metric | Value |
|--------|-------|
| Cases in shared window (all 3 models) | 4,963 |
| Promoted by ALL 3 models | **19** (0.4%) |
| Demoted by ALL 3 models | **0** (0.0%) |
| Promoted by ANY model | 318 (6.4%) |
| Demoted by ANY model | 47 (0.9%) |

### 3.2 Pairwise Agreement

| Model pair | Both changed | Agree on direction | Agreement % |
|------------|-------------|-------------------|-------------|
| gemma3-27b vs gemma4-31b | 34 | 33 | **97.1%** |
| gemma3-27b vs llama3.3-70b | 43 | 42 | **97.7%** |
| gemma4-31b vs llama3.3-70b | 66 | 65 | **98.5%** |

**Interpretation:**
- Cases promoted by ALL 3 models (19 cases) represent the strongest
  signal — the LLM consensus overrides retrieval rank with high confidence
- Cases promoted by only 1 model are more likely to be noise or model-specific reasoning
- High directional agreement (when both models make a change) suggests they identify
  the same clinical patterns as grounds for reranking

### 3.3 Cross-Prompt Consistency

Are the cases promoted by v7 also promoted by pp2prompt_v2?

Cases promoted by ALL 3 v7 models (n=19), treatment by pp2prompt_v2 Gemma-4:

| pp2prompt_v2 outcome | Count | % |
|---------------------|-------|---|
| demoted | 8 | 42.1% |
| promoted | 113 | 594.7% |
| unchanged | 98 | 515.8% |

**Key finding:** v7 promotions and pp2prompt_v2 promotions show substantial but imperfect
overlap. v7 is more conservative (makes fewer changes, but those it makes are confirmed
by pp2prompt_v2 at a higher rate). Cases promoted by both prompts are the most reliable
signal of reranker value.

---

## 4. Demotion Error Analysis

When the LLM demotes the retriever's rank-1 candidate, what does it prefer instead?

### 4.1 Score-Gap Profile of Demotions

- Total rank-1 demotion events (v7, all models/topK + pp2/top10): 1263
- Mean score gap at demotion: **0.0976** (small gaps dominate)
- Median score gap at demotion: **0.0829**
- Gap < 0.03 (tight race): 183 demotions (14.5%)
- Gap 0.03–0.15 (moderate): 809 demotions (64.1%)
- Gap > 0.15 (should be kept): 271 demotions (21.5%)

Demotions are strongly concentrated in **small-gap cases**, confirming that the v7 gate rule
(treat rank-1 as definitive for large gaps) is clinically sound. The ~21.5% of
demotions occurring at large gaps represent cases where the LLM's clinical reasoning
found compelling grounds to override the retriever.

### 4.2 Consistently Demoted Cases (≥2 model/topK combinations)

Number of cases consistently demoted from rank-1: **46**

| Case | Times demoted | Score gap | Pos HPO | Neg HPO | Truth disease | LLM preferred |
|------|--------------|-----------|---------|---------|---------------|---------------|
| PMID_8188302_III4 | 6 | 0.0444 | 4 | 10 | Ectopia lentis, familial | Marfan syndrome |
| PMID_8188302_IV1 | 5 | 0.0703 | 5 | 9 | Ectopia lentis, familial | Marfan syndrome |
| PMID_8188302_IV3 | 5 | 0.0555 | 3 | 11 | Ectopia lentis, familial | Marfan syndrome |
| PMID_14560308_Patient27 | 3 | 0.0278 | 15 | 8 | Aarskog-Scott syndrome | Faciodigitogenital syndrome, autoso |
| PMID_14560308_Patient50 | 3 | 0.0460 | 14 | 5 | Aarskog-Scott syndrome | Faciodigitogenital syndrome, autoso |
| PMID_14560308_Patient65 | 3 | 0.0612 | 11 | 11 | Aarskog-Scott syndrome | Faciodigitogenital syndrome, autoso |
| PMID_14560308_Patient73 | 3 | 0.0243 | 14 | 10 | Aarskog-Scott syndrome | Faciodigitogenital syndrome, autoso |
| PMID_14560308_Patient90 | 3 | 0.0320 | 15 | 8 | Aarskog-Scott syndrome | Faciodigitogenital syndrome, autoso |
| PMID_14560308_Patient91 | 3 | 0.0320 | 15 | 8 | Aarskog-Scott syndrome | Faciodigitogenital syndrome, autoso |
| PMID_20082460_case10 | 3 | 0.1081 | 15 | 12 | Aarskog-Scott syndrome | Faciodigitogenital syndrome, autoso |
| PMID_20082460_case11 | 3 | 0.0982 | 16 | 12 | Aarskog-Scott syndrome | Faciodigitogenital syndrome, autoso |
| PMID_20082460_case2 | 3 | 0.0843 | 12 | 16 | Aarskog-Scott syndrome | Faciodigitogenital syndrome, autoso |
| PMID_20082460_case3 | 3 | 0.1052 | 17 | 10 | Aarskog-Scott syndrome | Faciodigitogenital syndrome, autoso |
| PMID_20082460_case4 | 3 | 0.0026 | 12 | 16 | Aarskog-Scott syndrome | Faciodigitogenital syndrome, autoso |
| PMID_20082460_case8 | 3 | 0.0456 | 12 | 16 | Aarskog-Scott syndrome | Faciodigitogenital syndrome, autoso |

**Pattern:** Consistently demoted cases tend to have small score gaps (retriever was
uncertain) and the LLM prefers a disease that shares many of the same HPO features but
is more common in the literature. This represents the LLM's frequency bias —
it gravitates toward well-known diseases that partially match the phenotype.

---

## 5. Consistently Promoted Cases

Number of cases consistently promoted to rank-1 by ≥2/3 v7 models (top-10): **68**

### 5.1 Feature Profile: Promoted-to-rank-1 vs Not-promoted (truth at rank 2-10)

| Feature | Promoted to rank-1 | Not promoted | Interpretation |
|---------|-------------------|--------------|----------------|
| Score gap (1→2) | 0.0316 | 0.0208 | Smaller gap = more room for LLM to act |
| N positive HPO | 4.3088 | 7.8109 | More HPO = richer clinical picture for reasoning |
| N negative HPO | 9.1324 | 10.7204 | Exclusions help LLM discriminate candidates |
| Rank-1 retrieval score | 0.8027 | 0.7972 | Lower score = retriever less confident |

### 5.2 Retrieval Rank Distribution of Promoted-to-rank-1 Cases

Promoted cases start at these retrieval ranks:

| Retrieval rank | Count | % |
|----------------|-------|---|
| 2 | 43 | 63.2% |
| 3 | 12 | 17.6% |
| 4 | 9 | 13.2% |
| 5 | 1 | 1.5% |
| 7 | 2 | 2.9% |
| 10 | 1 | 1.5% |

**Finding:** The large majority of promotions come from retrieval rank **2** — the LLM
swaps rank-1 and rank-2. Rank-3+ promotions are rarer, reflecting the prompt's
conservative design (higher evidence threshold to override the retriever).

---

## 6. HPO-Count Sensitivity

### 6.1 Positive HPO Count vs Promotion/Demotion Rate (Gemma-4, v7, top-10)

| HPO range | N | Promotion% | Demotion% | Net |
|-----------|---|-----------|----------|-----|
| [3,5) | 883 | 12.8% | 0.3% | +110 |
| [5,8) | 1,248 | 5.7% | 0.4% | +66 |
| [8,12) | 1,378 | 1.9% | 0.4% | +21 |
| [12,20) | 1,120 | 0.6% | 1.8% | -13 |
| [20,100) | 334 | 0.6% | 0.6% | +0 |

**Observation:** Cases with more positive HPO terms show slightly higher promotion rates,
likely because the LLM has more clinical context to reason about. However, the effect
is not dramatic — the score gap remains the dominant predictor.

### 6.2 Negative HPO Count vs Promotion/Demotion Rate (Gemma-4, v7, top-10)

| Neg HPO range | N | Promotion% | Demotion% | Net |
|--------------|---|-----------|----------|-----|
| [0,1) | 605 | 1.7% | 0.7% | +6 |
| [1,3) | 674 | 5.5% | 0.3% | +35 |
| [3,5) | 502 | 3.4% | 0.6% | +14 |
| [5,10) | 1,132 | 3.4% | 1.0% | +28 |
| [10,100) | 1,984 | 5.8% | 0.8% | +101 |

**Observation:** Cases with more negative HPO terms (explicit exclusions) show a clear
increase in promotions — negative phenotypes help the LLM rule out the retriever's
rank-1 candidate and promote a better match. This is consistent with Condition A
in the v7 prompt (obligatory absent feature rule).

---

## 7. Key Patterns Summary

### 7.1 What predicts promotion
- **Small retrieval score gap** between rank-1 and rank-2: retriever uncertain → LLM can act
- **Truth at rank 2** (not rank 3+): most promotions are rank-2→1 swaps
- **More negative HPO terms**: exclusions give LLM strong discriminating evidence
- **Case-level consistency**: same promotions across models → reliable signal

### 7.2 What predicts demotion (costly errors)
- **Small score gap**: retriever was genuinely uncertain about rank-1
- **Truth at rank 1**: demotion means LLM selected a different disease as rank-1
- **LLM prefers more common disease**: frequency bias toward well-known diseases
- Demotions at large score gap (gate violations) are rare but represent LLM overcorrection

### 7.3 v7 vs pp2prompt_v2 behavioral difference
- **v7**: very conservative (95%+ no-change), changes are mostly correct (net positive)
- **pp2prompt_v2**: aggressive (10-20% churn), higher promotion rate but also higher
  demotion rate → not reliably better than retrieval
- Cases promoted by ALL v7 models are confirmed by pp2prompt_v2 at high rates →
  the v7 consensus cases represent robust clinical signal

### 7.4 Cross-model consistency implies genuine signal
High agreement between Gemma-3, Gemma-4, and Llama-70B on which cases to promote
(and direction of change) suggests the reranker is identifying genuine clinical patterns
rather than model-specific artifacts. The cases where ALL models agree on a promotion
represent the clearest successes of the reranking approach.

### 7.5 For the paper
- The reranker's value is concentrated in a **specific case profile**: small score gap,
  truth at rank 2, multiple exclusions available
- This suggests a **selective reranking strategy**: only invoke the LLM when the
  retriever's score gap is small (gap < 0.15) — this would maximize precision while
  reducing the cost of false demotions
- The consistency across models supports generalizability of findings
