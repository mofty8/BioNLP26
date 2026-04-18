# Experiment 3: Full-Scale Reranking (v3 and v6)

## Setup
- **Task**: Rerank all cases in the benchmark (not just curated subsets)
- **Models**: Gemma 3 27B-IT
- **Cutoffs**: top-3, top-5, top-10
- Two full runs: v3 on 3,451 cases (first half), v6 on all 6,901 cases

## Results (ID-correct)

### v3 Full Rerank (3,451 cases)

| Cutoff | H@1 | H@3 | H@5 | H@10 | MRR |
|--------|----:|----:|----:|-----:|----:|
| top-3 | 57.66% | 72.91% | 72.91% | 72.91% | 0.645 |
| top-5 | 57.66% | 72.91% | 77.28% | 77.28% | 0.655 |
| top-10 | 57.93% | 72.91% | 77.28% | 81.08% | 0.661 |

### v6 Full Rerank (6,901 cases)

| Cutoff | H@1 | H@3 | H@5 | H@10 | MRR |
|--------|----:|----:|----:|-----:|----:|
| top-3 | 51.18% | 63.27% | 63.27% | 63.27% | 0.565 |
| top-5 | 51.18% | 63.27% | 67.19% | 67.19% | 0.574 |
| top-10 | 51.12% | 63.27% | 67.19% | 71.90% | 0.580 |

### Baseline Retriever (6,901 cases)

| Metric | Value |
|--------|------:|
| Hit@1 | 51.24% |
| Hit@3 | 63.27% |
| Hit@5 | 67.19% |
| Hit@10 | 71.92% |

## Analysis

### v3 Shows Modest Improvement (on its subset)
v3 achieves H@1 = 57.66% on 3,451 cases, roughly +6.4% over the baseline. However, this run only covers half the benchmark (the other half crashed), so the comparison is not fully fair.

### v6 Matches Baseline -- Does Nothing
v6 on the full 6,901 cases achieves H@1 = 51.18%, essentially identical to the baseline 51.24%. The constrained prompt prevents both false demotions AND valid promotions. The net effect is zero.

The Hit@3/5/10 metrics are also identical to the baseline, confirming that v6 almost never reorders candidates.

### The "Do No Harm" Ceiling
v6 represents the convergence of prompt engineering: when you optimize purely to prevent errors, you converge to the identity function (pass-through). This is a fundamental limitation -- the reranker needs to take risks to improve, but every risk creates potential for harm.

### Cutoff Effect
Reranking top-3 vs top-10 has minimal effect on H@1 (the LLM's top pick stays the same). The benefit of larger cutoffs only appears at higher K (more candidates to potentially promote). This suggests the LLM is primarily making rank-1 vs rank-2 decisions, not deeply reasoning about the full list.

## Run Directories
- `runs/phenodp_gemma3_prompt_v3_full_rerank/`
- `runs/phenodp_gemma3_v6_full_rerank/`
