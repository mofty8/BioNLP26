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

## The only two valid reasons to demote retrieval rank-1
A. EXCLUSION: A finding that is a hallmark or very common feature of rank-1 is explicitly absent in this patient.
   'Less directly associated' or 'not the first explanation' is NOT exclusion.
B. SUPERIOR COVERAGE: A challenger explains ALL of the same organ systems as rank-1, PLUS at least one additional organ system or a highly specific finding rank-1 cannot explain.
   Explaining a single finding more specifically, while rank-1 explains more systems overall, is NOT superior coverage.
If neither A nor B is clearly met, keep rank-1 at position 1.

## Additional rules
- Negative phenotypes are hard clinical evidence. If a disease's hallmark feature is explicitly absent, that disease must rank below any candidate not contradicted by absent findings.
- Multi-system coherence wins over single-organ specificity. A disease explaining cardiac + limb findings together beats one explaining only the limb findings more precisely.
- For related disease families, numbered subtypes, and broad-vs-narrow syndrome names: treat them as distinct diseases. Require explicit discriminating findings to switch between them.
- Do not switch based on disease-name wording, lexical overlap with one phenotype, or apparent subtype specificity.
- Copy the exact candidate ID and exact candidate name from the list. Do not invent IDs or names.

## Required output
First write a brief clinical reasoning note (2-3 sentences) stating:
  (1) whether any candidate is excluded by a hallmark negative phenotype,
  (2) which candidate best explains the broadest combination of findings across organ systems,
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
The patient's presentation of chronic sinusitis, bronchitis, rhinitis, and nasal polyposis is highly suggestive of a primary ciliary dyskinesia (PCD). MHC class I deficiency does not readily explain the chronic airway issues, and the absence of severe viral infection makes it less likely. Ciliary dyskinesia, primary, 5 and 35 both explain the respiratory findings well, but the retrieval model ranked 5 higher, and there's no clear clinical reason to demote it.

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
Preserve rank-1 unless you find a specific, named clinical reason to change it.
The cost of incorrectly demoting rank-1 is higher than the cost of missing a promotion.
When in doubt, keep rank-1.

## The only two valid reasons to demote retrieval rank-1
A. EXCLUSION: A finding that is a hallmark or very common feature of rank-1 is explicitly absent in this patient.
   'Less directly associated' or 'not the first explanation' is NOT exclusion.
B. SUPERIOR COVERAGE: A challenger explains ALL of the same organ systems as rank-1, PLUS at least one additional organ system or a highly specific finding rank-1 cannot explain.
   Explaining a single finding more specifically, while rank-1 explains more systems overall, is NOT superior coverage.
If neither A nor B is clearly met, keep rank-1 at position 1.

## Additional rules
- Negative phenotypes are hard clinical evidence. If a disease's hallmark feature is explicitly absent, that disease must rank below any candidate not contradicted by absent findings.
- Multi-system coherence wins over single-organ specificity. A disease explaining cardiac + limb findings together beats one explaining only the limb findings more precisely.
- For related disease families, numbered subtypes, and broad-vs-narrow syndrome names: treat them as distinct diseases. Require explicit discriminating findings to switch between them.
- Do not switch based on disease-name wording, lexical overlap with one phenotype, or apparent subtype specificity.
- Copy the exact candidate ID and exact candidate name from the list. Do not invent IDs or names.

## Required output
First write a brief clinical reasoning note (2-3 sentences) stating:
  (1) whether any candidate is excluded by a hallmark negative phenotype,
  (2) which candidate best explains the broadest combination of findings across organ systems,
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
The patient has a constellation of bradyarrhythmias (sinus bradycardia, first-degree AV block, atrial fibrillation) without evidence of heart failure or cardiomyopathy, which excludes dilated cardiomyopathy as the primary diagnosis. Sick sinus syndrome 2 explains the bradyarrhythmias well, and does not require the presence of cardiomyopathy. While the retrieval model ranked dilated cardiomyopathy first, the explicit absence of dilated cardiomyopathy and heart failure meets exclusion criterion A, justifying a reranking.

```json
{
  "selected_candidate": {"id": "OMIM:163800", "name": "Sick sinus syndrome 2"},
  "ranking": [
    {"rank": 1, "id": "OMIM:163800", "name": "Sick sinus syndrome 2"},
    {"rank": 2, "id": "OMIM:600858", "name": "Cardiomyopathy, familial hypertrophic, 6"},
    {"rank": 3, "id": "OMIM:115200", "name": "Cardiomyopathy, dilated, 1A"}
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
      "id": "OMIM:600858",
      "name": "Cardiomyopathy, familial hypertrophic, 6",
      "source": "model"
    },
    {
      "rank": 3,
      "id": "OMIM:115200",
      "name": "Cardiomyopathy, dilated, 1A",
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

## The only two valid reasons to demote retrieval rank-1
A. EXCLUSION: A finding that is a hallmark or very common feature of rank-1 is explicitly absent in this patient.
   'Less directly associated' or 'not the first explanation' is NOT exclusion.
B. SUPERIOR COVERAGE: A challenger explains ALL of the same organ systems as rank-1, PLUS at least one additional organ system or a highly specific finding rank-1 cannot explain.
   Explaining a single finding more specifically, while rank-1 explains more systems overall, is NOT superior coverage.
If neither A nor B is clearly met, keep rank-1 at position 1.

## Additional rules
- Negative phenotypes are hard clinical evidence. If a disease's hallmark feature is explicitly absent, that disease must rank below any candidate not contradicted by absent findings.
- Multi-system coherence wins over single-organ specificity. A disease explaining cardiac + limb findings together beats one explaining only the limb findings more precisely.
- For related disease families, numbered subtypes, and broad-vs-narrow syndrome names: treat them as distinct diseases. Require explicit discriminating findings to switch between them.
- Do not switch based on disease-name wording, lexical overlap with one phenotype, or apparent subtype specificity.
- Copy the exact candidate ID and exact candidate name from the list. Do not invent IDs or names.

## Required output
First write a brief clinical reasoning note (2-3 sentences) stating:
  (1) whether any candidate is excluded by a hallmark negative phenotype,
  (2) which candidate best explains the broadest combination of findings across organ systems,
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
The patient's presentation of atrial fibrillation, congestive heart failure, dilated cardiomyopathy, and conduction abnormalities (second-degree AV block, sudden cardiac death) strongly suggests a primary cardiac condition. The absence of first, third degree AV block, and sinus bradycardia does not exclude any of the candidates. Rank-1, dilated cardiomyopathy 1A, explains the core cardiac findings well, and no other candidate provides superior coverage. Condition A or B is not met to justify demoting rank-1.

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

## The only two valid reasons to demote retrieval rank-1
A. EXCLUSION: A finding that is a hallmark or very common feature of rank-1 is explicitly absent in this patient.
   'Less directly associated' or 'not the first explanation' is NOT exclusion.
B. SUPERIOR COVERAGE: A challenger explains ALL of the same organ systems as rank-1, PLUS at least one additional organ system or a highly specific finding rank-1 cannot explain.
   Explaining a single finding more specifically, while rank-1 explains more systems overall, is NOT superior coverage.
If neither A nor B is clearly met, keep rank-1 at position 1.

## Additional rules
- Negative phenotypes are hard clinical evidence. If a disease's hallmark feature is explicitly absent, that disease must rank below any candidate not contradicted by absent findings.
- Multi-system coherence wins over single-organ specificity. A disease explaining cardiac + limb findings together beats one explaining only the limb findings more precisely.
- For related disease families, numbered subtypes, and broad-vs-narrow syndrome names: treat them as distinct diseases. Require explicit discriminating findings to switch between them.
- Do not switch based on disease-name wording, lexical overlap with one phenotype, or apparent subtype specificity.
- Copy the exact candidate ID and exact candidate name from the list. Do not invent IDs or names.

## Required output
First write a brief clinical reasoning note (2-3 sentences) stating:
  (1) whether any candidate is excluded by a hallmark negative phenotype,
  (2) which candidate best explains the broadest combination of findings across organ systems,
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
The patient has multiple joint contractures, a high palate, and micrognathia. The negative phenotype of absent arachnodactyly excludes Contractural arachnodactyly, congenital (OMIM:121050) as the primary diagnosis. Arthrogryposis, distal, type 1C (OMIM:619110) explains the contractures well and doesn't have any exclusionary negative findings. Condition A (exclusion) is met for the rank-1 candidate.

```json
{
  "selected_candidate": {"id": "OMIM:619110", "name": "Arthrogryposis, distal, type 1C"},
  "ranking": [
    {"rank": 1, "id": "OMIM:619110", "name": "Arthrogryposis, distal, type 1C"},
    {"rank": 2, "id": "OMIM:620727", "name": "Ullrich congenital muscular dystrophy 1B"},
    {"rank": 3, "id": "OMIM:121050", "name": "Contractural arachnodactyly, congenital"}
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
      "id": "OMIM:620727",
      "name": "Ullrich congenital muscular dystrophy 1B",
      "source": "model"
    },
    {
      "rank": 3,
      "id": "OMIM:121050",
      "name": "Contractural arachnodactyly, congenital",
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

## The only two valid reasons to demote retrieval rank-1
A. EXCLUSION: A finding that is a hallmark or very common feature of rank-1 is explicitly absent in this patient.
   'Less directly associated' or 'not the first explanation' is NOT exclusion.
B. SUPERIOR COVERAGE: A challenger explains ALL of the same organ systems as rank-1, PLUS at least one additional organ system or a highly specific finding rank-1 cannot explain.
   Explaining a single finding more specifically, while rank-1 explains more systems overall, is NOT superior coverage.
If neither A nor B is clearly met, keep rank-1 at position 1.

## Additional rules
- Negative phenotypes are hard clinical evidence. If a disease's hallmark feature is explicitly absent, that disease must rank below any candidate not contradicted by absent findings.
- Multi-system coherence wins over single-organ specificity. A disease explaining cardiac + limb findings together beats one explaining only the limb findings more precisely.
- For related disease families, numbered subtypes, and broad-vs-narrow syndrome names: treat them as distinct diseases. Require explicit discriminating findings to switch between them.
- Do not switch based on disease-name wording, lexical overlap with one phenotype, or apparent subtype specificity.
- Copy the exact candidate ID and exact candidate name from the list. Do not invent IDs or names.

## Required output
First write a brief clinical reasoning note (2-3 sentences) stating:
  (1) whether any candidate is excluded by a hallmark negative phenotype,
  (2) which candidate best explains the broadest combination of findings across organ systems,
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
The patient's negative phenotypes explicitly exclude several ventricular septal defects and other complex congenital heart defects, which are common in Holt-Oram syndrome. However, the atrial septal defect is still consistent with Holt-Oram syndrome. Holt-Oram syndrome explains both the cardiac (atrial septal defect) and limb (syndactyly, aplasia of the 3rd finger, short thumb) findings, while the other candidates do not offer the same multi-system coverage. Condition A is not clearly met, and condition B is not met.

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

