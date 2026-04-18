# Failure Analysis

## Overview
Systematic analysis of where and why the LLM reranker fails, based on error categorization across prompt versions and case subsets.

## Failure Categories

### 1. False Demotions (LLM incorrectly moves correct rank-1 down)

**Frequency**: The dominant failure mode in all prompt versions.

**Subtypes**:

#### 1a. Name-Inference Fallacy
The LLM infers that a phenotype is "obligatory" for a disease because the phenotype appears in the disease name. E.g., claims "optic atrophy must be present" for "Dystonia with optic atrophy and basal ganglia abnormalities" because it's in the name.
- **Addressed in**: v4 (check #3), v5 (expanded examples), v6 (stricter rule)
- **Outcome**: Rules help but the LLM still occasionally commits this error

#### 1b. Broader Syndrome Preference
The LLM promotes a broader syndrome that "explains more systems" even though the narrower rank-1 disease better matches the specific phenotype profile.
- **Addressed in**: v4 (Condition B -- biological impossibility only), v6 (invalid demotion examples)
- **Outcome**: Partially fixed; the LLM still finds creative ways to justify promotions

#### 1c. Numbered Subtype Confusion
The LLM switches between numbered subtypes of the same disease family (e.g., DEE 4 vs DEE 14) based on phenotype reasoning alone, which is unreliable.
- **Addressed in**: v4 (numbered-subtype rule), v5/v6 (strengthened)
- **Outcome**: Well-addressed by the rule; the LLM follows it

#### 1d. Hallucinated Penetrance
The LLM claims a feature has ">90% penetrance" without evidence. It confidently states frequencies that it cannot actually know.
- **Addressed in**: v4 (require >90% not just "hallmark"), HPO annotation variant (provide real data)
- **Outcome**: HPO annotations make this worse, not better (see Exp 4)

### 2. Missed Promotions (LLM fails to promote correct candidate from rank-2+)

**Frequency**: Increases as prompts become more constrained (v5, v6).

**Subtypes**:

#### 2a. Over-Cautious Score-Gap Interpretation
The LLM treats moderate score gaps (0.05-0.10) as prohibitive, refusing to promote even when clear clinical evidence supports it.
- **Root cause**: Prompts emphasize "large gap = strong evidence for rank-1" so aggressively that the model becomes paralyzed

#### 2b. Analysis Paralysis from Self-Check
v6's demotion self-check creates a pattern where the model reasons through all conditions correctly, then second-guesses itself in the final step.
- **Example output pattern**: "Condition A: met. Condition B: met. Self-check: both conditions appear met, but the gap is large, so I should be cautious. Decision: keep rank-1."

### 3. Structural Failures

#### 3a. JSON Parse Errors
The LLM occasionally produces malformed JSON (missing commas, extra text). Frequency: ~1-2% of outputs.

#### 3b. ID Hallucination
The LLM invents disease IDs or names not in the candidate list. Addressed by explicit instruction "copy exact ID and name."

## Quantitative Breakdown

### Demotion Subset (509 cases where rank-1 is correct)

| Prompt | Correct Keep (%) | False Demotion (%) |
|--------|----------:|------------:|
| v2 | 47.35% | 52.65% |
| v3 | 92.53% | 7.47% |
| v4 | 72.89% | 27.11% |
| v5 | 45.78% | 54.22% |
| v6 | 14.54% | 85.46% |

Wait -- v6 has 85.46% false demotions? Actually, v6's 14.54% H@1 means it KEEPS rank-1 only 14.54% of the time. This is misleading: v6 demotes rank-1 in 85.46% of cases, which sounds terrible. But on the FULL benchmark, v6 achieves baseline H@1 = 51.18%. This apparent contradiction is explained by the fact that the demotion subset is specifically curated cases where the LLM SHOULD NOT demote. On the full set, v6 also fails to promote in cases where it SHOULD promote, and these two effects cancel out to near-baseline.

### Failing IDs Analysis

From error analysis files:
- `failing_ids_all.txt`: Total failing cases across methods
- `failing_ids_demotions.txt`: Cases where false demotion occurred
- `failing_ids_missed_promo.txt`: Cases where valid promotion was missed

The demotion failures outnumber missed promotions by approximately 6:1, confirming that **preventing harm (false demotions) is the dominant challenge**.

## Key Insight for Paper

The fundamental tension is: **the same cases that test demotion prevention and promotion ability require opposite behaviors from the LLM**. No single prompt can optimize both. This is not a prompt engineering problem -- it's a limitation of using natural language reasoning for a task that requires structured ontological comparison.

The most promising direction is to bypass natural language reasoning entirely (MLP fusion) or to develop hybrid approaches that use the LLM only for specific, well-defined reasoning tasks where it has a genuine advantage (e.g., interpreting gene-disease associations).

## Source Files
- `failing_ids_all.txt`, `failing_ids_demotions.txt`, `failing_ids_missed_promo.txt`
- `analyze_phenopackets.py`
- `analyze_prediction_fuzzy_scores.py`
- Run-specific `qualitative_examples.md` files in each experiment directory
