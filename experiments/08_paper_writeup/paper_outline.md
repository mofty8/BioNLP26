# BioNLP Workshop Paper Outline (4 pages)

## Title (options)
- "Can LLMs Rerank Rare Disease Candidates? Lessons from 6,901 Phenopackets"
- "LLM Reranking for Rare Disease Diagnosis: When More Reasoning Means Worse Results"
- "Beyond Phenotype Similarity: Evaluating LLM and Learned Reranking for Rare Disease Candidate Prioritization"

## Abstract (~150 words)
Rare disease diagnosis from clinical phenotypes is typically framed as a retrieval problem: given a patient's HPO terms, rank candidate diseases by phenotype similarity. We investigate whether LLM-based reranking can improve upon PhenoDP, a well-calibrated phenotype similarity retriever, using Gemma 3 27B as a clinical reranker on 6,901 phenopacket cases. Through six prompt iterations and systematic error analysis, we find that (1) LLM reranking shows no net improvement at full scale despite strong performance on curated subsets, (2) increasingly constrained prompts paradoxically degrade performance through "analysis paralysis," (3) a simple MLP trained on decomposed retriever signals achieves the best in-distribution improvement (+6.8% Hit@1, p=0.004), but (4) neither learned reranking nor encoder fine-tuning generalizes to external benchmarks. Our results suggest that for phenotype-based rare disease diagnosis, improving the retriever's scoring function yields more reliable gains than post-hoc LLM reasoning.

---

## 1. Introduction (~0.5 page)

### Paragraph 1: Rare disease diagnosis challenge
- 7,000+ rare diseases, diagnostic odyssey averaging 4-7 years
- Phenotype-driven approaches: match patient HPO terms against disease profiles
- Tools: PhenoDP, Exomiser, LIRICAL, Phen2Gene
- Framing as candidate ranking problem

### Paragraph 2: The LLM reranking hypothesis
- LLMs encode clinical knowledge from training corpora
- Recent work on LLM-based clinical reasoning (cite relevant BioNLP papers)
- Hypothesis: LLMs can use clinical reasoning to rerank candidates beyond similarity scores
- Our question: Does this work at scale for rare diseases?

### Paragraph 3: Contributions
1. Systematic evaluation of LLM reranking (Gemma 3 27B, Llama 3.3 70B) on 6,901 cases
2. Six prompt iterations with error analysis showing the "analysis paralysis" phenomenon
3. Comparison against learned alternatives (MLP fusion, contrastive encoder fine-tuning)
4. Honest evaluation on external benchmarks showing generalization failures

---

## 2. Methods (~1 page)

### 2.1 Task and Data
- Phenopacket benchmark: 6,901 cases, 500 OMIM diseases, min 3 HPO terms
- Data source: published case reports converted to phenopackets (cite GA4GH)
- External benchmarks: HMS (88), MME (40), LIRICAL (370), RAMEDIS (624)
- Evaluation: Hit@1/3/5/10, MRR under ID-correct criterion

### 2.2 Retriever: PhenoDP
- IC-weighted phenotype matching + PCL_HPOEncoder embedding similarity
- Top-50 candidates per patient
- Baseline: H@1 = 51.24%

### 2.3 LLM Reranker
- Gemma 3 27B-IT via vLLM (temperature=0, greedy decoding)
- Prompt structure: system role, core principle, score-gap gate, conditions A/B, output format
- Six prompt versions (v2-v6 + HPO annotation variant)
- Brief description of prompt evolution and key rules (detailed in appendix)

### 2.4 Learned Alternatives
- **Z-score PR rescoring**: Z-score normalize PhenoDP's internal signals, asymmetric precision-recall weighting
- **MLP signal fusion**: Decompose PhenoDP scores into 8+ features, train MLP with pairwise ranking loss
- **Contrastive encoder fine-tuning**: Subtype-aware triplet loss on PCL_HPOEncoder

### 2.5 Evaluation Protocol
- Primary: nested 5-fold CV, PMID-grouped (prevent same-publication leakage)
- External: train on primary benchmark, evaluate on RareBench (zero-shot)
- Statistical testing: paired t-test across folds

---

## 3. Results (~1.5 pages)

### 3.1 LLM Reranking: Curated Subsets vs Full Scale
- Table: prompt versions on 509-case demotion subset (v3 best at 92.5%)
- Table: full-scale reranking (v6 on 6,901 = baseline)
- Key finding: prompts that prevent false demotions also prevent valid promotions
- Figure (optional): prompt constraint level vs H@1 on demotion subset (inverted U-shape for v3 being sweet spot)

### 3.2 The Prompt Over-Constraint Paradox
- Each v4/v5/v6 addition addresses a real failure mode but degrades overall performance
- v6's demotion self-check creates "analysis paralysis" in chain-of-thought
- HPO annotations hurt (-10.4%) despite providing ground-truth disease-phenotype frequencies
- Interpretation: the task requires discrimination, not more information

### 3.3 Model Comparison
- Gemma 3 27B outperforms Llama 3.3 70B (74% vs 50% on 100-case subset)
- Smaller model better at structured constraint following
- Implication: architecture/tuning > parameter count for clinical reasoning

### 3.4 Learned Alternatives
- Z-score PR rescoring: +6.4% (significant, simple)
- MLP fusion: +6.8% (best, significant)
- Both outperform best LLM prompt at full scale
- MLP beats LLM without any natural language reasoning

### 3.5 Generalization to External Benchmarks
- Table: RareBench results
- MLP: -2.93% combined (overfitting)
- Fine-tuned encoder: 0% delta
- Z-score PR: mixed results
- Only PhenoDP baseline is consistently robust

---

## 4. Discussion (~0.5 page)

### Why LLM reranking fails at scale
- The retriever is already well-calibrated (>50% H@1)
- LLM must distinguish between phenotypically similar diseases -- a task requiring structured ontological reasoning, not natural language inference
- Chain-of-thought reasoning introduces errors: the more the model reasons, the more opportunities to make mistakes
- Parallel to "overthinking" in human clinical reasoning

### The generalization problem
- Methods that "learn from data" overfit to disease distribution
- External benchmarks have dramatically different disease compositions (HMS: 92% unseen)
- This is a fundamental challenge for rare disease AI: the training distribution cannot cover the long tail

### Recommendations
1. Invest in retriever improvements (scoring functions, feature engineering) over post-hoc reranking
2. Use LLMs only for targeted, well-defined tasks (e.g., interpreting gene findings)
3. Always evaluate on external benchmarks; in-distribution gains are misleading
4. Simple methods (z-score normalization) are more robust than complex ones

### Limitations
- Single retriever (PhenoDP); results may differ with other retrievers
- Two LLMs tested; larger/newer models may perform differently
- Phenopacket benchmark derived from published cases (selection bias)
- 4-page format limits depth of analysis

---

## 5. Conclusion (~0.25 page)

We conducted a systematic evaluation of LLM-based candidate reranking for rare disease diagnosis. Despite strong performance on curated subsets, LLM reranking provides no net improvement at scale, and increasingly constrained prompts paradoxically degrade performance. A simple MLP trained on decomposed retriever signals achieves the best in-distribution improvement but fails to generalize. Our findings suggest that for phenotype-based rare disease diagnosis, improving the underlying retrieval scoring is more promising than adding LLM reasoning on top.

---

## References (key citations to include)
- PhenoDP (original paper)
- GA4GH Phenopackets
- RareBench (HMS, MME, LIRICAL, RAMEDIS)
- HPO (Human Phenotype Ontology)
- Gemma 3 (Google)
- vLLM
- Related LLM clinical reasoning papers (GPT-4 for diagnosis, etc.)
- Exomiser, LIRICAL, Phen2Gene (comparison systems)

---

## Appendix / Supplementary (if allowed)
- Full prompt text for v3 and v6
- Per-fold CV results
- Qualitative examples of LLM reasoning (correct and incorrect)
- Extended RareBench results per dataset
