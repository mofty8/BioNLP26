# Non-Retrievable Case Analysis
**BioNLP @ ACL 2026 — Error Analysis**
*Generated: 2026-04-13*

Non-retrievable cases are those where the ground-truth disease does not appear anywhere in
PhenoDP's top-50 candidate set. This is a hard ceiling for the retrieval paradigm — the
reranker cannot rescue these cases. This analysis asks: *who are these cases, why does
retrieval fail, and what does this tell us about when the LLM approach might have an
inherent advantage?*

---

## 1. Non-Retrievable Rates

| Dataset | Total | Non-retrievable | Rate |
|---------|-------|-----------------|------|
| **PhenoPacket** | 6,901 | 1,278 | **18.5%** |
| RareBench (all) | 1,122 | 380 | 33.9% |
| — RAMEDIS | 624 | 270 | **43.3%** |
| — HMS | 88 | 55 | **62.5%** |
| — LIRICAL | 370 | 53 | 14.3% |
| — MME | 40 | 2 | 5.0% |

**The sub-dataset reversal pattern maps directly onto non-retrievability:**
- RAMEDIS and HMS (where LLM wins) have the highest non-retrievable rates (43–63%)
- LIRICAL and MME (where retriever wins) have very low non-retrievable rates (5–14%)
- This is structural, not accidental: when the truth is absent from retrieved candidates,
  retrieval-based approaches are fundamentally limited and open-vocabulary LLMs have a
  natural advantage

---

## 2. Feature Comparison: Retrievable vs Non-Retrievable (PhenoPacket)

| Feature | Retrievable (n=5,623) | Non-retrievable (n=1,278) |
|---------|-----------------------|--------------------------|
| Mean positive HPO terms | 9.56 | **8.58** |
| Median positive HPO terms | 8 | **7** |
| Mean negative HPO terms | 12.85 | 12.73 |
| Mean HPOA annotations (disease) | **59.5** | **46.7** |
| Median HPOA annotations | **52** | **24** |
| Mean retriever top-1 score | 0.814 | 0.757 |

**Key pattern:** Non-retrievable cases are associated with poorly-annotated diseases
(median 24 HPOA phenotype entries vs 52 for retrievable). When the disease database
has few HPO annotations, the semantic similarity search cannot find a strong match.
Patients also present with slightly fewer HPO terms on average.

### 2.1 Non-Retrievable Rate by HPO Count (PhenoPacket)

| Patient HPO count | Cases | Non-retrievable | Rate |
|-------------------|-------|-----------------|------|
| 3–5 | 1,294 | 274 | 21.2% |
| 5–8 | 1,877 | 413 | 22.0% |
| 8–12 | 1,848 | 318 | 17.2% |
| 12–20 | 1,464 | 218 | 14.9% |
| 20+ | 418 | 55 | 13.2% |

More phenotype information reliably reduces non-retrievability. Cases with 20+ HPO terms
are 40% less likely to be missed than cases with 3–5 terms.

### 2.2 Non-Retrievable Rate by HPOA Annotation Density

| Disease HPOA annotations | Cases | Non-retrievable | Rate |
|--------------------------|-------|-----------------|------|
| 1–5 | 13 | 3 | 23.1% |
| 5–10 | 167 | 24 | 14.4% |
| 10–20 | 952 | 355 | **37.3%** |
| 20–40 | 1,790 | 409 | 22.8% |
| 40–200 | 3,852 | 447 | 11.6% |

The 10–20 annotation bin shows the highest non-retrievable rate (37.3%). This is the
"danger zone": diseases with enough annotation to appear in the benchmark, but not enough
phenotypic characterization to reliably match patient HPO profiles. Diseases with 40+
annotations are retrieved at 88.4% — well-annotated diseases are rarely missed.

---

## 3. Disease-Level Non-Retrievability (PhenoPacket)

### 3.1 Diseases Always Missed (100% non-retrievable, ≥3 cases)

| Disease | Cases | HPOA annotations |
|---------|-------|-----------------|
| Adrenal hyperplasia, congenital (21-hydroxylase deficiency) | 50 | 12 |
| Microcephaly 6, primary, autosomal recessive | 3 | 10 |
| Intellectual developmental disorder, autosomal dominant | 3 | 33 |

The most striking case is **congenital adrenal hyperplasia (21-hydroxylase deficiency)**:
50 patients in the benchmark, but the retriever misses all 50. With only 12 HPOA
annotations, the disease's phenotype profile is too sparse to match patient HPO sets via
semantic similarity.

### 3.2 Top 20 Diseases by Non-Retrievable Rate (≥3 cases)

| Disease | n | Non-ret | Rate | HPOA |
|---------|---|---------|------|------|
| Adrenal hyperplasia, congenital (21-hydroxylase) | 50 | 50 | 100.0% | 12 |
| Microcephaly 6, primary, AR | 3 | 3 | 100.0% | 10 |
| Intellectual developmental disorder, AD | 3 | 3 | 100.0% | 33 |
| Developmental delay, dysmorphic facies, brain abnormalities | 48 | 45 | 93.8% | 22 |
| Xia-Gibbs syndrome | 65 | 56 | 86.2% | 187 |
| Developmental and epileptic encephalopathy 11 | 260 | 214 | 82.3% | 11 |
| Glass syndrome | 147 | 120 | 81.6% | 55 |
| Myasthenic syndrome, congenital, 8 | 5 | 4 | 80.0% | 9 |
| Houge-Janssen syndrome 2 | 56 | 41 | 73.2% | 36 |
| Immunodeficiency, common variable, 13 | 72 | 49 | 68.1% | 10 |
| Short stature, optic nerve atrophy, Pelger-Huet anomaly | 51 | 34 | 66.7% | 34 |
| Developmental and epileptic encephalopathy 9 | 3 | 2 | 66.7% | 19 |
| Neurodevelopmental disorder with coarse facies | 66 | 40 | 60.6% | 230 |
| Glycine encephalopathy 2 | 5 | 3 | 60.0% | 7 |
| Coffin-Siris syndrome 8 | 57 | 33 | 57.9% | 27 |
| Seizures, benign familial infantile, 3 | 20 | 11 | 55.0% | 7 |
| DiGeorge syndrome | 22 | 12 | 54.5% | 75 |
| Developmental and epileptic encephalopathy 4 | 430 | 208 | 48.4% | 24 |
| Developmental and epileptic encephalopathy 5 | 21 | 10 | 47.6% | 19 |
| Epilepsy, early-onset, 3 | 27 | 12 | 44.4% | 20 |

**Notable outlier — Xia-Gibbs syndrome:** 86% non-retrievable despite 187 HPOA annotations.
This suggests a phenotype overlap problem: the disease's HPO profile closely resembles many
other neurodevelopmental disorders, and the correct disease is consistently outcompeted by
similar diseases in the top-50.

**"Developmental and epileptic encephalopathy" cluster:** DEE-4 (430 cases, 48%), DEE-11
(260 cases, 82%), and DEE-9 are all consistently missed. These are ultra-rare sub-types
of epileptic encephalopathy, distinguished primarily by gene (KCNQ2, SCN1A, etc.), yet the
HPO phenotypes are nearly identical across sub-types. The retriever cannot disambiguate
based on HPO alone — this is a fundamental limitation for genetically-heterogeneous
phenotypically-homogeneous disease groups.

---

## 4. Category-Level Analysis (PhenoPacket)

| Disease Category | Cases | Non-retrievable | Rate | Median HPOA |
|-----------------|-------|-----------------|------|-------------|
| Immunodeficiency | 162 | 68 | **42.0%** | 17 |
| Epilepsy / Neurological | 1,193 | 480 | **40.2%** | 24 |
| Renal / Nephrotic | 161 | 50 | 31.1% | 16 |
| Skeletal dysplasia | 167 | 43 | 25.8% | 84 |
| Other / Syndromic | 3,375 | 560 | 16.6% | 54 |
| Liver / Hepatic | 10 | 1 | 10.0% | 39 |
| Intellectual disability | 562 | 56 | 10.0% | 76 |
| Cardiomyopathy / Arrhythmia | 82 | 3 | 3.7% | 11 |
| Mitochondrial | 209 | 4 | **1.9%** | 113 |
| Vision / Retinal | 121 | 2 | 1.7% | 43 |
| Marfan / Connective tissue | 311 | 5 | 1.6% | 59 |
| Muscular dystrophy / Myopathy | 151 | 2 | 1.3% | 41 |
| Rasopathy / RAS pathway | 316 | 4 | 1.3% | 56 |
| Hearing loss | 5 | 0 | 0.0% | 14 |
| Endocrine / Hormonal | 74 | 0 | 0.0% | 30 |

**High-risk categories for retrieval:**
- **Immunodeficiency (42%):** Highly heterogeneous — many sub-types share overlapping
  phenotypes (infections, immune dysregulation) and many are poorly annotated (median 17 HPOA)
- **Epilepsy/Neurological (40%):** The genetically-heterogeneous epileptic encephalopathies
  dominate (DEE cluster) — HPO-based retrieval cannot distinguish sub-types

**Well-retrieved categories:**
- **Mitochondrial (1.9%):** Rich phenotypic profiles (median 113 HPOA), multi-system
  involvement creates distinctive phenotype combinations
- **RASopathies (1.3%):** Distinctive facial and cardiac phenotypes, well-annotated
- **Marfan/Connective tissue (1.6%):** Highly specific HPO terms (aortic dilation, ectopia lentis)

---

## 5. What the Retriever Returns Instead (Non-Retrievable Cases)

When the truth disease is not in the top-50, what does the retriever surface?

| Top-1 Category (wrong) | Count | % of non-ret cases |
|------------------------|-------|---------------------|
| Other / Syndromic | 469 | 36.7% |
| **Intellectual disability** | 401 | **31.4%** |
| Epilepsy / Neurological | 251 | 19.6% |
| Immunodeficiency | 50 | 3.9% |
| Endocrine / Hormonal | 36 | 2.8% |
| Mitochondrial | 24 | 1.9% |

**Most common wrong top-1 diseases:**

| Disease | Count | Category |
|---------|-------|----------|
| Mental retardation, autosomal dominant 50 | 37× | Intellectual disability |
| Pituitary adenoma 3, multiple types, somatic | 36× | Endocrine |
| Developmental delay, impaired speech and behavior | 29× | Other |
| Epileptic encephalopathy, early infantile, 13 | 29× | Epilepsy |
| Intellectual developmental disorder, AD | 19× | Intellectual disability |
| Developmental and epileptic encephalopathy 4 | 18× | Epilepsy |
| Developmental and epileptic encephalopathy 17 | 18× | Epilepsy |
| ReNU syndrome | 17× | Other |
| Zttk syndrome | 17× | Other |
| Coffin-Siris syndrome 11 | 16× | Other |

**Interpretation:** When retrieval fails, the top-1 is overwhelmingly generic "intellectual
disability" or "epileptic encephalopathy" phenocopies. The retriever defaults to the
nearest well-annotated disease with overlapping HPO terms — these are phenotypically similar
"attractors" that absorb poorly-characterized or phenotypically-indistinct diseases.

---

## 6. Score Profile Analysis

| | Non-retrievable | Retrievable |
|-|-----------------|-------------|
| Mean rank-1 score | 0.757 | 0.814 |
| Median rank-1 score | 0.753 | 0.814 |
| Mean rank-50 score | 0.652 | 0.627 |

The rank-50 boundary score for non-retrievable cases averages 0.652. This means the truth
disease must have a phenotypic similarity score **below 0.652** to be excluded from the
top-50 — i.e., less than 65% similarity to the patient's phenotype. For retrievable cases,
the first-ranked candidate already scores 0.814.

The rank-50 score is *higher* for non-retrievable cases (0.652) than for retrievable cases
(0.627), confirming that non-retrievable cases involve more competitive, harder-to-rank
disease spaces — the top-50 is densely populated with similar diseases, squeezing out the
true diagnosis.

---

## 7. RareBench Sub-Dataset Non-Retrievability

| Sub-dataset | Non-retrievable | Rate | Mean HPOA (non-ret) | Mean HPOA (ret) |
|-------------|-----------------|------|---------------------|-----------------|
| RAMEDIS | 270/624 | **43.3%** | 23.9 | 36.2 |
| HMS | 55/88 | **62.5%** | 8.0 | 23.0 |
| LIRICAL | 53/370 | 14.3% | 29.8 | 47.9 |
| MME | 2/40 | **5.0%** | 49.0 | 45.6 |

The HPOA annotation density pattern holds across all sub-datasets:
non-retrievable diseases are consistently less annotated than retrievable ones.

**HMS is the most extreme case:** 62.5% of cases are non-retrievable, and non-retrievable
diseases have a mean of only 8.0 HPOA annotations — essentially empty disease profiles.
This explains why HMS is the hardest dataset for retrieval and why LLM approaches
(which rely on clinical knowledge rather than HPOA annotations) have an inherent advantage.

---

## 8. Implications for the Paper

### 8.1 Explaining the Sub-Dataset Reversal

The LLM advantage on RAMEDIS/HMS is not random — it correlates precisely with
non-retrievability rates. When the truth disease is absent from the candidate set,
no amount of reranking can help. The LLM can still succeed because it has clinical
knowledge independent of the HPOA annotation database.

| Sub-dataset | Non-ret rate | LLM advantage (exact) |
|-------------|-------------|----------------------|
| HMS | 62.5% | Yes (2.9% vs 7.4% but directional) |
| RAMEDIS | 43.3% | **Yes (+24.2pp)** |
| LIRICAL | 14.3% | No (retriever +49pp) |
| MME | 5.0% | No (retriever +65pp) |

### 8.2 The 18.5% Hard Ceiling

On PhenoPacket, 18.5% of cases are structurally unreachable by any retrieval-based
approach regardless of reranking quality. An optimal hybrid system that uses LLM-only
for non-retrievable cases and retrieval for retrievable cases has a theoretical upper
bound of:

- Retrievable (81.5%): retriever top-1 accuracy = ~63% of retrievable cases correct
  → ~51.2% overall from retriever
- Non-retrievable (18.5%): if LLM hits 11.5% overall, a large fraction of its
  successes come from non-retrievable cases
- **Oracle upper bound including LLM-only on non-retrievable:** 56.7% (measured)

### 8.3 Disease Families to Highlight

For qualitative analysis in the paper, three disease patterns are worth noting:

1. **Genetically heterogeneous, phenotypically homogeneous epilepsies (DEE cluster):**
   HPO-based retrieval fundamentally cannot distinguish DEE sub-types; gene information
   would be required.

2. **Congenital adrenal hyperplasia (21-hydroxylase):** Completely missed (50 cases,
   100% non-retrievable) due to sparse HPOA annotation (12 terms). A known, treatable
   disease invisible to the retriever.

3. **Xia-Gibbs syndrome:** Missed despite 187 HPOA annotations — a phenotypic overlap
   problem, not an annotation sparsity problem. The syndrome's profile is too similar to
   competing neurodevelopmental disorders.

### 8.4 Recommended Paper Statement

> "Analysis of the 18.5% non-retrievable PhenoPacket cases reveals two structural failure
> modes: annotation sparsity (diseases with <20 HPOA entries, non-retrievable rate 22–37%)
> and phenotypic homogeneity (genetically-distinct sub-types sharing near-identical HPO
> profiles, e.g., DEE subtypes). These failure modes explain the sub-dataset reversal:
> RAMEDIS and HMS, where LLM approaches outperform retrieval, have non-retrievable rates
> of 43% and 63% respectively, driven by sparse disease annotation in HPOA. LIRICAL and
> MME, where retrieval dominates, have non-retrievable rates of 14% and 5%."

---

## Output Files

| File | Description |
|------|-------------|
| `tables/table_nonretrievable_by_disease.csv` | Per-disease non-retrievable rates and HPOA counts |
| `tables/table_nonretrievable_by_category.csv` | Category-level non-retrievable rates |
| `tables/table_nonretrievable_cases_pp.csv` | Full case-level data for 1,278 non-retrievable PhenoPacket cases |
| `data/nonretrievable_summary.json` | Complete numerical results |
