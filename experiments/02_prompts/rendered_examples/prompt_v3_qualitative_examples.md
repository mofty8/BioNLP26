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
Preserve rank-1 unless you find a specific, named clinical reason to change it.
The cost of incorrectly demoting rank-1 is higher than the cost of missing a promotion.
When in doubt, keep rank-1.

## Retrieval score gap rule
The retrieval_score gap between rank-1 and rank-2 reflects how much more strongly the model supports rank-1.
If the gap is large (rank-1 score minus rank-2 score > 0.05), a single absent feature is not sufficient to demote rank-1.
A large gap requires multiple independent hard exclusions — not one absent finding, no matter how seemingly specific.

## The only two valid reasons to demote retrieval rank-1
A. EXCLUSION: A feature that is OBLIGATORY (present in >90% of cases) for rank-1 is explicitly absent in this patient.
   'Hallmark', 'typical', or 'common' features are NOT sufficient — only truly obligatory features qualify.
   CRITICAL: Do NOT infer obligatory features from the disease name. Phenotype words in a disease name
   (e.g. 'arachnodactyly' in 'Contractural arachnodactyly', 'cutis laxa' in 'Cutis laxa type ID',
   'hip dysplasia' in 'Osteosclerosis with hip dysplasia') are NOT evidence that feature is obligatory.
   Disease names reflect historical descriptions, not penetrance. Use only independent medical knowledge of penetrance.
B. SUPERIOR COVERAGE: A challenger explains ALL of the same organ systems as rank-1, PLUS at least one additional organ system or a highly specific finding rank-1 cannot explain.
   Explaining a single finding more specifically, while rank-1 explains more systems overall, is NOT superior coverage.
   The challenger must be a candidate from the list below — do not reason about diagnoses outside the list.
If neither A nor B is clearly met, keep rank-1 at position 1.

## Additional rules
- Negative phenotypes are hard clinical evidence ONLY when the absent feature is truly obligatory for a disease.
  Variable-penetrance features (even if present in 50-80% of cases) are not grounds for exclusion.
- Multi-system coherence wins over single-organ specificity. A disease explaining cardiac + limb findings together beats one explaining only the limb findings more precisely.
- For related disease families, numbered subtypes, and broad-vs-narrow syndrome names: treat them as distinct diseases. Require explicit discriminating findings to switch between them.
- Do not switch based on disease-name wording, lexical overlap with one phenotype, or apparent subtype specificity.
- Copy the exact candidate ID and exact candidate name from the list. Do not invent IDs or names.

## Required output
First write a brief clinical reasoning note (2-3 sentences) stating:
  (1) whether any candidate is excluded by an OBLIGATORY (>90% penetrance) negative phenotype — and confirm this is NOT inferred from the disease name,
  (2) what the retrieval score gap is between rank-1 and rank-2, and whether it is large (>0.05),
  (3) whether condition A or B above is clearly met to justify changing rank-1.
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
The patient does not have any features obligatorily present in MHC class I deficiency 2 that are absent here. The retrieval score gap between rank-1 and rank-2 is 0.097321, which is large (>0.05). Neither exclusion criterion A nor superior coverage criterion B is met. Therefore, I will preserve the rank-1 candidate.

```json
{
  "selected_candidate": {"id": "OMIM:620813", "name": "MHC class I deficiency 2"},
  "ranking": [
    {"rank": 1, "id": "OMIM:620813", "name": "MHC class I deficiency 2"},
    {"rank": 2, "id": "OMIM:608647", "name": "Ciliary dyskinesia, primary, 5"},
    {"rank": 3, "id": "OMIM:617092", "name": "Ciliary dyskinesia, primary, 35"}
  ]
}
```
```

### Parsed Output
```json
{
  "selected_candidate": {
    "id": "OMIM:620813",
    "name": "MHC class I deficiency 2"
  },
  "ranking": [
    {
      "rank": 1,
      "id": "OMIM:620813",
      "name": "MHC class I deficiency 2",
      "source": "model"
    },
    {
      "rank": 2,
      "id": "OMIM:608647",
      "name": "Ciliary dyskinesia, primary, 5",
      "source": "model"
    },
    {
      "rank": 3,
      "id": "OMIM:617092",
      "name": "Ciliary dyskinesia, primary, 35",
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
Preserve rank-1 unless you find a specific, named clinical reason to change it.
The cost of incorrectly demoting rank-1 is higher than the cost of missing a promotion.
When in doubt, keep rank-1.

## Retrieval score gap rule
The retrieval_score gap between rank-1 and rank-2 reflects how much more strongly the model supports rank-1.
If the gap is large (rank-1 score minus rank-2 score > 0.05), a single absent feature is not sufficient to demote rank-1.
A large gap requires multiple independent hard exclusions — not one absent finding, no matter how seemingly specific.

## The only two valid reasons to demote retrieval rank-1
A. EXCLUSION: A feature that is OBLIGATORY (present in >90% of cases) for rank-1 is explicitly absent in this patient.
   'Hallmark', 'typical', or 'common' features are NOT sufficient — only truly obligatory features qualify.
   CRITICAL: Do NOT infer obligatory features from the disease name. Phenotype words in a disease name
   (e.g. 'arachnodactyly' in 'Contractural arachnodactyly', 'cutis laxa' in 'Cutis laxa type ID',
   'hip dysplasia' in 'Osteosclerosis with hip dysplasia') are NOT evidence that feature is obligatory.
   Disease names reflect historical descriptions, not penetrance. Use only independent medical knowledge of penetrance.
B. SUPERIOR COVERAGE: A challenger explains ALL of the same organ systems as rank-1, PLUS at least one additional organ system or a highly specific finding rank-1 cannot explain.
   Explaining a single finding more specifically, while rank-1 explains more systems overall, is NOT superior coverage.
   The challenger must be a candidate from the list below — do not reason about diagnoses outside the list.
If neither A nor B is clearly met, keep rank-1 at position 1.

## Additional rules
- Negative phenotypes are hard clinical evidence ONLY when the absent feature is truly obligatory for a disease.
  Variable-penetrance features (even if present in 50-80% of cases) are not grounds for exclusion.
- Multi-system coherence wins over single-organ specificity. A disease explaining cardiac + limb findings together beats one explaining only the limb findings more precisely.
- For related disease families, numbered subtypes, and broad-vs-narrow syndrome names: treat them as distinct diseases. Require explicit discriminating findings to switch between them.
- Do not switch based on disease-name wording, lexical overlap with one phenotype, or apparent subtype specificity.
- Copy the exact candidate ID and exact candidate name from the list. Do not invent IDs or names.

## Required output
First write a brief clinical reasoning note (2-3 sentences) stating:
  (1) whether any candidate is excluded by an OBLIGATORY (>90% penetrance) negative phenotype — and confirm this is NOT inferred from the disease name,
  (2) what the retrieval score gap is between rank-1 and rank-2, and whether it is large (>0.05),
  (3) whether condition A or B above is clearly met to justify changing rank-1.
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
The patient presents with a constellation of bradyarrhythmias (sinus bradycardia, first-degree AV block, atrial fibrillation) without evidence of heart failure or cardiomyopathy. No obligatory features for any of the candidates are absent. The retrieval score gap between rank-1 (OMIM:115200) and rank-2 (OMIM:163800) is 0.052, which is large. While the patient does not have dilated cardiomyopathy, this is not an obligatory feature of dilated cardiomyopathy 1A. Therefore, condition A is not met, and there is no superior coverage by another candidate.

```json
{
  "selected_candidate": {"id": "OMIM:115200", "name": "Cardiomyopathy, dilated, 1A"},
  "ranking": [
    {"rank": 1, "id": "OMIM:115200", "name": "Cardiomyopathy, dilated, 1A"},
    {"rank": 2, "id": "OMIM:163800", "name": "Sick sinus syndrome 2"},
    {"rank": 3, "id": "OMIM:600858", "name": "Cardiomyopathy, familial hypertrophic, 6"}
  ]
}
```
```

### Parsed Output
```json
{
  "selected_candidate": {
    "id": "OMIM:115200",
    "name": "Cardiomyopathy, dilated, 1A"
  },
  "ranking": [
    {
      "rank": 1,
      "id": "OMIM:115200",
      "name": "Cardiomyopathy, dilated, 1A",
      "source": "model"
    },
    {
      "rank": 2,
      "id": "OMIM:163800",
      "name": "Sick sinus syndrome 2",
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
Preserve rank-1 unless you find a specific, named clinical reason to change it.
The cost of incorrectly demoting rank-1 is higher than the cost of missing a promotion.
When in doubt, keep rank-1.

## Retrieval score gap rule
The retrieval_score gap between rank-1 and rank-2 reflects how much more strongly the model supports rank-1.
If the gap is large (rank-1 score minus rank-2 score > 0.05), a single absent feature is not sufficient to demote rank-1.
A large gap requires multiple independent hard exclusions — not one absent finding, no matter how seemingly specific.

## The only two valid reasons to demote retrieval rank-1
A. EXCLUSION: A feature that is OBLIGATORY (present in >90% of cases) for rank-1 is explicitly absent in this patient.
   'Hallmark', 'typical', or 'common' features are NOT sufficient — only truly obligatory features qualify.
   CRITICAL: Do NOT infer obligatory features from the disease name. Phenotype words in a disease name
   (e.g. 'arachnodactyly' in 'Contractural arachnodactyly', 'cutis laxa' in 'Cutis laxa type ID',
   'hip dysplasia' in 'Osteosclerosis with hip dysplasia') are NOT evidence that feature is obligatory.
   Disease names reflect historical descriptions, not penetrance. Use only independent medical knowledge of penetrance.
B. SUPERIOR COVERAGE: A challenger explains ALL of the same organ systems as rank-1, PLUS at least one additional organ system or a highly specific finding rank-1 cannot explain.
   Explaining a single finding more specifically, while rank-1 explains more systems overall, is NOT superior coverage.
   The challenger must be a candidate from the list below — do not reason about diagnoses outside the list.
If neither A nor B is clearly met, keep rank-1 at position 1.

## Additional rules
- Negative phenotypes are hard clinical evidence ONLY when the absent feature is truly obligatory for a disease.
  Variable-penetrance features (even if present in 50-80% of cases) are not grounds for exclusion.
- Multi-system coherence wins over single-organ specificity. A disease explaining cardiac + limb findings together beats one explaining only the limb findings more precisely.
- For related disease families, numbered subtypes, and broad-vs-narrow syndrome names: treat them as distinct diseases. Require explicit discriminating findings to switch between them.
- Do not switch based on disease-name wording, lexical overlap with one phenotype, or apparent subtype specificity.
- Copy the exact candidate ID and exact candidate name from the list. Do not invent IDs or names.

## Required output
First write a brief clinical reasoning note (2-3 sentences) stating:
  (1) whether any candidate is excluded by an OBLIGATORY (>90% penetrance) negative phenotype — and confirm this is NOT inferred from the disease name,
  (2) what the retrieval score gap is between rank-1 and rank-2, and whether it is large (>0.05),
  (3) whether condition A or B above is clearly met to justify changing rank-1.
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
The patient presents with a constellation of cardiac findings including atrial fibrillation, congestive heart failure, dilated cardiomyopathy, AV block, and sudden cardiac death. There are no obligatory features for any of the candidates explicitly absent in this patient; the absence of first, second, or third-degree AV block does not exclude any of these diagnoses. The retrieval score gap between rank-1 (0.934933) and rank-2 (0.788512) is 0.146421, which is large (>0.05). Therefore, multiple hard exclusions would be needed to demote rank-1, and these are not present.

```json
{
  "selected_candidate": {"id": "OMIM:115200", "name": "Cardiomyopathy, dilated, 1A"},
  "ranking": [
    {"rank": 1, "id": "OMIM:115200", "name": "Cardiomyopathy, dilated, 1A"},
    {"rank": 2, "id": "OMIM:616117", "name": "Cardiac conduction disease with or without dilated cardiomyopathy"},
    {"rank": 3, "id": "OMIM:601494", "name": "Cardiomyopathy, dilated, 1D"}
  ]
}
```
```

### Parsed Output
```json
{
  "selected_candidate": {
    "id": "OMIM:115200",
    "name": "Cardiomyopathy, dilated, 1A"
  },
  "ranking": [
    {
      "rank": 1,
      "id": "OMIM:115200",
      "name": "Cardiomyopathy, dilated, 1A",
      "source": "model"
    },
    {
      "rank": 2,
      "id": "OMIM:616117",
      "name": "Cardiac conduction disease with or without dilated cardiomyopathy",
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
Preserve rank-1 unless you find a specific, named clinical reason to change it.
The cost of incorrectly demoting rank-1 is higher than the cost of missing a promotion.
When in doubt, keep rank-1.

## Retrieval score gap rule
The retrieval_score gap between rank-1 and rank-2 reflects how much more strongly the model supports rank-1.
If the gap is large (rank-1 score minus rank-2 score > 0.05), a single absent feature is not sufficient to demote rank-1.
A large gap requires multiple independent hard exclusions — not one absent finding, no matter how seemingly specific.

## The only two valid reasons to demote retrieval rank-1
A. EXCLUSION: A feature that is OBLIGATORY (present in >90% of cases) for rank-1 is explicitly absent in this patient.
   'Hallmark', 'typical', or 'common' features are NOT sufficient — only truly obligatory features qualify.
   CRITICAL: Do NOT infer obligatory features from the disease name. Phenotype words in a disease name
   (e.g. 'arachnodactyly' in 'Contractural arachnodactyly', 'cutis laxa' in 'Cutis laxa type ID',
   'hip dysplasia' in 'Osteosclerosis with hip dysplasia') are NOT evidence that feature is obligatory.
   Disease names reflect historical descriptions, not penetrance. Use only independent medical knowledge of penetrance.
B. SUPERIOR COVERAGE: A challenger explains ALL of the same organ systems as rank-1, PLUS at least one additional organ system or a highly specific finding rank-1 cannot explain.
   Explaining a single finding more specifically, while rank-1 explains more systems overall, is NOT superior coverage.
   The challenger must be a candidate from the list below — do not reason about diagnoses outside the list.
If neither A nor B is clearly met, keep rank-1 at position 1.

## Additional rules
- Negative phenotypes are hard clinical evidence ONLY when the absent feature is truly obligatory for a disease.
  Variable-penetrance features (even if present in 50-80% of cases) are not grounds for exclusion.
- Multi-system coherence wins over single-organ specificity. A disease explaining cardiac + limb findings together beats one explaining only the limb findings more precisely.
- For related disease families, numbered subtypes, and broad-vs-narrow syndrome names: treat them as distinct diseases. Require explicit discriminating findings to switch between them.
- Do not switch based on disease-name wording, lexical overlap with one phenotype, or apparent subtype specificity.
- Copy the exact candidate ID and exact candidate name from the list. Do not invent IDs or names.

## Required output
First write a brief clinical reasoning note (2-3 sentences) stating:
  (1) whether any candidate is excluded by an OBLIGATORY (>90% penetrance) negative phenotype — and confirm this is NOT inferred from the disease name,
  (2) what the retrieval score gap is between rank-1 and rank-2, and whether it is large (>0.05),
  (3) whether condition A or B above is clearly met to justify changing rank-1.
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
The patient does not have arachnodactyly, but this is not an obligatory feature of Contractural arachnodactyly, congenital. The retrieval score gap between rank-1 and rank-2 is 0.090213, which is large (>0.05). Neither exclusion criterion A nor superior coverage criterion B is met. Therefore, the ranking will be preserved.

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
Preserve rank-1 unless you find a specific, named clinical reason to change it.
The cost of incorrectly demoting rank-1 is higher than the cost of missing a promotion.
When in doubt, keep rank-1.

## Retrieval score gap rule
The retrieval_score gap between rank-1 and rank-2 reflects how much more strongly the model supports rank-1.
If the gap is large (rank-1 score minus rank-2 score > 0.05), a single absent feature is not sufficient to demote rank-1.
A large gap requires multiple independent hard exclusions — not one absent finding, no matter how seemingly specific.

## The only two valid reasons to demote retrieval rank-1
A. EXCLUSION: A feature that is OBLIGATORY (present in >90% of cases) for rank-1 is explicitly absent in this patient.
   'Hallmark', 'typical', or 'common' features are NOT sufficient — only truly obligatory features qualify.
   CRITICAL: Do NOT infer obligatory features from the disease name. Phenotype words in a disease name
   (e.g. 'arachnodactyly' in 'Contractural arachnodactyly', 'cutis laxa' in 'Cutis laxa type ID',
   'hip dysplasia' in 'Osteosclerosis with hip dysplasia') are NOT evidence that feature is obligatory.
   Disease names reflect historical descriptions, not penetrance. Use only independent medical knowledge of penetrance.
B. SUPERIOR COVERAGE: A challenger explains ALL of the same organ systems as rank-1, PLUS at least one additional organ system or a highly specific finding rank-1 cannot explain.
   Explaining a single finding more specifically, while rank-1 explains more systems overall, is NOT superior coverage.
   The challenger must be a candidate from the list below — do not reason about diagnoses outside the list.
If neither A nor B is clearly met, keep rank-1 at position 1.

## Additional rules
- Negative phenotypes are hard clinical evidence ONLY when the absent feature is truly obligatory for a disease.
  Variable-penetrance features (even if present in 50-80% of cases) are not grounds for exclusion.
- Multi-system coherence wins over single-organ specificity. A disease explaining cardiac + limb findings together beats one explaining only the limb findings more precisely.
- For related disease families, numbered subtypes, and broad-vs-narrow syndrome names: treat them as distinct diseases. Require explicit discriminating findings to switch between them.
- Do not switch based on disease-name wording, lexical overlap with one phenotype, or apparent subtype specificity.
- Copy the exact candidate ID and exact candidate name from the list. Do not invent IDs or names.

## Required output
First write a brief clinical reasoning note (2-3 sentences) stating:
  (1) whether any candidate is excluded by an OBLIGATORY (>90% penetrance) negative phenotype — and confirm this is NOT inferred from the disease name,
  (2) what the retrieval score gap is between rank-1 and rank-2, and whether it is large (>0.05),
  (3) whether condition A or B above is clearly met to justify changing rank-1.
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
The patient has atrial septal defect and upper limb anomalies (short thumb, 3-4 finger syndactyly, aplasia of the 3rd finger). There are no obligatory features for Holt-Oram syndrome absent in this patient; while upper limb defects are common, they are not present in >90% of cases. The retrieval score gap between Holt-Oram syndrome (rank 1) and Syndactyly, mesoaxial synostotic, with phalangeal reduction (rank 2) is 0.045837, which is not large (>0.05). Neither exclusion criterion A nor superior coverage criterion B is met. Therefore, the ranking remains unchanged.

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

