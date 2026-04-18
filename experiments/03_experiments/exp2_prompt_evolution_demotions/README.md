# Experiment 2: Prompt Evolution on Demotion Subset

## Setup
- **Task**: Rerank top-3 candidates for cases where the retriever's rank-1 is correct but might be demoted
- **Subset**: 509 cases where the correct diagnosis is at retriever rank-1 and a plausible challenger exists at rank-2 or rank-3
- **Model**: Gemma 3 27B-IT
- **Prompts tested**: v2, v3, v4, v5, v6

## Goal
Measure how well each prompt protects the correct rank-1 candidate from being incorrectly demoted by the LLM.

## Results (ID-correct, 509 cases, top-3 rerank)

| Prompt | H@1 | H@3 | H@5 | H@10 |
|--------|----:|----:|----:|-----:|
| v2 | 47.35% | 100% | 100% | 100% |
| v3 | **92.53%** | 100% | 100% | 100% |
| v4 | 72.89% | 100% | 100% | 100% |
| v5 | 45.78% | 100% | 100% | 100% |
| v6 | 14.54% | 100% | 100% | 100% |

Note: H@3/5/10 = 100% because the correct answer is always in the top-3 by construction.

## Analysis

### v3 is the Sweet Spot
v3 achieves 92.53% by adding a score-gap heuristic: if rank-1 has a large score lead, require strong evidence to demote. This simple rule prevents most false demotions while allowing the LLM some freedom.

### The Over-Constraint Paradox
Each subsequent prompt (v4 -> v5 -> v6) adds more safeguards, yet performance degrades:
- **v4** (72.89%): Strict 3-check verification gate introduces false negatives -- the model fails some valid checks
- **v5** (45.78%): 4th check (age-dependent) and absolute protection at gap>0.15 creates confusion
- **v6** (14.54%): Same-gene spectrum rule + demotion self-check causes the model to refuse almost all actions

### Why This Happens
The LLM's chain-of-thought reasoning is vulnerable to "analysis paralysis." When given many conditions to check, the model tends to find reasons NOT to act. The demotion self-check in v6 especially backfires: explicitly asking "should I really do this?" causes the model to second-guess correct decisions.

## Run Directories
- `runs/phenodp_gemma3_prompt_v2_demotions_rerank/`
- `runs/phenodp_gemma3_prompt_v3_demotions_rerank/`
- `runs/phenodp_gemma3_prompt_v4_demotions_rerank/`
- `runs/phenodp_gemma3_prompt_v5_demotions_rerank/`
- `runs/phenodp_gemma3_prompt_v6_demotions_rerank/`
