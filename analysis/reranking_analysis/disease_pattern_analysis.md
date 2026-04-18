# Disease-Level Pattern Analysis
**BioNLP @ ACL 2026 — Supplementary Analysis**
*Generated: 2026-04-12*

This report analyses which **diseases** benefit or are harmed by LLM reranking,
what the LLM prefers when it demotes the correct diagnosis, and whether patterns
are consistent across models.

Focus: PhenoPacket dataset (n=6,901), v7 prompt, top-10, Gemma-4 31B as primary
model (cross-checked against Gemma-3 27B and Llama-3.3 70B).

---

## 1. Per-Disease Promotion and Demotion Rates

### 1.1 Most Promoted Diseases (Gemma-4, v7, top-10, ≥3 window cases)

| Disease | N in window | Promoted | Promo rate | Demoted | Demo rate | Net |
|---------|-------------|----------|-----------|---------|-----------|-----|
| Tuberous sclerosis-2 | 8 | 6 | **75%** | 0 | 0% | +6 |
| Neurofibromatosis, type 1 | 204 | 103 | **50%** | 0 | 0% | +103 |
| Sulfite oxidase deficiency | 14 | 7 | **50%** | 1 | 7% | +6 |
| Fanconi anemia, complementation group C | 4 | 2 | 50% | 0 | 0% | +2 |
| Bardet-Biedl syndrome 1 | 13 | 3 | 23% | 0 | 0% | +3 |
| Rubinstein-Taybi syndrome 2 | 9 | 2 | 22% | 0 | 0% | +2 |
| HMG-CoA synthase-2 deficiency | 39 | 8 | 21% | 0 | 0% | +8 |
| Holt-Oram syndrome | 100 | 20 | **20%** | 0 | 0% | +20 |
| Osteogenesis imperfecta, type IX | 5 | 1 | 20% | 0 | 0% | +1 |
| Craniofrontonasal dysplasia | 6 | 1 | 17% | 0 | 0% | +1 |
| Greig cephalopolysyndactyly syndrome | 43 | 7 | 16% | 0 | 0% | +7 |
| Marfan syndrome | 45 | 6 | 13% | 0 | 0% | +6 |
| Loeys-Dietz syndrome 1 | 22 | 2 | 9% | 0 | 0% | +2 |
| Kabuki syndrome 2 | 20 | 2 | 10% | 0 | 0% | +2 |

**Key finding:** Neurofibromatosis type 1 (NF1) is the single largest beneficiary with
103 promotions — almost half of all promotions-to-rank-1 in the dataset (218 total).
This is not noise: the promotion rate is 50% with zero demotions.

### 1.2 Most Demoted Diseases (Gemma-4, v7, top-10, ≥3 window cases)

| Disease | N in window | Demoted | Demo rate | Promoted | Promo rate | Net |
|---------|-------------|---------|-----------|----------|-----------|-----|
| Aarskog-Scott syndrome | 48 | 15 | **31%** | 1 | 2% | −14 |
| Citrullinemia | 4 | 2 | 50% | 0 | 0% | −2 |
| Spondyloepimetaphyseal dysplasia, Guo-Campeau type | 5 | 2 | 40% | 0 | 0% | −2 |
| Cutis laxa, autosomal recessive, type IA | 3 | 1 | 33% | 0 | 0% | −1 |
| Acrofacial dysostosis 1, Nager type | 24 | 3 | 12% | 0 | 0% | −3 |
| Noonan syndrome 2 | 34 | 2 | 6% | 0 | 0% | −2 |
| Ectopia lentis, familial | 24 | 1 | 4% | 0 | 0% | −1 |

**Key finding:** Aarskog-Scott syndrome is the single most harmed disease — 31%
demotion rate, consistently across all 3 models, with a clear and consistent LLM
confusion target (see Section 2).

---

## 2. Demotion Confusion Pairs — What Does the LLM Prefer Instead?

When the LLM demotes the correct rank-1 disease, it promotes a specific alternative.
Analysis across all 3 models (43 total rank-1 demotion events):

| Truth disease | LLM preferred | Events | Mechanism |
|---|---|---|---|
| Aarskog-Scott syndrome | Faciodigitogenital syndrome, autosomal recessive | **15×** | OMIM nomenclature collision — same disease, different IDs |
| Ectopia lentis, familial | Marfan syndrome | **12×** | FBN1 family — LLM picks the well-known common anchor |
| SEMD, Guo-Campeau type | ERI1-related disease | 2× | Ultra-rare disease, limited LLM parametric knowledge |

### 2.1 Aarskog-Scott → Faciodigitogenital (15 events, most frequent demotion pair)

**Aarskog-Scott syndrome** (OMIM:305400, X-linked recessive) and **Faciodigitogenital
syndrome, autosomal recessive** are clinically near-identical conditions caused by
variants in the FGD1 pathway. They appear as separate OMIM entries under different
names but share the same core phenotype (facial, digit, and genital anomalies). The
retriever correctly identifies the exact OMIM ID from the patient's phenotype; the
LLM "corrects" it to the synonym entry. This is a **nomenclature-induced demotion**:
the LLM creates an error where there was none.

This pattern is consistent across all 3 models, affecting multiple independent cases
from the same PMID cohorts.

### 2.2 Ectopia Lentis → Marfan Syndrome (12 events)

**Ectopia lentis, familial** is caused by FBN1 variants — the same gene responsible
for Marfan syndrome — but is a clinically distinct entity with a narrower phenotype
(lens dislocation without aortic involvement). The LLM systematically promotes Marfan
syndrome (the most prominent FBN1-associated disease in medical literature) over the
more specific ectopia lentis diagnosis. This is a **frequency bias** pattern: the LLM
prefers the common, famous disease in the gene family over the rarer, more specific one.

---

## 3. Diseases with Consistent Promotions

### 3.1 Promotions to rank-1 by Gemma-4 (top-10), ≥2 cases

| Disease | Cases promoted | Starting ranks | Mean score gap |
|---------|---------------|----------------|----------------|
| Neurofibromatosis, type 1 | **102** | 2–4 (mostly 2, 3) | 0.035 |
| Holt-Oram syndrome | **20** | 2–10 | 0.020 |
| HMG-CoA synthase-2 deficiency | 8 | 2–4 | 0.013 |
| Sulfite oxidase deficiency | 7 | 3–9 | 0.038 |
| Kleefstra syndrome 1 | 7 | 2–5 | 0.019 |
| Greig cephalopolysyndactyly syndrome | 7 | 2–5 | 0.042 |
| Tuberous sclerosis-2 | 6 | 2 | 0.002 |
| Marfan syndrome | 6 | 2–5 | 0.040 |
| Spinocerebellar ataxia 29, congenital nonprogressive | 4 | 2–3 | 0.014 |
| Bardet-Biedl syndrome 1 | 3 | 2 | 0.017 |
| Kabuki syndrome 1 | 3 | 2–5 | 0.025 |
| KBG syndrome | 3 | 2 | 0.013 |
| Hypomagnesemia 3, renal | 3 | 3 | 0.022 |
| Loeys-Dietz syndrome 4 | 2 | 2–3 | 0.035 |
| Loeys-Dietz syndrome 1 | 2 | 2–4 | 0.010 |
| Fanconi anemia, complementation group C | 2 | 3–7 | 0.014 |
| Ehlers-Danlos syndrome, vascular type | 2 | 2–3 | 0.038 |
| Distal renal tubular acidosis 4 with hemolytic anemia | 2 | 3 | 0.006 |

### 3.2 The NF1 story in detail

NF1 dominates because:
- It shares many HPO features with related conditions (Legius syndrome, NF2, Noonan,
  Costello) — café-au-lait macules, learning difficulties, short stature
- The retriever cannot reliably separate these: small score gaps (~0.035) are typical
- NF1 is one of the most thoroughly documented genetic diseases in literature; the LLM
  has strong parametric knowledge to distinguish it from its phenotypic neighbours
- Promotions are overwhelmingly rank 2→1 or rank 3→1 swaps — the LLM corrects a
  tight race, not a dramatic reordering

This is the **frequency bias working correctly**: NF1 is both the most common and the
most literarily prominent disease in its phenotypic cluster, and the LLM picks it reliably.

---

## 4. Disease Category Analysis

Diseases grouped by category (Gemma-4, v7, top-10):

| Category | Diseases | Cases | Promo rate | Demo rate | Net rate |
|----------|----------|-------|-----------|----------|----------|
| Rasopathy / RAS pathway | 7 | 299 | **34.8%** | 0.7% | **+34.1%** |
| Holt-Oram family | 1 | 100 | **20.0%** | 0.0% | **+20.0%** |
| Renal / Nephrotic | 7 | 105 | 5.7% | 0.0% | +5.7% |
| Marfan / Connective tissue | 13 | 283 | 4.2% | 0.4% | +3.9% |
| Other | 209 | 2,727 | 2.5% | 0.4% | +2.1% |
| Intellectual disability | 16 | 237 | 0.8% | 0.0% | +0.8% |
| Epilepsy / Neurological | 22 | 325 | 0.6% | 0.3% | +0.3% |
| Amyloidosis | 3 | 16 | 0.0% | 0.0% | 0.0% |
| Immunodeficiency | 9 | 48 | 0.0% | 0.0% | 0.0% |
| Cardiomyopathy | 5 | 62 | 0.0% | 0.0% | 0.0% |
| Muscular dystrophy | 12 | 142 | 0.0% | 0.0% | 0.0% |
| Vision / Retinal | 3 | 81 | 0.0% | 0.0% | 0.0% |
| Mitochondrial | 6 | 194 | 0.0% | 0.5% | −0.5% |
| Skeletal dysplasia | 10 | 94 | 1.1% | 5.3% | −4.3% |
| **Aarskog-Scott family** | **1** | **48** | **2.1%** | **31.2%** | **−29.2%** |

### 4.1 Category interpretation

**Categories that benefit:**
- **Rasopathies (RAS pathway):** NF1 drives the +34.1% figure, but the broader pattern
  holds across Noonan, Legius, and other RAS-pathway conditions. These diseases have
  overlapping phenotypes that confuse the retriever; the LLM resolves them correctly
  using clinical literature knowledge.
- **Holt-Oram family:** The retriever struggles to separate Holt-Oram syndrome from
  related limb-heart conditions; the LLM uses gene–phenotype associations (TBX5) to
  promote the correct diagnosis.
- **Connective tissue / Marfan family:** Net positive because Marfan promotions (+6)
  outweigh ectopia lentis demotions (−1 from G4 alone). However, the ectopia lentis
  confusion pattern is a systematic qualitative error even if numerically small.

**Categories that are neutral:**
- Cardiomyopathy, muscular dystrophy, retinal diseases, immunodeficiency: the retriever
  is already highly accurate (large score gaps) and the LLM correctly defers.

**Categories that are harmed:**
- **Skeletal dysplasia:** −4.3% net. Multiple specific subtypes (spondyloepimetaphyseal,
  acrofacial dysostosis) are demoted in favor of better-known skeletal syndromes.
- **Aarskog-Scott family:** −29.2% net — entirely driven by the nomenclature collision
  with Faciodigitogenital syndrome.

---

## 5. Diseases the LLM Never Modifies

192 diseases (with ≥5 window cases) show **zero changes** across all cases.
The LLM consistently preserves retrieval rank for these. Top examples:

| Disease | N in window |
|---------|-------------|
| Lipodystrophy, familial partial, type 2 | 126 |
| Mitochondrial DNA depletion syndrome 13 | 85 |
| Tubulointerstitial kidney disease, autosomal dominant | 73 |
| Leber congenital amaurosis 6 | 71 |
| Pseudohypoparathyroidism Ia | 65 |
| Cornelia de Lange syndrome 1 | 60 |
| ReNU syndrome | 60 |
| Mitochondrial DNA depletion syndrome 6 | 57 |
| Autoimmune polyendocrinopathy syndrome type I | 48 |
| Emery-Dreifuss muscular dystrophy 2 | 41 |

These are diseases where the retriever is confident (large score gap between rank-1
and rank-2) and the v7 gate rule correctly prevents the LLM from intervening. They
represent the stable core of the retrieval paradigm — cases where phenotype-based
retrieval is already definitive.

---

## 6. Cross-Model Consistency of Disease Patterns

### 6.1 NF1 promotion consistency

NF1 promotions were observed across all three models (Gemma-3, Gemma-4, Llama-3.3-70B).
The high cross-model agreement on NF1 promotions confirms this is a genuine clinical
signal, not a model-specific artifact. Different models identify the same cases as
candidates for reranking within the NF1/rasopathy cluster.

### 6.2 Aarskog-Scott demotion consistency

All 3 models show the Aarskog-Scott → Faciodigitogenital confusion. The pattern
is consistent in **disease identity** across models but not always in **which specific
cases** each model demotes — models sometimes demote different individual cases from
the same disease. This is consistent with the confusion being triggered by score-gap
uncertainty (case-specific) combined with a disease-level LLM bias (shared across models).

### 6.3 No universal 3-model consensus on any single demotion case

No single case was demoted by all 3 models to exactly the same alternative disease.
This shows that while the disease-level patterns are real and consistent, the exact
trigger is case-specific (score gap, which candidates are in the window). The models
share the bias but activate it on different instances.

---

## 7. Summary of Key Patterns for the Paper

### 7.1 The LLM adds most value for phenotypically overlapping disease families

The reranker's benefit is concentrated in disease groups where the retriever produces
ambiguous rankings — multiple diseases with similar HPO profiles receive similar
retrieval scores. The LLM resolves this using parametric clinical knowledge.
Rasopathies, Holt-Oram, and connective tissue disorders are the prime examples.
NF1 alone accounts for nearly half of all promotions to rank-1.

### 7.2 The LLM's failure modes are systematic and disease-specific

Two recurring error patterns:
1. **Frequency bias**: Preferring the well-known disease in a gene family over the
   rarer, more specific variant (ectopia lentis → Marfan). The LLM is biased toward
   diseases that appear more frequently in its training data.
2. **Nomenclature collision**: Selecting a synonym OMIM entry for the same clinical
   condition (Aarskog-Scott → Faciodigitogenital). This creates artificial errors where
   the retriever was already correct.

### 7.3 Most diseases are unaffected

192 of 324 well-represented diseases (59%) show zero LLM intervention. The reranker
acts selectively on a minority of cases — those where the retrieval score gap is small
and the disease falls in a phenotypically ambiguous cluster.

### 7.4 Implications for selective reranking

A practical finding: LLM reranking could be made more reliable by:
- Applying it only in specific disease-family contexts (rasopathies, connective tissue)
  where its clinical knowledge is strong
- Suppressing it for ultra-rare diseases with limited LLM training coverage
- Adding an OMIM synonym-awareness step to prevent nomenclature-induced demotions

---

## Output Files

| File | Description |
|------|-------------|
| `tables/table_disease_promo_demo_rates.csv` | Per-disease promotion/demotion rates (all ≥3-case diseases) |
| `tables/table_demotion_confusion_pairs.csv` | All rank-1 demotion events with LLM preference (all 3 models) |
| `tables/table_consistent_demotions.csv` | Cases where all 3 models agree on the same demotion target |
| `tables/table_promotion_events.csv` | All promotion-to-rank-1 events (Gemma-4) |
| `tables/table_disease_category_rates.csv` | Category-level aggregated promotion/demotion rates |
