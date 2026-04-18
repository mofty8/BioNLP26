# Qualitative Examples

## PMID_10077612_FamilyAIII-10

Truth IDs: `OMIM:142900`

### Prompt
```text
You are a rare disease expert reranking a short list of candidate diagnoses for a single patient.
The candidates were retrieved by a phenotype-similarity model. Your job is to rerank them using clinical reasoning.
Choose only from the candidate list provided below.

## Core principle
The retrieval model is well-calibrated. Its rank-1 candidate is correct more than half the time.
Each candidate below includes HPO phenotype annotations with observed frequencies from medical literature.
Use these frequencies — not your own guesses — to judge which features are obligatory (>=90%) vs variable.

## The two valid reasons to change rank-1
A. EXCLUSION: A phenotype annotated at >=90% frequency for rank-1 is explicitly listed as ABSENT (negative phenotype) in this patient.
   Only features tagged [OBLIGATORY, PATIENT ABSENT] in the annotations qualify for exclusion.
   If the annotations show a feature at <90%, it is NOT grounds for exclusion even if absent.
   CRITICAL: A disease having obligatory features that the patient simply did NOT REPORT is NOT evidence against it.
   Patients rarely report all their features. Only features explicitly listed as ABSENT (negative phenotypes) count.
B. COVERAGE GAP: Rank-1 fails to explain at least one key positive phenotype or organ system present in this patient,
   AND a challenger explains that gap, AND the challenger covers at least as many of the other phenotypes as rank-1.
   Use the annotations to verify coverage: a disease 'explains' a phenotype only if it is annotated for that disease.
   Compare how many of the patient's positive phenotypes are annotated for each candidate.
   IMPORTANT: The fact that a challenger has more total annotations or more obligatory features does NOT mean it is a better match.
   Focus ONLY on the patient's actual phenotypes — not on unreported disease features.
   The challenger must be a candidate from the list below — do not reason about diagnoses outside the list.
If neither A nor B is clearly met, keep rank-1 at position 1.

## Additional rules
- Use the frequency annotations to determine obligatory features. Do NOT override annotated frequencies with your own assumptions.
- Features with frequency <90% are variable and CANNOT be used for exclusion, even if they seem important.
- CRITICAL: Do NOT penalize rank-1 for having obligatory features the patient did not report. Unreported ≠ absent.
  Only features explicitly listed in the 'Negative phenotypes' section are confirmed absent.
- When in doubt, keep rank-1. The retrieval model's ranking is strong evidence.
- Multi-system coherence wins over single-organ specificity. A disease explaining cardiac + limb findings together beats one explaining only the limb findings more precisely.
- For related disease families, numbered subtypes, and broad-vs-narrow syndrome names: treat them as distinct diseases. Require explicit discriminating findings to switch between them.
- Do not switch based on disease-name wording, lexical overlap with one phenotype, or apparent subtype specificity.
- Copy the exact candidate ID and exact candidate name from the list. Do not invent IDs or names.

## Required output
First write a brief clinical reasoning note (2-3 sentences) stating:
  (1) whether rank-1 has any OBLIGATORY (>=90%) annotated feature that is absent in this patient,
  (2) which candidate's annotations best match the patient's positive phenotypes,
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
- Atrial septal defect (HP:0001631)
- Hypoplasia of the radius (HP:0002984)
- Abnormal carpal morphology (HP:0001191)
- Cardiac conduction abnormality (HP:0031546)
Negative phenotypes (explicitly absent):
- Ventricular septal defect (HP:0001629)
- Absent thumb (HP:0009777)
- Triphalangeal thumb (HP:0001199)
- Upper limb phocomelia (HP:0009813)
- Amelia involving the upper limbs (HP:0009812)
- Persistent left superior vena cava (HP:0005301)
- Common atrium (HP:0011565)
- Unroofed coronary sinus (HP:0031297)
- Patent ductus arteriosus (HP:0001643)

Candidate diseases:
1. id=OMIM:142900 | name=Holt-Oram syndrome | retrieval_score=0.781418 | retrieval_rank=1 | phenodp_total_similarity=0.781418
  - Atrial septal defect: 96% [OBLIGATORY, PATIENT HAS]
  - Abnormal carpal morphology: 95% [OBLIGATORY, PATIENT HAS]
  - Ventricular septal defect: 45% [PATIENT ABSENT]
  - Hypoplasia of the radius: 44% [PATIENT HAS]
  - Cardiac conduction abnormality: 39% [PATIENT HAS]
  - Absent thumb: 32% [PATIENT ABSENT]
  - Triphalangeal thumb: 25% [PATIENT ABSENT]
  - Patent ductus arteriosus: 17% [PATIENT ABSENT]
  - Persistent left superior vena cava: 10% [PATIENT ABSENT]
  - Upper limb phocomelia: 7% [PATIENT ABSENT]
  (88 more annotations omitted)
2. id=OMIM:127300 | name=Leri-Weill dyschondrosteosis | retrieval_score=0.697628 | retrieval_rank=2 | phenodp_total_similarity=0.697628
  - Abnormal carpal morphology: freq unknown [PATIENT HAS]
  - Hypoplasia of the radius: freq unknown [PATIENT HAS]
  - Multiple exostoses: freq unknown
  - Tibial bowing: freq unknown
  - Fibular hypoplasia: freq unknown
  - Abnormal humerus morphology: freq unknown
  - Disproportionate short-limb short stature: freq unknown
  - High palate: freq unknown
  - Limited elbow movement: freq unknown
  - Dorsal subluxation of ulna: freq unknown
  (15 more annotations omitted)
3. id=OMIM:191440 | name=Ulnar hypoplasia | retrieval_score=0.681751 | retrieval_rank=3 | phenodp_total_similarity=0.681751
  - Hypoplasia of the radius: freq unknown [PATIENT HAS]
  - Hypoplasia of the ulna: freq unknown
  - Ulnar deviation of the hand: freq unknown
  - Distal ulnar hypoplasia: freq unknown
  - Mesomelic arm shortening: freq unknown
  - Radial bowing: freq unknown
```

### Raw Output
```text
Holt-Oram syndrome (rank-1) has two obligatory features (atrial septal defect and abnormal carpal morphology) that are present in the patient. Leri-Weill dyschondrosteosis and Ulnar hypoplasia do not explain the atrial septal defect. Therefore, Holt-Oram syndrome remains the best candidate, as it covers the most key phenotypes and has no exclusionary criteria.

```json
{
  "selected_candidate": {"id": "OMIM:142900", "name": "Holt-Oram syndrome"},
  "ranking": [
    {"rank": 1, "id": "OMIM:142900", "name": "Holt-Oram syndrome"},
    {"rank": 2, "id": "OMIM:127300", "name": "Leri-Weill dyschondrosteosis"},
    {"rank": 3, "id": "OMIM:191440", "name": "Ulnar hypoplasia"}
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
      "id": "OMIM:127300",
      "name": "Leri-Weill dyschondrosteosis",
      "source": "model"
    },
    {
      "rank": 3,
      "id": "OMIM:191440",
      "name": "Ulnar hypoplasia",
      "source": "model"
    }
  ],
  "parse_mode": "json_object"
}
```

## PMID_10077612_FamilyAIII-3

Truth IDs: `OMIM:142900`

### Prompt
```text
You are a rare disease expert reranking a short list of candidate diagnoses for a single patient.
The candidates were retrieved by a phenotype-similarity model. Your job is to rerank them using clinical reasoning.
Choose only from the candidate list provided below.

## Core principle
The retrieval model is well-calibrated. Its rank-1 candidate is correct more than half the time.
Each candidate below includes HPO phenotype annotations with observed frequencies from medical literature.
Use these frequencies — not your own guesses — to judge which features are obligatory (>=90%) vs variable.

## The two valid reasons to change rank-1
A. EXCLUSION: A phenotype annotated at >=90% frequency for rank-1 is explicitly listed as ABSENT (negative phenotype) in this patient.
   Only features tagged [OBLIGATORY, PATIENT ABSENT] in the annotations qualify for exclusion.
   If the annotations show a feature at <90%, it is NOT grounds for exclusion even if absent.
   CRITICAL: A disease having obligatory features that the patient simply did NOT REPORT is NOT evidence against it.
   Patients rarely report all their features. Only features explicitly listed as ABSENT (negative phenotypes) count.
B. COVERAGE GAP: Rank-1 fails to explain at least one key positive phenotype or organ system present in this patient,
   AND a challenger explains that gap, AND the challenger covers at least as many of the other phenotypes as rank-1.
   Use the annotations to verify coverage: a disease 'explains' a phenotype only if it is annotated for that disease.
   Compare how many of the patient's positive phenotypes are annotated for each candidate.
   IMPORTANT: The fact that a challenger has more total annotations or more obligatory features does NOT mean it is a better match.
   Focus ONLY on the patient's actual phenotypes — not on unreported disease features.
   The challenger must be a candidate from the list below — do not reason about diagnoses outside the list.
If neither A nor B is clearly met, keep rank-1 at position 1.

## Additional rules
- Use the frequency annotations to determine obligatory features. Do NOT override annotated frequencies with your own assumptions.
- Features with frequency <90% are variable and CANNOT be used for exclusion, even if they seem important.
- CRITICAL: Do NOT penalize rank-1 for having obligatory features the patient did not report. Unreported ≠ absent.
  Only features explicitly listed in the 'Negative phenotypes' section are confirmed absent.
- When in doubt, keep rank-1. The retrieval model's ranking is strong evidence.
- Multi-system coherence wins over single-organ specificity. A disease explaining cardiac + limb findings together beats one explaining only the limb findings more precisely.
- For related disease families, numbered subtypes, and broad-vs-narrow syndrome names: treat them as distinct diseases. Require explicit discriminating findings to switch between them.
- Do not switch based on disease-name wording, lexical overlap with one phenotype, or apparent subtype specificity.
- Copy the exact candidate ID and exact candidate name from the list. Do not invent IDs or names.

## Required output
First write a brief clinical reasoning note (2-3 sentences) stating:
  (1) whether rank-1 has any OBLIGATORY (>=90%) annotated feature that is absent in this patient,
  (2) which candidate's annotations best match the patient's positive phenotypes,
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
- Ventricular septal defect (HP:0001629)
- Triphalangeal thumb (HP:0001199)
- Abnormal carpal morphology (HP:0001191)
Negative phenotypes (explicitly absent):
- Absent thumb (HP:0009777)
- Hypoplasia of the radius (HP:0002984)
- Upper limb phocomelia (HP:0009813)
- Amelia involving the upper limbs (HP:0009812)
- Cardiac conduction abnormality (HP:0031546)
- Persistent left superior vena cava (HP:0005301)
- Common atrium (HP:0011565)
- Unroofed coronary sinus (HP:0031297)
- Patent ductus arteriosus (HP:0001643)

Candidate diseases:
1. id=OMIM:615550 | name=Diamond-Blackfan anemia 12 | retrieval_score=0.650231 | retrieval_rank=1 | phenodp_total_similarity=0.650231
  - Triphalangeal thumb: 100% [OBLIGATORY, PATIENT HAS]
  - Ventricular septal defect: 100% [OBLIGATORY, PATIENT HAS]
  - Elevated red cell adenosine deaminase activity: 100% [OBLIGATORY]
  - Reticulocytopenia: 100% [OBLIGATORY]
  - Macrocytic anemia: 100% [OBLIGATORY]
  - Normochromic anemia: 100% [OBLIGATORY]
2. id=OMIM:142900 | name=Holt-Oram syndrome | retrieval_score=0.647902 | retrieval_rank=2 | phenodp_total_similarity=0.647902
  - Abnormal carpal morphology: 95% [OBLIGATORY, PATIENT HAS]
  - Ventricular septal defect: 45% [PATIENT HAS]
  - Hypoplasia of the radius: 44% [PATIENT ABSENT]
  - Cardiac conduction abnormality: 39% [PATIENT ABSENT]
  - Absent thumb: 32% [PATIENT ABSENT]
  - Triphalangeal thumb: 25% [PATIENT HAS]
  - Patent ductus arteriosus: 17% [PATIENT ABSENT]
  - Persistent left superior vena cava: 10% [PATIENT ABSENT]
  - Upper limb phocomelia: 7% [PATIENT ABSENT]
  - Amelia involving the upper limbs: 1% [PATIENT ABSENT]
  (88 more annotations omitted)
3. id=OMIM:192350 | name=Vater associationvacterl association, included | retrieval_score=0.589820 | retrieval_rank=3 | phenodp_total_similarity=0.589820
  - Triphalangeal thumb: freq unknown [PATIENT HAS]
  - Ventricular septal defect: freq unknown [PATIENT HAS]
  - Patent ductus arteriosus: freq unknown [PATIENT ABSENT]
  - Hypoplasia of the radius: freq unknown [PATIENT ABSENT]
  - Anal atresia: freq unknown
  - Tethered cord: freq unknown
  - Single umbilical artery: freq unknown
  - Ectopic kidney: freq unknown
  - Occipital encephalocele: freq unknown
  - Failure to thrive: freq unknown
  (27 more annotations omitted)
```

### Raw Output
```text
Diamond-Blackfan anemia 12 (rank-1) has no obligatory features listed as absent in this patient. Holt-Oram syndrome (rank-2) explains the abnormal carpal morphology better than Diamond-Blackfan anemia 12, and covers the ventricular septal defect and triphalangeal thumb. Therefore, I will rerank the candidates to place Holt-Oram syndrome at rank 1.

```json
{
  "selected_candidate": {"id": "OMIM:142900", "name": "Holt-Oram syndrome"},
  "ranking": [
    {"rank": 1, "id": "OMIM:142900", "name": "Holt-Oram syndrome"},
    {"rank": 2, "id": "OMIM:615550", "name": "Diamond-Blackfan anemia 12"},
    {"rank": 3, "id": "OMIM:192350", "name": "Vater associationvacterl association, included"}
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
      "id": "OMIM:615550",
      "name": "Diamond-Blackfan anemia 12",
      "source": "model"
    },
    {
      "rank": 3,
      "id": "OMIM:192350",
      "name": "Vater associationvacterl association, included",
      "source": "model"
    }
  ],
  "parse_mode": "json_object"
}
```

## PMID_10077612_FamilyAIV-11

Truth IDs: `OMIM:142900`

### Prompt
```text
You are a rare disease expert reranking a short list of candidate diagnoses for a single patient.
The candidates were retrieved by a phenotype-similarity model. Your job is to rerank them using clinical reasoning.
Choose only from the candidate list provided below.

## Core principle
The retrieval model is well-calibrated. Its rank-1 candidate is correct more than half the time.
Each candidate below includes HPO phenotype annotations with observed frequencies from medical literature.
Use these frequencies — not your own guesses — to judge which features are obligatory (>=90%) vs variable.

## The two valid reasons to change rank-1
A. EXCLUSION: A phenotype annotated at >=90% frequency for rank-1 is explicitly listed as ABSENT (negative phenotype) in this patient.
   Only features tagged [OBLIGATORY, PATIENT ABSENT] in the annotations qualify for exclusion.
   If the annotations show a feature at <90%, it is NOT grounds for exclusion even if absent.
   CRITICAL: A disease having obligatory features that the patient simply did NOT REPORT is NOT evidence against it.
   Patients rarely report all their features. Only features explicitly listed as ABSENT (negative phenotypes) count.
B. COVERAGE GAP: Rank-1 fails to explain at least one key positive phenotype or organ system present in this patient,
   AND a challenger explains that gap, AND the challenger covers at least as many of the other phenotypes as rank-1.
   Use the annotations to verify coverage: a disease 'explains' a phenotype only if it is annotated for that disease.
   Compare how many of the patient's positive phenotypes are annotated for each candidate.
   IMPORTANT: The fact that a challenger has more total annotations or more obligatory features does NOT mean it is a better match.
   Focus ONLY on the patient's actual phenotypes — not on unreported disease features.
   The challenger must be a candidate from the list below — do not reason about diagnoses outside the list.
If neither A nor B is clearly met, keep rank-1 at position 1.

## Additional rules
- Use the frequency annotations to determine obligatory features. Do NOT override annotated frequencies with your own assumptions.
- Features with frequency <90% are variable and CANNOT be used for exclusion, even if they seem important.
- CRITICAL: Do NOT penalize rank-1 for having obligatory features the patient did not report. Unreported ≠ absent.
  Only features explicitly listed in the 'Negative phenotypes' section are confirmed absent.
- When in doubt, keep rank-1. The retrieval model's ranking is strong evidence.
- Multi-system coherence wins over single-organ specificity. A disease explaining cardiac + limb findings together beats one explaining only the limb findings more precisely.
- For related disease families, numbered subtypes, and broad-vs-narrow syndrome names: treat them as distinct diseases. Require explicit discriminating findings to switch between them.
- Do not switch based on disease-name wording, lexical overlap with one phenotype, or apparent subtype specificity.
- Copy the exact candidate ID and exact candidate name from the list. Do not invent IDs or names.

## Required output
First write a brief clinical reasoning note (2-3 sentences) stating:
  (1) whether rank-1 has any OBLIGATORY (>=90%) annotated feature that is absent in this patient,
  (2) which candidate's annotations best match the patient's positive phenotypes,
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
- Hypoplasia of the radius (HP:0002984)
- Abnormal carpal morphology (HP:0001191)
- Persistent left superior vena cava (HP:0005301)
Negative phenotypes (explicitly absent):
- Ventricular septal defect (HP:0001629)
- Absent thumb (HP:0009777)
- Triphalangeal thumb (HP:0001199)
- Upper limb phocomelia (HP:0009813)
- Amelia involving the upper limbs (HP:0009812)
- Cardiac conduction abnormality (HP:0031546)
- Common atrium (HP:0011565)
- Unroofed coronary sinus (HP:0031297)
- Patent ductus arteriosus (HP:0001643)

Candidate diseases:
1. id=OMIM:142900 | name=Holt-Oram syndrome | retrieval_score=0.782957 | retrieval_rank=1 | phenodp_total_similarity=0.782957
  - Abnormal carpal morphology: 95% [OBLIGATORY, PATIENT HAS]
  - Ventricular septal defect: 45% [PATIENT ABSENT]
  - Hypoplasia of the radius: 44% [PATIENT HAS]
  - Cardiac conduction abnormality: 39% [PATIENT ABSENT]
  - Absent thumb: 32% [PATIENT ABSENT]
  - Triphalangeal thumb: 25% [PATIENT ABSENT]
  - Patent ductus arteriosus: 17% [PATIENT ABSENT]
  - Persistent left superior vena cava: 10% [PATIENT HAS]
  - Upper limb phocomelia: 7% [PATIENT ABSENT]
  - Amelia involving the upper limbs: 1% [PATIENT ABSENT]
  (88 more annotations omitted)
2. id=OMIM:127300 | name=Leri-Weill dyschondrosteosis | retrieval_score=0.726631 | retrieval_rank=2 | phenodp_total_similarity=0.726631
  - Abnormal carpal morphology: freq unknown [PATIENT HAS]
  - Hypoplasia of the radius: freq unknown [PATIENT HAS]
  - Multiple exostoses: freq unknown
  - Tibial bowing: freq unknown
  - Fibular hypoplasia: freq unknown
  - Abnormal humerus morphology: freq unknown
  - Disproportionate short-limb short stature: freq unknown
  - High palate: freq unknown
  - Limited elbow movement: freq unknown
  - Dorsal subluxation of ulna: freq unknown
  (15 more annotations omitted)
3. id=OMIM:191440 | name=Ulnar hypoplasia | retrieval_score=0.690225 | retrieval_rank=3 | phenodp_total_similarity=0.690225
  - Hypoplasia of the radius: freq unknown [PATIENT HAS]
  - Hypoplasia of the ulna: freq unknown
  - Ulnar deviation of the hand: freq unknown
  - Distal ulnar hypoplasia: freq unknown
  - Mesomelic arm shortening: freq unknown
  - Radial bowing: freq unknown
```

### Raw Output
```text
Holt-Oram syndrome (rank-1) has no obligatory features listed as absent in this patient. Both Leri-Weill dyschondrosteosis and Ulnar hypoplasia cover the radius hypoplasia, but Holt-Oram syndrome best explains the combination of radius hypoplasia, abnormal carpal morphology, and persistent left superior vena cava. Therefore, I will maintain the original ranking.

```json
{
  "selected_candidate": {"id": "OMIM:142900", "name": "Holt-Oram syndrome"},
  "ranking": [
    {"rank": 1, "id": "OMIM:142900", "name": "Holt-Oram syndrome"},
    {"rank": 2, "id": "OMIM:127300", "name": "Leri-Weill dyschondrosteosis"},
    {"rank": 3, "id": "OMIM:191440", "name": "Ulnar hypoplasia"}
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
      "id": "OMIM:127300",
      "name": "Leri-Weill dyschondrosteosis",
      "source": "model"
    },
    {
      "rank": 3,
      "id": "OMIM:191440",
      "name": "Ulnar hypoplasia",
      "source": "model"
    }
  ],
  "parse_mode": "json_object"
}
```

## PMID_10077612_FamilyAIV-14

Truth IDs: `OMIM:142900`

### Prompt
```text
You are a rare disease expert reranking a short list of candidate diagnoses for a single patient.
The candidates were retrieved by a phenotype-similarity model. Your job is to rerank them using clinical reasoning.
Choose only from the candidate list provided below.

## Core principle
The retrieval model is well-calibrated. Its rank-1 candidate is correct more than half the time.
Each candidate below includes HPO phenotype annotations with observed frequencies from medical literature.
Use these frequencies — not your own guesses — to judge which features are obligatory (>=90%) vs variable.

## The two valid reasons to change rank-1
A. EXCLUSION: A phenotype annotated at >=90% frequency for rank-1 is explicitly listed as ABSENT (negative phenotype) in this patient.
   Only features tagged [OBLIGATORY, PATIENT ABSENT] in the annotations qualify for exclusion.
   If the annotations show a feature at <90%, it is NOT grounds for exclusion even if absent.
   CRITICAL: A disease having obligatory features that the patient simply did NOT REPORT is NOT evidence against it.
   Patients rarely report all their features. Only features explicitly listed as ABSENT (negative phenotypes) count.
B. COVERAGE GAP: Rank-1 fails to explain at least one key positive phenotype or organ system present in this patient,
   AND a challenger explains that gap, AND the challenger covers at least as many of the other phenotypes as rank-1.
   Use the annotations to verify coverage: a disease 'explains' a phenotype only if it is annotated for that disease.
   Compare how many of the patient's positive phenotypes are annotated for each candidate.
   IMPORTANT: The fact that a challenger has more total annotations or more obligatory features does NOT mean it is a better match.
   Focus ONLY on the patient's actual phenotypes — not on unreported disease features.
   The challenger must be a candidate from the list below — do not reason about diagnoses outside the list.
If neither A nor B is clearly met, keep rank-1 at position 1.

## Additional rules
- Use the frequency annotations to determine obligatory features. Do NOT override annotated frequencies with your own assumptions.
- Features with frequency <90% are variable and CANNOT be used for exclusion, even if they seem important.
- CRITICAL: Do NOT penalize rank-1 for having obligatory features the patient did not report. Unreported ≠ absent.
  Only features explicitly listed in the 'Negative phenotypes' section are confirmed absent.
- When in doubt, keep rank-1. The retrieval model's ranking is strong evidence.
- Multi-system coherence wins over single-organ specificity. A disease explaining cardiac + limb findings together beats one explaining only the limb findings more precisely.
- For related disease families, numbered subtypes, and broad-vs-narrow syndrome names: treat them as distinct diseases. Require explicit discriminating findings to switch between them.
- Do not switch based on disease-name wording, lexical overlap with one phenotype, or apparent subtype specificity.
- Copy the exact candidate ID and exact candidate name from the list. Do not invent IDs or names.

## Required output
First write a brief clinical reasoning note (2-3 sentences) stating:
  (1) whether rank-1 has any OBLIGATORY (>=90%) annotated feature that is absent in this patient,
  (2) which candidate's annotations best match the patient's positive phenotypes,
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
- Ventricular septal defect (HP:0001629)
- Abnormal carpal morphology (HP:0001191)
- Cardiac conduction abnormality (HP:0031546)
Negative phenotypes (explicitly absent):
- Absent thumb (HP:0009777)
- Triphalangeal thumb (HP:0001199)
- Hypoplasia of the radius (HP:0002984)
- Upper limb phocomelia (HP:0009813)
- Amelia involving the upper limbs (HP:0009812)
- Persistent left superior vena cava (HP:0005301)
- Common atrium (HP:0011565)
- Unroofed coronary sinus (HP:0031297)
- Patent ductus arteriosus (HP:0001643)

Candidate diseases:
1. id=OMIM:142900 | name=Holt-Oram syndrome | retrieval_score=0.748807 | retrieval_rank=1 | phenodp_total_similarity=0.748807
  - Abnormal carpal morphology: 95% [OBLIGATORY, PATIENT HAS]
  - Ventricular septal defect: 45% [PATIENT HAS]
  - Hypoplasia of the radius: 44% [PATIENT ABSENT]
  - Cardiac conduction abnormality: 39% [PATIENT HAS]
  - Absent thumb: 32% [PATIENT ABSENT]
  - Triphalangeal thumb: 25% [PATIENT ABSENT]
  - Patent ductus arteriosus: 17% [PATIENT ABSENT]
  - Persistent left superior vena cava: 10% [PATIENT ABSENT]
  - Upper limb phocomelia: 7% [PATIENT ABSENT]
  - Amelia involving the upper limbs: 1% [PATIENT ABSENT]
  (88 more annotations omitted)
2. id=OMIM:122850 | name=Cranioacrofacial syndrome | retrieval_score=0.665233 | retrieval_rank=2 | phenodp_total_similarity=0.665233
  - Ventricular septal defect: freq unknown [PATIENT HAS]
  - Narrow face: freq unknown
  - Pulmonic stenosis: freq unknown
  - Abnormal hand morphology: freq unknown
  - Dupuytren contracture: freq unknown
3. id=OMIM:617063 | name=Meier-Gorlin syndrome 7 | retrieval_score=0.663182 | retrieval_rank=3 | phenodp_total_similarity=0.663182
  - Ventricular septal defect: 20% [PATIENT HAS]
  - Thin eyebrow: 100% [OBLIGATORY]
  - Craniosynostosis: 93% [OBLIGATORY]
  - Progressive microcephaly: 92% [OBLIGATORY]
  - Microtia: 87%
  - Short stature: 77%
  - Decreased body weight: 75%
  - Aplasia/Hypoplasia of the patella: 73%
  - Hypospadias: 29%
  - Anteriorly placed anus: 27%
  (40 more annotations omitted)
```

### Raw Output
```text
Holt-Oram syndrome (rank-1) has no obligatory features listed as absent in this patient. Cranioacrofacial syndrome (rank-2) and Meier-Gorlin syndrome 7 (rank-3) do not explain the carpal morphology as well as Holt-Oram syndrome. Therefore, I will keep the original ranking.

```json
{
  "selected_candidate": {"id": "OMIM:142900", "name": "Holt-Oram syndrome"},
  "ranking": [
    {"rank": 1, "id": "OMIM:142900", "name": "Holt-Oram syndrome"},
    {"rank": 2, "id": "OMIM:122850", "name": "Cranioacrofacial syndrome"},
    {"rank": 3, "id": "OMIM:617063", "name": "Meier-Gorlin syndrome 7"}
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
      "id": "OMIM:122850",
      "name": "Cranioacrofacial syndrome",
      "source": "model"
    },
    {
      "rank": 3,
      "id": "OMIM:617063",
      "name": "Meier-Gorlin syndrome 7",
      "source": "model"
    }
  ],
  "parse_mode": "json_object"
}
```

## PMID_10077612_FamilyAIV-20

Truth IDs: `OMIM:142900`

### Prompt
```text
You are a rare disease expert reranking a short list of candidate diagnoses for a single patient.
The candidates were retrieved by a phenotype-similarity model. Your job is to rerank them using clinical reasoning.
Choose only from the candidate list provided below.

## Core principle
The retrieval model is well-calibrated. Its rank-1 candidate is correct more than half the time.
Each candidate below includes HPO phenotype annotations with observed frequencies from medical literature.
Use these frequencies — not your own guesses — to judge which features are obligatory (>=90%) vs variable.

## The two valid reasons to change rank-1
A. EXCLUSION: A phenotype annotated at >=90% frequency for rank-1 is explicitly listed as ABSENT (negative phenotype) in this patient.
   Only features tagged [OBLIGATORY, PATIENT ABSENT] in the annotations qualify for exclusion.
   If the annotations show a feature at <90%, it is NOT grounds for exclusion even if absent.
   CRITICAL: A disease having obligatory features that the patient simply did NOT REPORT is NOT evidence against it.
   Patients rarely report all their features. Only features explicitly listed as ABSENT (negative phenotypes) count.
B. COVERAGE GAP: Rank-1 fails to explain at least one key positive phenotype or organ system present in this patient,
   AND a challenger explains that gap, AND the challenger covers at least as many of the other phenotypes as rank-1.
   Use the annotations to verify coverage: a disease 'explains' a phenotype only if it is annotated for that disease.
   Compare how many of the patient's positive phenotypes are annotated for each candidate.
   IMPORTANT: The fact that a challenger has more total annotations or more obligatory features does NOT mean it is a better match.
   Focus ONLY on the patient's actual phenotypes — not on unreported disease features.
   The challenger must be a candidate from the list below — do not reason about diagnoses outside the list.
If neither A nor B is clearly met, keep rank-1 at position 1.

## Additional rules
- Use the frequency annotations to determine obligatory features. Do NOT override annotated frequencies with your own assumptions.
- Features with frequency <90% are variable and CANNOT be used for exclusion, even if they seem important.
- CRITICAL: Do NOT penalize rank-1 for having obligatory features the patient did not report. Unreported ≠ absent.
  Only features explicitly listed in the 'Negative phenotypes' section are confirmed absent.
- When in doubt, keep rank-1. The retrieval model's ranking is strong evidence.
- Multi-system coherence wins over single-organ specificity. A disease explaining cardiac + limb findings together beats one explaining only the limb findings more precisely.
- For related disease families, numbered subtypes, and broad-vs-narrow syndrome names: treat them as distinct diseases. Require explicit discriminating findings to switch between them.
- Do not switch based on disease-name wording, lexical overlap with one phenotype, or apparent subtype specificity.
- Copy the exact candidate ID and exact candidate name from the list. Do not invent IDs or names.

## Required output
First write a brief clinical reasoning note (2-3 sentences) stating:
  (1) whether rank-1 has any OBLIGATORY (>=90%) annotated feature that is absent in this patient,
  (2) which candidate's annotations best match the patient's positive phenotypes,
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
- Atrial septal defect (HP:0001631)
- Ventricular septal defect (HP:0001629)
- Triphalangeal thumb (HP:0001199)
- Hypoplasia of the radius (HP:0002984)
- Abnormal carpal morphology (HP:0001191)
- Cardiac conduction abnormality (HP:0031546)
Negative phenotypes (explicitly absent):
- Absent thumb (HP:0009777)
- Upper limb phocomelia (HP:0009813)
- Amelia involving the upper limbs (HP:0009812)
- Persistent left superior vena cava (HP:0005301)
- Common atrium (HP:0011565)
- Unroofed coronary sinus (HP:0031297)
- Patent ductus arteriosus (HP:0001643)

Candidate diseases:
1. id=OMIM:142900 | name=Holt-Oram syndrome | retrieval_score=0.734865 | retrieval_rank=1 | phenodp_total_similarity=0.734865
  - Atrial septal defect: 96% [OBLIGATORY, PATIENT HAS]
  - Abnormal carpal morphology: 95% [OBLIGATORY, PATIENT HAS]
  - Ventricular septal defect: 45% [PATIENT HAS]
  - Hypoplasia of the radius: 44% [PATIENT HAS]
  - Cardiac conduction abnormality: 39% [PATIENT HAS]
  - Absent thumb: 32% [PATIENT ABSENT]
  - Triphalangeal thumb: 25% [PATIENT HAS]
  - Patent ductus arteriosus: 17% [PATIENT ABSENT]
  - Persistent left superior vena cava: 10% [PATIENT ABSENT]
  - Upper limb phocomelia: 7% [PATIENT ABSENT]
  (88 more annotations omitted)
2. id=OMIM:607323 | name=Duane-Radial ray syndrome | retrieval_score=0.653975 | retrieval_rank=2 | phenodp_total_similarity=0.653975
  - Hypoplasia of the radius: 100% [OBLIGATORY, PATIENT HAS]
  - Absent thumb: freq unknown [PATIENT ABSENT]
  - Triphalangeal thumb: freq unknown [PATIENT HAS]
  - Ventricular septal defect: freq unknown [PATIENT HAS]
  - Atrial septal defect: freq unknown [PATIENT HAS]
  - Shoulder dislocation: 100% [OBLIGATORY]
  - Hypoplasia of the ulna: 100% [OBLIGATORY]
  - Microphthalmia: 95% [OBLIGATORY]
  - Duane anomaly: 92% [OBLIGATORY]
  - Small thenar eminence: 90% [OBLIGATORY]
  (43 more annotations omitted)
3. id=OMIM:192350 | name=Vater associationvacterl association, included | retrieval_score=0.650016 | retrieval_rank=3 | phenodp_total_similarity=0.650016
  - Triphalangeal thumb: freq unknown [PATIENT HAS]
  - Ventricular septal defect: freq unknown [PATIENT HAS]
  - Patent ductus arteriosus: freq unknown [PATIENT ABSENT]
  - Hypoplasia of the radius: freq unknown [PATIENT HAS]
  - Anal atresia: freq unknown
  - Tethered cord: freq unknown
  - Single umbilical artery: freq unknown
  - Ectopic kidney: freq unknown
  - Occipital encephalocele: freq unknown
  - Failure to thrive: freq unknown
  (27 more annotations omitted)
```

### Raw Output
```text
Holt-Oram syndrome (rank-1) has one obligatory feature (atrial septal defect) that is present in the patient. Duane-Radial ray syndrome explains the hypoplasia of the radius and absent thumb better, but it has several obligatory features not seen in the patient (shoulder dislocation, hypoplasia of the ulna, microphthalmia, Duane anomaly, small thenar eminence). Therefore, I will keep Holt-Oram syndrome as rank-1.

```json
{
  "selected_candidate": {"id": "OMIM:142900", "name": "Holt-Oram syndrome"},
  "ranking": [
    {"rank": 1, "id": "OMIM:142900", "name": "Holt-Oram syndrome"},
    {"rank": 2, "id": "OMIM:607323", "name": "Duane-Radial ray syndrome"},
    {"rank": 3, "id": "OMIM:192350", "name": "Vater associationvacterl association, included"}
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
      "id": "OMIM:607323",
      "name": "Duane-Radial ray syndrome",
      "source": "model"
    },
    {
      "rank": 3,
      "id": "OMIM:192350",
      "name": "Vater associationvacterl association, included",
      "source": "model"
    }
  ],
  "parse_mode": "json_object"
}
```

