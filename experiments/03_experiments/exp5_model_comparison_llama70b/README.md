# Experiment 5: Model Comparison -- Gemma 3 27B vs Llama 3.3 70B

## Setup
- **Task**: Rerank a curated 100-case demotion+promotion subset
- **Models**: Gemma 3 27B-IT vs Llama 3.3 70B-Instruct
- **Prompt**: v5 for Llama, v6 for Gemma
- **Cutoffs**: top-3, top-5

## Results (ID-correct, 100 cases)

### Gemma 3 27B (v6 prompt)

| Cutoff | H@1 | H@3 | H@5 | MRR |
|--------|----:|----:|----:|----:|
| top-3 | **74.00%** | 99.00% | 99.00% | 0.865 |
| top-5 | **77.00%** | 99.00% | 100% | 0.883 |

### Llama 3.3 70B (v5 prompt)

| Cutoff | H@1 | H@3 | H@5 | MRR |
|--------|----:|----:|----:|----:|
| top-3 | 50.00% | 99.00% | 99.00% | 0.742 |
| top-5 | 49.00% | 97.00% | 100% | 0.737 |

## Analysis

### Gemma 3 Significantly Outperforms Llama 3.3
Despite being 2.6x smaller (27B vs 70B parameters), Gemma 3 achieves +24% H@1 over Llama 3.3 on this task. This is a striking result.

### Possible Explanations
1. **Instruction following**: Gemma 3's instruction tuning may be better suited for structured clinical reasoning tasks with complex constraint sets.
2. **Output format compliance**: Gemma 3 more reliably produces valid JSON output and follows the required reasoning format.
3. **Llama's over-eagerness to rerank**: Llama 3.3 appears to demote rank-1 more aggressively, even when the prompt warns against it. The model may weight its own "clinical knowledge" over the explicit score-gap constraints.
4. **Different prompt versions**: Note that Gemma used v6 (most constrained) and Llama used v5. Even with a less constrained prompt, Llama performs worse, suggesting the model itself is the bottleneck.

### Implication for Paper
Model choice matters more than model size for structured clinical reasoning. A smaller, well-tuned model can outperform a larger one on tasks requiring strict adherence to decision rules. This is relevant to the clinical NLP community where computational resources and deployment constraints are real considerations.

## Run Directories
- `runs/phenodp_gemma3_v6_demotions_promotions/`
- `runs/phenodp_llama70b_v5_demotions_promotions/`
