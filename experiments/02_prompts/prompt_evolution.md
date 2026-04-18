# Prompt Evolution: v2 through v6 + HPO Annotation Variant

## Overview

Six prompt iterations were developed, each addressing specific failure modes discovered through error analysis of the previous version. The evolution shows an inherent tension: prompts that prevent false demotions (good for cases where retriever rank-1 is correct) also prevent valid promotions (bad for cases where rank-1 is wrong).

## Prompt Timeline

### v2 -- Minimal Protection
- **Key idea**: Protect retrieval rank-1; only two demotion reasons allowed: exclusion of an obligatory feature, or superior phenotype coverage.
- **Result on 509 demotion cases**: H@1 = 47.35%
- **Failure mode discovered**: The LLM aggressively demotes rank-1 based on vague "broader syndrome" reasoning.

### v3 -- Score Gap Rule
- **Key idea**: Adds a retrieval score-gap rule. If rank-1 has a large score lead, require stronger evidence to demote. Stricter definition of "obligatory absent features."
- **Result on 509 demotion cases**: H@1 = 92.53% (best on this subset)
- **Result on 3,451 full rerank**: H@1 = 57.66% (+6.42% over baseline)
- **Failure modes**: Still demotes rank-1 when the disease name contains the absent feature (name-inference fallacy). E.g., claims "optic atrophy is obligatory" for a disease named "Dystonia with optic atrophy."
- **Source**: Default fallback in `prompting.py:536`

### v4 -- Hard Score-Gap Gate + Strict Conditions
- **Key idea**: Makes score-gap thresholds explicit (gap > 0.05 = LARGE). Adds strict 3-check verification gate for Condition A (exclusion). Adds Condition B (biological impossibility). Numbered-subtype rule.
- **Result on 509 demotion cases**: H@1 = 72.89%
- **Regression from v3**: The stricter conditions block some valid demotions that v3 correctly handled.
- **Source**: `prompting.py:30`

### v5 -- Coverage-First + Age-Dependent Caveat
- **Key idea**: Adds 4th verification check (not age-dependent). Absolute protection for gap > 0.15. Stronger name-inference rule with explicit examples.
- **Result on 509 demotion cases**: H@1 = 45.78%
- **Severe regression**: The model now interprets the strict rules as "never demote" for most cases.
- **Source**: `prompting.py:181`

### v6 -- Same-Gene Spectrum Rule + Demotion Self-Check
- **Key idea**: Adds same-gene spectrum rule (if rank-1 and challenger share same causal gene, keep rank-1). Tightens gap threshold (small gap <= 0.03). Adds explicit demotion self-check requiring model to verify all conditions before acting.
- **Result on 509 demotion cases**: H@1 = 14.54% (worst)
- **Result on 6,901 full rerank**: H@1 = 51.18% (essentially equals baseline 51.24%)
- **Interpretation**: The accumulation of constraints makes the model refuse almost all demotions. It achieves "do no harm" by doing nothing.
- **Source**: `prompting.py:348`

### HPO Annotation Variant
- **Key idea**: Instead of relying on LLM's parametric knowledge of disease phenotypes, provide explicit HPO-frequency annotations from `phenotype.hpoa`. The LLM can now check actual annotation frequencies rather than guessing penetrance.
- **Result on 6,901 full rerank**: H@1 = 40.81% (10% below baseline)
- **Interpretation**: The added context overwhelms the model. More information paradoxically leads to worse decisions, possibly because the model now has too many features to weigh and makes more confused demotions.
- **Source**: HPO annotation branch in `prompting.py:536`, uses `hpo_annotations.py`

## Prompt Delta Summary

| Version | Key Addition | Demotion H@1 (509) | Full H@1 | Direction |
|---------|-------------|--------------------:|----------:|-----------|
| Baseline (retriever) | -- | -- | 51.24% | -- |
| v2 | Basic protection | 47.35% | -- | -- |
| v3 | Score-gap rule | **92.53%** | **57.66%** (3451) | Best |
| v4 | Hard gate + 3 checks | 72.89% | -- | Decline |
| v5 | 4th check + gap>0.15 | 45.78% | -- | Decline |
| v6 | Same-gene + self-check | 14.54% | 51.18% (6901) | Baseline-level |
| HPO ann. | Annotation frequencies | -- | 40.81% (6901) | Below baseline |

## Key Insight for Paper

The prompt evolution reveals a fundamental limitation of LLM reranking: **there is no single prompt that simultaneously prevents false demotions and enables valid promotions**. The sweet spot (v3) works because it gives the LLM enough freedom to act while providing a simple heuristic (score gap) to avoid the worst mistakes. More elaborate prompts create an "analysis paralysis" effect where the model's chain-of-thought reasoning talks itself out of every action.

This suggests that prompt-based reranking has a ceiling determined by the LLM's ability to distinguish between diseases using phenotype descriptions -- a task that may fundamentally require structured ontological reasoning rather than natural language inference.

## Rendered Prompt Examples

See `rendered_examples/` for actual prompts sent to the LLM with patient data, as extracted from qualitative_examples.md files in each run directory.
