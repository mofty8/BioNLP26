# Qualitative Examples

## PMID_10560675_P3

Truth IDs: `OMIM:620813`

### Prompt
```text
You are a rare disease expert reranking a short list of candidate diagnoses for a single patient.
The candidates were retrieved by a phenotype-similarity model. Your job is to rerank them using clinical reasoning.
Choose only from the candidate list provided below.

## Core principle
The retrieval model is well-calibrated. Its rank-1 candidate is correct more than half the time.
Your task: protect rank-1 from demotion by weak reasoning, but promote a challenger when rank-1 is clearly missing key phenotype coverage.

## The two valid reasons to change rank-1
A. EXCLUSION: A feature that is OBLIGATORY (present in >90% of cases) for rank-1 is explicitly absent in this patient.
   'Hallmark', 'typical', or 'common' features are NOT sufficient — only truly obligatory features qualify.
   CRITICAL: Do NOT infer obligatory features from the disease name. Phenotype words in a disease name
   (e.g. 'arachnodactyly' in 'Contractural arachnodactyly', 'cutis laxa' in 'Cutis laxa type ID',
   'hip dysplasia' in 'Osteosclerosis with hip dysplasia') are NOT evidence that feature is obligatory.
   Disease names reflect historical descriptions, not penetrance. Use only independent medical knowledge of penetrance.
B. COVERAGE GAP: Rank-1 fails to explain at least one key positive phenotype or organ system present in this patient,
   AND a challenger explains that gap, AND the challenger covers at least as many of the other phenotypes as rank-1.
   This is about what rank-1 is MISSING — not about which disease has the most impressive name or broadest description.
   The challenger must explain phenotypes rank-1 genuinely cannot account for — not merely explain them differently.
   The challenger must be a candidate from the list below — do not reason about diagnoses outside the list.
If neither A nor B is clearly met, keep rank-1 at position 1.

## Additional rules
- Negative phenotypes exclude a disease ONLY when the absent feature is truly obligatory (>90% penetrance).
  Variable-penetrance features (even if present in 50-80% of cases) are not grounds for exclusion.
- Multi-system coherence wins over single-organ specificity. A disease explaining cardiac + limb findings together beats one explaining only the limb findings more precisely.
- For related disease families, numbered subtypes, and broad-vs-narrow syndrome names: treat them as distinct diseases. Require explicit discriminating findings to switch between them.
- Do not switch based on disease-name wording, lexical overlap with one phenotype, or apparent subtype specificity.
- Copy the exact candidate ID and exact candidate name from the list. Do not invent IDs or names.

## Required output
First write a brief clinical reasoning note (2-3 sentences) stating:
  (1) whether rank-1 is excluded by an OBLIGATORY absent feature (not name-inferred),
  (2) whether rank-1 fails to explain any key positive phenotype or organ system that a challenger covers (Coverage Gap B),
  (3) your final ranking decision.
Then output the JSON block. Do not add any other text.

{
  "selected_candidate": {"id": "...", "name": "..."},
  "ranking": [
    {"rank": 1, "id": "...", "name": "..."},
    {"rank": 2, "id": "...", "name": "..."}
  ]
}
Return exactly 3 ranking items ordered from best to worst.

Positive phenotypes:
- Chronic sinusitis (HP:0011109)
- Chronic bronchitis (HP:0004469)
- Chronic rhinitis (HP:0002257)
- Nasal polyposis (HP:0100582)
Negative phenotypes (explicitly absent):
- Severe viral infection (HP:0031691)

Candidate diseases:
1. id=OMIM:620813 | name=MHC class I deficiency 2 | retrieval_score=0.919789 | retrieval_rank=1 | phenodp_total_similarity=0.919789
2. id=OMIM:608647 | name=Ciliary dyskinesia, primary, 5 | retrieval_score=0.822468 | retrieval_rank=2 | phenodp_total_similarity=0.822468
3. id=OMIM:617092 | name=Ciliary dyskinesia, primary, 35 | retrieval_score=0.814905 | retrieval_rank=3 | phenodp_total_similarity=0.814905
```

### Raw Output
```text
The patient presents with chronic sinusitis, rhinitis, bronchitis, and nasal polyposis, all pointing towards a chronic airway disease. MHC class I deficiency 2 does not typically present with chronic airway disease, and its primary features are recurrent infections, particularly viral infections, which are explicitly absent in this patient. Ciliary dyskinesia, primary, 5 and 35 both explain the chronic airway issues well, and given the slight edge in retrieval score, Ciliary dyskinesia, primary, 5 is preferred.

```json
{
  "selected_candidate": {"id": "OMIM:608647", "name": "Ciliary dyskinesia, primary, 5"},
  "ranking": [
    {"rank": 1, "id": "OMIM:608647", "name": "Ciliary dyskinesia, primary, 5"},
    {"rank": 2, "id": "OMIM:617092", "name": "Ciliary dyskinesia, primary, 35"},
    {"rank": 3, "id": "OMIM:620813", "name": "MHC class I deficiency 2"}
  ]
}
```
```

### Parsed Output
```json
{
  "selected_candidate": {
    "id": "OMIM:608647",
    "name": "Ciliary dyskinesia, primary, 5"
  },
  "ranking": [
    {
      "rank": 1,
      "id": "OMIM:608647",
      "name": "Ciliary dyskinesia, primary, 5",
      "source": "model"
    },
    {
      "rank": 2,
      "id": "OMIM:617092",
      "name": "Ciliary dyskinesia, primary, 35",
      "source": "model"
    },
    {
      "rank": 3,
      "id": "OMIM:620813",
      "name": "MHC class I deficiency 2",
      "source": "model"
    }
  ],
  "parse_mode": "json_object"
}
```

## PMID_10580070_FamilyAindividualIII-13

Truth IDs: `OMIM:115200`

### Prompt
```text
You are a rare disease expert reranking a short list of candidate diagnoses for a single patient.
The candidates were retrieved by a phenotype-similarity model. Your job is to rerank them using clinical reasoning.
Choose only from the candidate list provided below.

## Core principle
The retrieval model is well-calibrated. Its rank-1 candidate is correct more than half the time.
Your task: protect rank-1 from demotion by weak reasoning, but promote a challenger when rank-1 is clearly missing key phenotype coverage.

## The two valid reasons to change rank-1
A. EXCLUSION: A feature that is OBLIGATORY (present in >90% of cases) for rank-1 is explicitly absent in this patient.
   'Hallmark', 'typical', or 'common' features are NOT sufficient — only truly obligatory features qualify.
   CRITICAL: Do NOT infer obligatory features from the disease name. Phenotype words in a disease name
   (e.g. 'arachnodactyly' in 'Contractural arachnodactyly', 'cutis laxa' in 'Cutis laxa type ID',
   'hip dysplasia' in 'Osteosclerosis with hip dysplasia') are NOT evidence that feature is obligatory.
   Disease names reflect historical descriptions, not penetrance. Use only independent medical knowledge of penetrance.
B. COVERAGE GAP: Rank-1 fails to explain at least one key positive phenotype or organ system present in this patient,
   AND a challenger explains that gap, AND the challenger covers at least as many of the other phenotypes as rank-1.
   This is about what rank-1 is MISSING — not about which disease has the most impressive name or broadest description.
   The challenger must explain phenotypes rank-1 genuinely cannot account for — not merely explain them differently.
   The challenger must be a candidate from the list below — do not reason about diagnoses outside the list.
If neither A nor B is clearly met, keep rank-1 at position 1.

## Additional rules
- Negative phenotypes exclude a disease ONLY when the absent feature is truly obligatory (>90% penetrance).
  Variable-penetrance features (even if present in 50-80% of cases) are not grounds for exclusion.
- Multi-system coherence wins over single-organ specificity. A disease explaining cardiac + limb findings together beats one explaining only the limb findings more precisely.
- For related disease families, numbered subtypes, and broad-vs-narrow syndrome names: treat them as distinct diseases. Require explicit discriminating findings to switch between them.
- Do not switch based on disease-name wording, lexical overlap with one phenotype, or apparent subtype specificity.
- Copy the exact candidate ID and exact candidate name from the list. Do not invent IDs or names.

## Required output
First write a brief clinical reasoning note (2-3 sentences) stating:
  (1) whether rank-1 is excluded by an OBLIGATORY absent feature (not name-inferred),
  (2) whether rank-1 fails to explain any key positive phenotype or organ system that a challenger covers (Coverage Gap B),
  (3) your final ranking decision.
Then output the JSON block. Do not add any other text.

{
  "selected_candidate": {"id": "...", "name": "..."},
  "ranking": [
    {"rank": 1, "id": "...", "name": "..."},
    {"rank": 2, "id": "...", "name": "..."}
  ]
}
Return exactly 3 ranking items ordered from best to worst.

Sex: Male
Positive phenotypes:
- Atrial fibrillation (HP:0005110)
- First degree atrioventricular block (HP:0011705)
- Sinus bradycardia (HP:0001688)
Negative phenotypes (explicitly absent):
- Congestive heart failure (HP:0001635)
- Dilated cardiomyopathy (HP:0001644)
- Second degree atrioventricular block (HP:0011706)
- Third degree atrioventricular block (HP:0001709)
- Sudden cardiac death (HP:0001645)
- Thromboembolic stroke (HP:0001727)
- Elevated circulating creatine kinase concentration (HP:0003236)
- Progeroid facial appearance (HP:0005328)
- Lipodystrophy (HP:0009125)
- Joint contracture (HP:0034392)
- Muscle weakness (HP:0001324)
- Skeletal muscle atrophy (HP:0003202)

Candidate diseases:
1. id=OMIM:115200 | name=Cardiomyopathy, dilated, 1A | retrieval_score=0.892445 | retrieval_rank=1 | phenodp_total_similarity=0.892445
2. id=OMIM:163800 | name=Sick sinus syndrome 2 | retrieval_score=0.840393 | retrieval_rank=2 | phenodp_total_similarity=0.840393
3. id=OMIM:600858 | name=Cardiomyopathy, familial hypertrophic, 6 | retrieval_score=0.808502 | retrieval_rank=3 | phenodp_total_similarity=0.808502
```

### Raw Output
```text
The patient presents with a constellation of bradyarrhythmias (sinus bradycardia, first-degree AV block, atrial fibrillation) without evidence of heart failure or cardiomyopathy. Rank-1, dilated cardiomyopathy, is unlikely given the *absence* of dilated cardiomyopathy and congestive heart failure, which are highly prevalent features (>90%) of the condition. Rank-2, Sick sinus syndrome 2, directly addresses the bradyarrhythmias and atrial fibrillation, and does not require the presence of cardiomyopathy. Therefore, I am promoting Rank-2 to position 1.

```json
{
  "selected_candidate": {"id": "OMIM:163800", "name": "Sick sinus syndrome 2"},
  "ranking": [
    {"rank": 1, "id": "OMIM:163800", "name": "Sick sinus syndrome 2"},
    {"rank": 2, "id": "OMIM:115200", "name": "Cardiomyopathy, dilated, 1A"},
    {"rank": 3, "id": "OMIM:600858", "name": "Cardiomyopathy, familial hypertrophic, 6"}
  ]
}
```
```

### Parsed Output
```json
{
  "selected_candidate": {
    "id": "OMIM:163800",
    "name": "Sick sinus syndrome 2"
  },
  "ranking": [
    {
      "rank": 1,
      "id": "OMIM:163800",
      "name": "Sick sinus syndrome 2",
      "source": "model"
    },
    {
      "rank": 2,
      "id": "OMIM:115200",
      "name": "Cardiomyopathy, dilated, 1A",
      "source": "model"
    },
    {
      "rank": 3,
      "id": "OMIM:600858",
      "name": "Cardiomyopathy, familial hypertrophic, 6",
      "source": "model"
    }
  ],
  "parse_mode": "json_object"
}
```

## PMID_10580070_FamilyEindividualII-8

Truth IDs: `OMIM:115200`

### Prompt
```text
You are a rare disease expert reranking a short list of candidate diagnoses for a single patient.
The candidates were retrieved by a phenotype-similarity model. Your job is to rerank them using clinical reasoning.
Choose only from the candidate list provided below.

## Core principle
The retrieval model is well-calibrated. Its rank-1 candidate is correct more than half the time.
Your task: protect rank-1 from demotion by weak reasoning, but promote a challenger when rank-1 is clearly missing key phenotype coverage.

## The two valid reasons to change rank-1
A. EXCLUSION: A feature that is OBLIGATORY (present in >90% of cases) for rank-1 is explicitly absent in this patient.
   'Hallmark', 'typical', or 'common' features are NOT sufficient — only truly obligatory features qualify.
   CRITICAL: Do NOT infer obligatory features from the disease name. Phenotype words in a disease name
   (e.g. 'arachnodactyly' in 'Contractural arachnodactyly', 'cutis laxa' in 'Cutis laxa type ID',
   'hip dysplasia' in 'Osteosclerosis with hip dysplasia') are NOT evidence that feature is obligatory.
   Disease names reflect historical descriptions, not penetrance. Use only independent medical knowledge of penetrance.
B. COVERAGE GAP: Rank-1 fails to explain at least one key positive phenotype or organ system present in this patient,
   AND a challenger explains that gap, AND the challenger covers at least as many of the other phenotypes as rank-1.
   This is about what rank-1 is MISSING — not about which disease has the most impressive name or broadest description.
   The challenger must explain phenotypes rank-1 genuinely cannot account for — not merely explain them differently.
   The challenger must be a candidate from the list below — do not reason about diagnoses outside the list.
If neither A nor B is clearly met, keep rank-1 at position 1.

## Additional rules
- Negative phenotypes exclude a disease ONLY when the absent feature is truly obligatory (>90% penetrance).
  Variable-penetrance features (even if present in 50-80% of cases) are not grounds for exclusion.
- Multi-system coherence wins over single-organ specificity. A disease explaining cardiac + limb findings together beats one explaining only the limb findings more precisely.
- For related disease families, numbered subtypes, and broad-vs-narrow syndrome names: treat them as distinct diseases. Require explicit discriminating findings to switch between them.
- Do not switch based on disease-name wording, lexical overlap with one phenotype, or apparent subtype specificity.
- Copy the exact candidate ID and exact candidate name from the list. Do not invent IDs or names.

## Required output
First write a brief clinical reasoning note (2-3 sentences) stating:
  (1) whether rank-1 is excluded by an OBLIGATORY absent feature (not name-inferred),
  (2) whether rank-1 fails to explain any key positive phenotype or organ system that a challenger covers (Coverage Gap B),
  (3) your final ranking decision.
Then output the JSON block. Do not add any other text.

{
  "selected_candidate": {"id": "...", "name": "..."},
  "ranking": [
    {"rank": 1, "id": "...", "name": "..."},
    {"rank": 2, "id": "...", "name": "..."}
  ]
}
Return exactly 3 ranking items ordered from best to worst.

Sex: Male
Positive phenotypes:
- Atrial fibrillation (HP:0005110)
- Congestive heart failure (HP:0001635)
- Dilated cardiomyopathy (HP:0001644)
- Second degree atrioventricular block (HP:0011706)
- Sudden cardiac death (HP:0001645)
Negative phenotypes (explicitly absent):
- First degree atrioventricular block (HP:0011705)
- Third degree atrioventricular block (HP:0001709)
- Sinus bradycardia (HP:0001688)
- Thromboembolic stroke (HP:0001727)
- Elevated circulating creatine kinase concentration (HP:0003236)
- Progeroid facial appearance (HP:0005328)
- Lipodystrophy (HP:0009125)
- Joint contracture (HP:0034392)
- Muscle weakness (HP:0001324)
- Skeletal muscle atrophy (HP:0003202)

Candidate diseases:
1. id=OMIM:115200 | name=Cardiomyopathy, dilated, 1A | retrieval_score=0.934933 | retrieval_rank=1 | phenodp_total_similarity=0.934933
2. id=OMIM:616117 | name=Cardiac conduction disease with or without dilated cardiomyopathy | retrieval_score=0.788512 | retrieval_rank=2 | phenodp_total_similarity=0.788512
3. id=OMIM:601494 | name=Cardiomyopathy, dilated, 1D | retrieval_score=0.786619 | retrieval_rank=3 | phenodp_total_similarity=0.786619
```

### Raw Output
```text
The patient presents with a constellation of cardiac conduction abnormalities and dilated cardiomyopathy. Rank-1, dilated cardiomyopathy 1A, does not fully explain the conduction defects (second-degree AV block, sudden cardiac death) as prominently as the other candidates. Candidate 2, Cardiac conduction disease with or without dilated cardiomyopathy, directly addresses both the cardiomyopathy and the conduction abnormalities, offering a more comprehensive explanation of the patient's phenotype. Therefore, I am promoting candidate 2 to rank 1.

```json
{
  "selected_candidate": {"id": "OMIM:616117", "name": "Cardiac conduction disease with or without dilated cardiomyopathy"},
  "ranking": [
    {"rank": 1, "id": "OMIM:616117", "name": "Cardiac conduction disease with or without dilated cardiomyopathy"},
    {"rank": 2, "id": "OMIM:115200", "name": "Cardiomyopathy, dilated, 1A"},
    {"rank": 3, "id": "OMIM:601494", "name": "Cardiomyopathy, dilated, 1D"}
  ]
}
```
```

### Parsed Output
```json
{
  "selected_candidate": {
    "id": "OMIM:616117",
    "name": "Cardiac conduction disease with or without dilated cardiomyopathy"
  },
  "ranking": [
    {
      "rank": 1,
      "id": "OMIM:616117",
      "name": "Cardiac conduction disease with or without dilated cardiomyopathy",
      "source": "model"
    },
    {
      "rank": 2,
      "id": "OMIM:115200",
      "name": "Cardiomyopathy, dilated, 1A",
      "source": "model"
    },
    {
      "rank": 3,
      "id": "OMIM:601494",
      "name": "Cardiomyopathy, dilated, 1D",
      "source": "model"
    }
  ],
  "parse_mode": "json_object"
}
```

## PMID_10797416_BellehPatientCF1347

Truth IDs: `OMIM:121050`

### Prompt
```text
You are a rare disease expert reranking a short list of candidate diagnoses for a single patient.
The candidates were retrieved by a phenotype-similarity model. Your job is to rerank them using clinical reasoning.
Choose only from the candidate list provided below.

## Core principle
The retrieval model is well-calibrated. Its rank-1 candidate is correct more than half the time.
Your task: protect rank-1 from demotion by weak reasoning, but promote a challenger when rank-1 is clearly missing key phenotype coverage.

## The two valid reasons to change rank-1
A. EXCLUSION: A feature that is OBLIGATORY (present in >90% of cases) for rank-1 is explicitly absent in this patient.
   'Hallmark', 'typical', or 'common' features are NOT sufficient — only truly obligatory features qualify.
   CRITICAL: Do NOT infer obligatory features from the disease name. Phenotype words in a disease name
   (e.g. 'arachnodactyly' in 'Contractural arachnodactyly', 'cutis laxa' in 'Cutis laxa type ID',
   'hip dysplasia' in 'Osteosclerosis with hip dysplasia') are NOT evidence that feature is obligatory.
   Disease names reflect historical descriptions, not penetrance. Use only independent medical knowledge of penetrance.
B. COVERAGE GAP: Rank-1 fails to explain at least one key positive phenotype or organ system present in this patient,
   AND a challenger explains that gap, AND the challenger covers at least as many of the other phenotypes as rank-1.
   This is about what rank-1 is MISSING — not about which disease has the most impressive name or broadest description.
   The challenger must explain phenotypes rank-1 genuinely cannot account for — not merely explain them differently.
   The challenger must be a candidate from the list below — do not reason about diagnoses outside the list.
If neither A nor B is clearly met, keep rank-1 at position 1.

## Additional rules
- Negative phenotypes exclude a disease ONLY when the absent feature is truly obligatory (>90% penetrance).
  Variable-penetrance features (even if present in 50-80% of cases) are not grounds for exclusion.
- Multi-system coherence wins over single-organ specificity. A disease explaining cardiac + limb findings together beats one explaining only the limb findings more precisely.
- For related disease families, numbered subtypes, and broad-vs-narrow syndrome names: treat them as distinct diseases. Require explicit discriminating findings to switch between them.
- Do not switch based on disease-name wording, lexical overlap with one phenotype, or apparent subtype specificity.
- Copy the exact candidate ID and exact candidate name from the list. Do not invent IDs or names.

## Required output
First write a brief clinical reasoning note (2-3 sentences) stating:
  (1) whether rank-1 is excluded by an OBLIGATORY absent feature (not name-inferred),
  (2) whether rank-1 fails to explain any key positive phenotype or organ system that a challenger covers (Coverage Gap B),
  (3) your final ranking decision.
Then output the JSON block. Do not add any other text.

{
  "selected_candidate": {"id": "...", "name": "..."},
  "ranking": [
    {"rank": 1, "id": "...", "name": "..."},
    {"rank": 2, "id": "...", "name": "..."}
  ]
}
Return exactly 3 ranking items ordered from best to worst.

Sex: Female
Positive phenotypes:
- Crumpled ear (HP:0009901)
- Camptodactyly of finger (HP:0100490)
- Hip contracture (HP:0003273)
- Elbow contracture (HP:0034391)
- Knee contracture (HP:0034671)
- Scoliosis (HP:0002650)
- High palate (HP:0000218)
- Micrognathia (HP:0000347)
Negative phenotypes (explicitly absent):
- Arachnodactyly (HP:0001166)
- Camptodactyly of toe (HP:0001836)
- Wrist flexion contracture (HP:0001239)
- Pectus carinatum (HP:0000768)
- Pectus excavatum (HP:0000767)
- Patellar subluxation (HP:0010499)
- Elbow dislocation (HP:0003042)
- Aortic root aneurysm (HP:0002616)
- Mitral valve prolapse (HP:0001634)

Candidate diseases:
1. id=OMIM:121050 | name=Contractural arachnodactyly, congenital | retrieval_score=0.867601 | retrieval_rank=1 | phenodp_total_similarity=0.867601
2. id=OMIM:619110 | name=Arthrogryposis, distal, type 1C | retrieval_score=0.777388 | retrieval_rank=2 | phenodp_total_similarity=0.777388
3. id=OMIM:620727 | name=Ullrich congenital muscular dystrophy 1B | retrieval_score=0.773532 | retrieval_rank=3 | phenodp_total_similarity=0.773532
```

### Raw Output
```text
The patient lacks arachnodactyly, which is part of the name of the top-ranked candidate, but is not an obligatory feature of Contractural arachnodactyly, congenital. The top-ranked candidate explains most of the observed contractures and skeletal features. Arthrogryposis, distal, type 1C also explains the contractures, but doesn't address the high palate and micrognathia as well as the top candidate. Therefore, I will maintain the original ranking.

```json
{
  "selected_candidate": {"id": "OMIM:121050", "name": "Contractural arachnodactyly, congenital"},
  "ranking": [
    {"rank": 1, "id": "OMIM:121050", "name": "Contractural arachnodactyly, congenital"},
    {"rank": 2, "id": "OMIM:619110", "name": "Arthrogryposis, distal, type 1C"},
    {"rank": 3, "id": "OMIM:620727", "name": "Ullrich congenital muscular dystrophy 1B"}
  ]
}
```
```

### Parsed Output
```json
{
  "selected_candidate": {
    "id": "OMIM:121050",
    "name": "Contractural arachnodactyly, congenital"
  },
  "ranking": [
    {
      "rank": 1,
      "id": "OMIM:121050",
      "name": "Contractural arachnodactyly, congenital",
      "source": "model"
    },
    {
      "rank": 2,
      "id": "OMIM:619110",
      "name": "Arthrogryposis, distal, type 1C",
      "source": "model"
    },
    {
      "rank": 3,
      "id": "OMIM:620727",
      "name": "Ullrich congenital muscular dystrophy 1B",
      "source": "model"
    }
  ],
  "parse_mode": "json_object"
}
```

## PMID_10842287_HOS-B1

Truth IDs: `OMIM:142900`

### Prompt
```text
You are a rare disease expert reranking a short list of candidate diagnoses for a single patient.
The candidates were retrieved by a phenotype-similarity model. Your job is to rerank them using clinical reasoning.
Choose only from the candidate list provided below.

## Core principle
The retrieval model is well-calibrated. Its rank-1 candidate is correct more than half the time.
Your task: protect rank-1 from demotion by weak reasoning, but promote a challenger when rank-1 is clearly missing key phenotype coverage.

## The two valid reasons to change rank-1
A. EXCLUSION: A feature that is OBLIGATORY (present in >90% of cases) for rank-1 is explicitly absent in this patient.
   'Hallmark', 'typical', or 'common' features are NOT sufficient — only truly obligatory features qualify.
   CRITICAL: Do NOT infer obligatory features from the disease name. Phenotype words in a disease name
   (e.g. 'arachnodactyly' in 'Contractural arachnodactyly', 'cutis laxa' in 'Cutis laxa type ID',
   'hip dysplasia' in 'Osteosclerosis with hip dysplasia') are NOT evidence that feature is obligatory.
   Disease names reflect historical descriptions, not penetrance. Use only independent medical knowledge of penetrance.
B. COVERAGE GAP: Rank-1 fails to explain at least one key positive phenotype or organ system present in this patient,
   AND a challenger explains that gap, AND the challenger covers at least as many of the other phenotypes as rank-1.
   This is about what rank-1 is MISSING — not about which disease has the most impressive name or broadest description.
   The challenger must explain phenotypes rank-1 genuinely cannot account for — not merely explain them differently.
   The challenger must be a candidate from the list below — do not reason about diagnoses outside the list.
If neither A nor B is clearly met, keep rank-1 at position 1.

## Additional rules
- Negative phenotypes exclude a disease ONLY when the absent feature is truly obligatory (>90% penetrance).
  Variable-penetrance features (even if present in 50-80% of cases) are not grounds for exclusion.
- Multi-system coherence wins over single-organ specificity. A disease explaining cardiac + limb findings together beats one explaining only the limb findings more precisely.
- For related disease families, numbered subtypes, and broad-vs-narrow syndrome names: treat them as distinct diseases. Require explicit discriminating findings to switch between them.
- Do not switch based on disease-name wording, lexical overlap with one phenotype, or apparent subtype specificity.
- Copy the exact candidate ID and exact candidate name from the list. Do not invent IDs or names.

## Required output
First write a brief clinical reasoning note (2-3 sentences) stating:
  (1) whether rank-1 is excluded by an OBLIGATORY absent feature (not name-inferred),
  (2) whether rank-1 fails to explain any key positive phenotype or organ system that a challenger covers (Coverage Gap B),
  (3) your final ranking decision.
Then output the JSON block. Do not add any other text.

{
  "selected_candidate": {"id": "...", "name": "..."},
  "ranking": [
    {"rank": 1, "id": "...", "name": "..."},
    {"rank": 2, "id": "...", "name": "..."}
  ]
}
Return exactly 3 ranking items ordered from best to worst.

Positive phenotypes:
- Atrial septal defect (HP:0001631)
- Short thumb (HP:0009778)
- 3-4 finger syndactyly (HP:0006097)
- Aplasia of the 3rd finger (HP:0009460)
Negative phenotypes (explicitly absent):
- Muscular ventricular septal defect (HP:0011623)
- Perimembranous ventricular septal defect (HP:0011682)
- Complete atrioventricular canal defect (HP:0001674)
- Patent foramen ovale (HP:0001655)
- Absent thumb (HP:0009777)
- Triphalangeal thumb (HP:0001199)
- Upper limb phocomelia (HP:0009813)
- Amelia involving the upper limbs (HP:0009812)
- Common atrium (HP:0011565)
- Unroofed coronary sinus (HP:0031297)

Candidate diseases:
1. id=OMIM:142900 | name=Holt-Oram syndrome | retrieval_score=0.687621 | retrieval_rank=1 | phenodp_total_similarity=0.687621
2. id=OMIM:609432 | name=Syndactyly, mesoaxial synostotic, with phalangeal reduction | retrieval_score=0.641784 | retrieval_rank=2 | phenodp_total_similarity=0.641784
3. id=OMIM:613681 | name=Chromosome 2q31.1 duplication syndrome | retrieval_score=0.638702 | retrieval_rank=3 | phenodp_total_similarity=0.638702
```

### Raw Output
```text
Holt-Oram syndrome (rank-1) explains the atrial septal defect and limb abnormalities (syndactyly, aplasia of the 3rd finger, short thumb). The negative phenotypes, specifically the absence of complete atrioventricular canal defect, do not exclude Holt-Oram syndrome as this is not an obligatory feature. Syndactyly, mesoaxial synostotic, with phalangeal reduction (rank-2) focuses solely on the hand findings and does not address the atrial septal defect. Therefore, there is no compelling reason to demote Holt-Oram syndrome.

```json
{
  "selected_candidate": {"id": "OMIM:142900", "name": "Holt-Oram syndrome"},
  "ranking": [
    {"rank": 1, "id": "OMIM:142900", "name": "Holt-Oram syndrome"},
    {"rank": 2, "id": "OMIM:609432", "name": "Syndactyly, mesoaxial synostotic, with phalangeal reduction"},
    {"rank": 3, "id": "OMIM:613681", "name": "Chromosome 2q31.1 duplication syndrome"}
  ]
}
```
```

### Parsed Output
```json
{
  "selected_candidate": {
    "id": "OMIM:142900",
    "name": "Holt-Oram syndrome"
  },
  "ranking": [
    {
      "rank": 1,
      "id": "OMIM:142900",
      "name": "Holt-Oram syndrome",
      "source": "model"
    },
    {
      "rank": 2,
      "id": "OMIM:609432",
      "name": "Syndactyly, mesoaxial synostotic, with phalangeal reduction",
      "source": "model"
    },
    {
      "rank": 3,
      "id": "OMIM:613681",
      "name": "Chromosome 2q31.1 duplication syndrome",
      "source": "model"
    }
  ],
  "parse_mode": "json_object"
}
```

