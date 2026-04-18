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
Use clinical reasoning to improve on the retrieval ranking: promote a better candidate when evidence supports it, or preserve rank-1 when it is well-supported.

## Score gap rule — the most important signal
Compute: gap = rank-1 retrieval_score minus rank-2 retrieval_score.
  gap < 0.05  (small):      the retrieval model was uncertain. Clinical reasoning should freely determine the final ranking.
  gap >= 0.05 (large):       rank-1 is strongly supported. Require strong clinical evidence to demote it.
  gap >= 0.10 (very large):  rank-1 is very strongly supported. Do not demote unless two or more obligatory features are absent.

## Valid reasons to change rank-1
A. EXCLUSION: A feature that is OBLIGATORY (present in >90% of cases) for rank-1 is explicitly absent in this patient.
   'Hallmark', 'typical', or 'common' features are NOT sufficient — only truly obligatory features qualify.
   CRITICAL: Do NOT infer obligatory features from the disease name. Phenotype words in a disease name
   (e.g. 'arachnodactyly' in 'Contractural arachnodactyly', 'cutis laxa' in 'Cutis laxa type ID',
   'hip dysplasia' in 'Osteosclerosis with hip dysplasia') are NOT evidence that feature is obligatory.
   Disease names reflect historical descriptions, not penetrance. Use only independent medical knowledge of penetrance.
B. SUPERIOR COVERAGE: A challenger explains ALL of the same organ systems as rank-1, PLUS at least one additional organ system or a highly specific finding rank-1 cannot explain.
   Explaining a single finding more specifically, while rank-1 explains more systems overall, is NOT superior coverage.
   The challenger must be a candidate from the list below — do not reason about diagnoses outside the list.
When gap is small (<0.05): either A or B with moderate evidence is sufficient to rerank.
When gap is large (>=0.05): A and B require strong, unambiguous evidence; a single uncertain finding is not enough.
When gap is very large (>=0.10): do not rerank unless two or more obligatory features are absent.

## Additional rules
- Negative phenotypes are hard clinical evidence ONLY when the absent feature is truly obligatory for a disease.
  Variable-penetrance features (even if present in 50-80% of cases) are not grounds for exclusion.
- Multi-system coherence wins over single-organ specificity. A disease explaining cardiac + limb findings together beats one explaining only the limb findings more precisely.
- For related disease families, numbered subtypes, and broad-vs-narrow syndrome names: treat them as distinct diseases. Require explicit discriminating findings to switch between them.
- Do not switch based on disease-name wording, lexical overlap with one phenotype, or apparent subtype specificity.
- Copy the exact candidate ID and exact candidate name from the list. Do not invent IDs or names.

## Required output
First write a brief clinical reasoning note (2-3 sentences) stating:
  (1) the score gap between rank-1 and rank-2, and whether it is small (<0.05), large (>=0.05), or very large (>=0.10),
  (2) whether any candidate is excluded by an OBLIGATORY (>90% penetrance) absent feature — confirm this is NOT inferred from the disease name,
  (3) which candidate best explains the broadest combination of findings, and your final ranking decision.
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
The score gap between MHC class I deficiency 2 (rank 1) and Ciliary dyskinesia, primary, 5 (rank 2) is 0.097321, which is large. There are no obligatory features for MHC class I deficiency 2 that are absent in this patient. Both candidates explain the respiratory phenotypes (sinusitis, bronchitis, rhinitis, nasal polyposis), but MHC class I deficiency 2 is a primary immunodeficiency that can present with chronic respiratory infections, while ciliary dyskinesia is a structural defect of the cilia. Given the lack of specific findings pointing towards ciliary dysfunction, and the broader explanatory power of MHC class I deficiency 2, I will preserve the original ranking.

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
Use clinical reasoning to improve on the retrieval ranking: promote a better candidate when evidence supports it, or preserve rank-1 when it is well-supported.

## Score gap rule — the most important signal
Compute: gap = rank-1 retrieval_score minus rank-2 retrieval_score.
  gap < 0.05  (small):      the retrieval model was uncertain. Clinical reasoning should freely determine the final ranking.
  gap >= 0.05 (large):       rank-1 is strongly supported. Require strong clinical evidence to demote it.
  gap >= 0.10 (very large):  rank-1 is very strongly supported. Do not demote unless two or more obligatory features are absent.

## Valid reasons to change rank-1
A. EXCLUSION: A feature that is OBLIGATORY (present in >90% of cases) for rank-1 is explicitly absent in this patient.
   'Hallmark', 'typical', or 'common' features are NOT sufficient — only truly obligatory features qualify.
   CRITICAL: Do NOT infer obligatory features from the disease name. Phenotype words in a disease name
   (e.g. 'arachnodactyly' in 'Contractural arachnodactyly', 'cutis laxa' in 'Cutis laxa type ID',
   'hip dysplasia' in 'Osteosclerosis with hip dysplasia') are NOT evidence that feature is obligatory.
   Disease names reflect historical descriptions, not penetrance. Use only independent medical knowledge of penetrance.
B. SUPERIOR COVERAGE: A challenger explains ALL of the same organ systems as rank-1, PLUS at least one additional organ system or a highly specific finding rank-1 cannot explain.
   Explaining a single finding more specifically, while rank-1 explains more systems overall, is NOT superior coverage.
   The challenger must be a candidate from the list below — do not reason about diagnoses outside the list.
When gap is small (<0.05): either A or B with moderate evidence is sufficient to rerank.
When gap is large (>=0.05): A and B require strong, unambiguous evidence; a single uncertain finding is not enough.
When gap is very large (>=0.10): do not rerank unless two or more obligatory features are absent.

## Additional rules
- Negative phenotypes are hard clinical evidence ONLY when the absent feature is truly obligatory for a disease.
  Variable-penetrance features (even if present in 50-80% of cases) are not grounds for exclusion.
- Multi-system coherence wins over single-organ specificity. A disease explaining cardiac + limb findings together beats one explaining only the limb findings more precisely.
- For related disease families, numbered subtypes, and broad-vs-narrow syndrome names: treat them as distinct diseases. Require explicit discriminating findings to switch between them.
- Do not switch based on disease-name wording, lexical overlap with one phenotype, or apparent subtype specificity.
- Copy the exact candidate ID and exact candidate name from the list. Do not invent IDs or names.

## Required output
First write a brief clinical reasoning note (2-3 sentences) stating:
  (1) the score gap between rank-1 and rank-2, and whether it is small (<0.05), large (>=0.05), or very large (>=0.10),
  (2) whether any candidate is excluded by an OBLIGATORY (>90% penetrance) absent feature — confirm this is NOT inferred from the disease name,
  (3) which candidate best explains the broadest combination of findings, and your final ranking decision.
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
The score gap between rank-1 (Cardiomyopathy, dilated, 1A) and rank-2 (Sick sinus syndrome 2) is 0.052, which is a large gap. There are no obligatory features for dilated cardiomyopathy that are explicitly absent in this patient. While the patient has several cardiac conduction abnormalities (atrial fibrillation, first-degree AV block, sinus bradycardia), the absence of dilated cardiomyopathy and congestive heart failure argues *against* dilated cardiomyopathy. Sick sinus syndrome 2 better explains the bradycardia and conduction abnormalities without requiring the presence of cardiomyopathy or heart failure. Therefore, I will rerank the candidates.

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
Use clinical reasoning to improve on the retrieval ranking: promote a better candidate when evidence supports it, or preserve rank-1 when it is well-supported.

## Score gap rule — the most important signal
Compute: gap = rank-1 retrieval_score minus rank-2 retrieval_score.
  gap < 0.05  (small):      the retrieval model was uncertain. Clinical reasoning should freely determine the final ranking.
  gap >= 0.05 (large):       rank-1 is strongly supported. Require strong clinical evidence to demote it.
  gap >= 0.10 (very large):  rank-1 is very strongly supported. Do not demote unless two or more obligatory features are absent.

## Valid reasons to change rank-1
A. EXCLUSION: A feature that is OBLIGATORY (present in >90% of cases) for rank-1 is explicitly absent in this patient.
   'Hallmark', 'typical', or 'common' features are NOT sufficient — only truly obligatory features qualify.
   CRITICAL: Do NOT infer obligatory features from the disease name. Phenotype words in a disease name
   (e.g. 'arachnodactyly' in 'Contractural arachnodactyly', 'cutis laxa' in 'Cutis laxa type ID',
   'hip dysplasia' in 'Osteosclerosis with hip dysplasia') are NOT evidence that feature is obligatory.
   Disease names reflect historical descriptions, not penetrance. Use only independent medical knowledge of penetrance.
B. SUPERIOR COVERAGE: A challenger explains ALL of the same organ systems as rank-1, PLUS at least one additional organ system or a highly specific finding rank-1 cannot explain.
   Explaining a single finding more specifically, while rank-1 explains more systems overall, is NOT superior coverage.
   The challenger must be a candidate from the list below — do not reason about diagnoses outside the list.
When gap is small (<0.05): either A or B with moderate evidence is sufficient to rerank.
When gap is large (>=0.05): A and B require strong, unambiguous evidence; a single uncertain finding is not enough.
When gap is very large (>=0.10): do not rerank unless two or more obligatory features are absent.

## Additional rules
- Negative phenotypes are hard clinical evidence ONLY when the absent feature is truly obligatory for a disease.
  Variable-penetrance features (even if present in 50-80% of cases) are not grounds for exclusion.
- Multi-system coherence wins over single-organ specificity. A disease explaining cardiac + limb findings together beats one explaining only the limb findings more precisely.
- For related disease families, numbered subtypes, and broad-vs-narrow syndrome names: treat them as distinct diseases. Require explicit discriminating findings to switch between them.
- Do not switch based on disease-name wording, lexical overlap with one phenotype, or apparent subtype specificity.
- Copy the exact candidate ID and exact candidate name from the list. Do not invent IDs or names.

## Required output
First write a brief clinical reasoning note (2-3 sentences) stating:
  (1) the score gap between rank-1 and rank-2, and whether it is small (<0.05), large (>=0.05), or very large (>=0.10),
  (2) whether any candidate is excluded by an OBLIGATORY (>90% penetrance) absent feature — confirm this is NOT inferred from the disease name,
  (3) which candidate best explains the broadest combination of findings, and your final ranking decision.
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
The score gap between rank-1 (OMIM:115200) and rank-2 (OMIM:616117) is 0.146421, which is very large. There are no obligatory features for dilated cardiomyopathy 1A that are explicitly absent in this patient. Both candidates explain the cardiac findings well, but OMIM:115200 (dilated cardiomyopathy, 1A) is a more specific diagnosis within the broader category of dilated cardiomyopathy and is strongly supported by the retrieval score. Therefore, I will preserve the rank-1 candidate.

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
Use clinical reasoning to improve on the retrieval ranking: promote a better candidate when evidence supports it, or preserve rank-1 when it is well-supported.

## Score gap rule — the most important signal
Compute: gap = rank-1 retrieval_score minus rank-2 retrieval_score.
  gap < 0.05  (small):      the retrieval model was uncertain. Clinical reasoning should freely determine the final ranking.
  gap >= 0.05 (large):       rank-1 is strongly supported. Require strong clinical evidence to demote it.
  gap >= 0.10 (very large):  rank-1 is very strongly supported. Do not demote unless two or more obligatory features are absent.

## Valid reasons to change rank-1
A. EXCLUSION: A feature that is OBLIGATORY (present in >90% of cases) for rank-1 is explicitly absent in this patient.
   'Hallmark', 'typical', or 'common' features are NOT sufficient — only truly obligatory features qualify.
   CRITICAL: Do NOT infer obligatory features from the disease name. Phenotype words in a disease name
   (e.g. 'arachnodactyly' in 'Contractural arachnodactyly', 'cutis laxa' in 'Cutis laxa type ID',
   'hip dysplasia' in 'Osteosclerosis with hip dysplasia') are NOT evidence that feature is obligatory.
   Disease names reflect historical descriptions, not penetrance. Use only independent medical knowledge of penetrance.
B. SUPERIOR COVERAGE: A challenger explains ALL of the same organ systems as rank-1, PLUS at least one additional organ system or a highly specific finding rank-1 cannot explain.
   Explaining a single finding more specifically, while rank-1 explains more systems overall, is NOT superior coverage.
   The challenger must be a candidate from the list below — do not reason about diagnoses outside the list.
When gap is small (<0.05): either A or B with moderate evidence is sufficient to rerank.
When gap is large (>=0.05): A and B require strong, unambiguous evidence; a single uncertain finding is not enough.
When gap is very large (>=0.10): do not rerank unless two or more obligatory features are absent.

## Additional rules
- Negative phenotypes are hard clinical evidence ONLY when the absent feature is truly obligatory for a disease.
  Variable-penetrance features (even if present in 50-80% of cases) are not grounds for exclusion.
- Multi-system coherence wins over single-organ specificity. A disease explaining cardiac + limb findings together beats one explaining only the limb findings more precisely.
- For related disease families, numbered subtypes, and broad-vs-narrow syndrome names: treat them as distinct diseases. Require explicit discriminating findings to switch between them.
- Do not switch based on disease-name wording, lexical overlap with one phenotype, or apparent subtype specificity.
- Copy the exact candidate ID and exact candidate name from the list. Do not invent IDs or names.

## Required output
First write a brief clinical reasoning note (2-3 sentences) stating:
  (1) the score gap between rank-1 and rank-2, and whether it is small (<0.05), large (>=0.05), or very large (>=0.10),
  (2) whether any candidate is excluded by an OBLIGATORY (>90% penetrance) absent feature — confirm this is NOT inferred from the disease name,
  (3) which candidate best explains the broadest combination of findings, and your final ranking decision.
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
The score gap between rank-1 (Contractural arachnodactyly, congenital) and rank-2 (Arthrogryposis, distal, type 1C) is 0.090213, which is large. Arachnodactyly is explicitly absent in this patient, but this is not an obligatory feature of Contractural arachnodactyly, congenital. Both candidates explain multiple features well, but Arthrogryposis, distal, type 1C better explains the multiple joint contractures (elbow, hip, knee) and skeletal features (scoliosis, high palate, micrognathia) without the arachnodactyly seen in the rank-1 candidate. Therefore, I will rerank to place Arthrogryposis, distal, type 1C as rank-1.

```json
{
  "selected_candidate": {"id": "OMIM:619110", "name": "Arthrogryposis, distal, type 1C"},
  "ranking": [
    {"rank": 1, "id": "OMIM:619110", "name": "Arthrogryposis, distal, type 1C"},
    {"rank": 2, "id": "OMIM:121050", "name": "Contractural arachnodactyly, congenital"},
    {"rank": 3, "id": "OMIM:620727", "name": "Ullrich congenital muscular dystrophy 1B"}
  ]
}
```
```

### Parsed Output
```json
{
  "selected_candidate": {
    "id": "OMIM:619110",
    "name": "Arthrogryposis, distal, type 1C"
  },
  "ranking": [
    {
      "rank": 1,
      "id": "OMIM:619110",
      "name": "Arthrogryposis, distal, type 1C",
      "source": "model"
    },
    {
      "rank": 2,
      "id": "OMIM:121050",
      "name": "Contractural arachnodactyly, congenital",
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
Use clinical reasoning to improve on the retrieval ranking: promote a better candidate when evidence supports it, or preserve rank-1 when it is well-supported.

## Score gap rule — the most important signal
Compute: gap = rank-1 retrieval_score minus rank-2 retrieval_score.
  gap < 0.05  (small):      the retrieval model was uncertain. Clinical reasoning should freely determine the final ranking.
  gap >= 0.05 (large):       rank-1 is strongly supported. Require strong clinical evidence to demote it.
  gap >= 0.10 (very large):  rank-1 is very strongly supported. Do not demote unless two or more obligatory features are absent.

## Valid reasons to change rank-1
A. EXCLUSION: A feature that is OBLIGATORY (present in >90% of cases) for rank-1 is explicitly absent in this patient.
   'Hallmark', 'typical', or 'common' features are NOT sufficient — only truly obligatory features qualify.
   CRITICAL: Do NOT infer obligatory features from the disease name. Phenotype words in a disease name
   (e.g. 'arachnodactyly' in 'Contractural arachnodactyly', 'cutis laxa' in 'Cutis laxa type ID',
   'hip dysplasia' in 'Osteosclerosis with hip dysplasia') are NOT evidence that feature is obligatory.
   Disease names reflect historical descriptions, not penetrance. Use only independent medical knowledge of penetrance.
B. SUPERIOR COVERAGE: A challenger explains ALL of the same organ systems as rank-1, PLUS at least one additional organ system or a highly specific finding rank-1 cannot explain.
   Explaining a single finding more specifically, while rank-1 explains more systems overall, is NOT superior coverage.
   The challenger must be a candidate from the list below — do not reason about diagnoses outside the list.
When gap is small (<0.05): either A or B with moderate evidence is sufficient to rerank.
When gap is large (>=0.05): A and B require strong, unambiguous evidence; a single uncertain finding is not enough.
When gap is very large (>=0.10): do not rerank unless two or more obligatory features are absent.

## Additional rules
- Negative phenotypes are hard clinical evidence ONLY when the absent feature is truly obligatory for a disease.
  Variable-penetrance features (even if present in 50-80% of cases) are not grounds for exclusion.
- Multi-system coherence wins over single-organ specificity. A disease explaining cardiac + limb findings together beats one explaining only the limb findings more precisely.
- For related disease families, numbered subtypes, and broad-vs-narrow syndrome names: treat them as distinct diseases. Require explicit discriminating findings to switch between them.
- Do not switch based on disease-name wording, lexical overlap with one phenotype, or apparent subtype specificity.
- Copy the exact candidate ID and exact candidate name from the list. Do not invent IDs or names.

## Required output
First write a brief clinical reasoning note (2-3 sentences) stating:
  (1) the score gap between rank-1 and rank-2, and whether it is small (<0.05), large (>=0.05), or very large (>=0.10),
  (2) whether any candidate is excluded by an OBLIGATORY (>90% penetrance) absent feature — confirm this is NOT inferred from the disease name,
  (3) which candidate best explains the broadest combination of findings, and your final ranking decision.
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
The score gap between Holt-Oram syndrome (rank 1) and Syndactyly, mesoaxial synostotic, with phalangeal reduction (rank 2) is 0.045837, which is small. There are no obligatory features for Holt-Oram syndrome that are explicitly absent in this patient. Holt-Oram syndrome explains the atrial septal defect and limb abnormalities (syndactyly, aplasia of the 3rd finger, short thumb) as a cohesive syndrome, while the syndactyly syndrome focuses solely on the hand findings. Therefore, Holt-Oram syndrome provides broader coverage and is the more appropriate diagnosis.

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

