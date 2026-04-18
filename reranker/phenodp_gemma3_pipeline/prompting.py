from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set

from .hpo_annotations import HPOAnnotationStore
from .models import DiseaseCandidate, PatientCase


@dataclass
class PromptOptions:
    max_phenotypes: int = 30
    max_negative_phenotypes: int = 20
    max_genes: int = 20
    include_negative_phenotypes: bool = True
    include_genes: bool = True
    include_demographics: bool = True
    output_top_k: int = 10
    candidate_count_in_prompt: int = 10
    include_hpo_annotations: bool = False
    max_annotations_per_candidate: int = 10
    prompt_version: str = "v3"  # "v3", "v4", "v5", "v6", "v7", "pp2prompt", or "pp2prompt_v2"
    pp2prompt_dir: Optional[str] = None  # required when prompt_version == "pp2prompt"


def _normalize_id(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _build_pp2prompt_index(prompts_dir: str) -> Dict[str, Path]:
    """Build normalized-id → Path lookup for all *_en-prompt.txt files."""
    index: Dict[str, Path] = {}
    for f in Path(prompts_dir).iterdir():
        if f.name.endswith("_en-prompt.txt"):
            stem = f.name[: -len("_en-prompt.txt")]
            index[_normalize_id(stem)] = f
    return index


_PP2PROMPT_INDEX_CACHE: Dict[str, Dict[str, Path]] = {}


def _get_pp2prompt_file(patient_id: str, prompts_dir: str) -> Optional[Path]:
    if prompts_dir not in _PP2PROMPT_INDEX_CACHE:
        _PP2PROMPT_INDEX_CACHE[prompts_dir] = _build_pp2prompt_index(prompts_dir)
    return _PP2PROMPT_INDEX_CACHE[prompts_dir].get(_normalize_id(patient_id))


def _format_pairs(ids: List[str], labels: List[str], limit: int) -> List[str]:
    pairs = list(zip(ids, labels))
    return [f"- {label} ({term_id})" for term_id, label in pairs[: max(0, int(limit))]]


def _build_prompt_v4_text(
    case: PatientCase,
    candidates: List[DiseaseCandidate],
    opts: PromptOptions,
    annotation_store: Optional[HPOAnnotationStore] = None,
    hpo_names: Optional[Dict[str, str]] = None,
) -> str:
    """Prompt v4: hard score-gap gate, strict Condition A verification, biological-impossibility B, numbered-subtype rule."""
    prompt_candidates = candidates[: max(0, int(opts.candidate_count_in_prompt))]
    output_top_k = min(int(opts.output_top_k), len(prompt_candidates))
    has_annotations = opts.include_hpo_annotations and annotation_store is not None

    lines: List[str] = []
    lines.append("You are a rare disease expert reranking a short list of candidate diagnoses for a single patient.")
    lines.append("The candidates were retrieved by a phenotype-similarity model. Your job is to rerank them using clinical reasoning.")
    lines.append("Choose only from the candidate list provided below.")
    lines.append("")
    lines.append("## Core principle")
    lines.append("The retrieval model is well-calibrated. Its rank-1 candidate is correct more than half the time.")
    lines.append("Preserve rank-1 unless you find a specific, named clinical reason to change it.")
    lines.append("The cost of incorrectly demoting rank-1 is higher than the cost of missing a promotion.")
    lines.append("When in doubt, keep rank-1.")
    lines.append("")
    lines.append("## Score gap hard gate")
    lines.append("Compute: gap = rank-1 retrieval_score minus rank-2 retrieval_score.")
    lines.append("If gap > 0.05 (LARGE GAP): BOTH Condition A AND Condition B must be clearly met simultaneously to demote rank-1.")
    lines.append("  One condition alone — no matter how compelling — is NOT sufficient when the gap is large.")
    lines.append("If gap <= 0.05 (small gap): either Condition A or Condition B alone is sufficient.")
    lines.append("A large gap is strong probabilistic evidence for rank-1. It takes proportionally more evidence to override it.")
    lines.append("")
    lines.append("## Condition A — EXCLUSION (obligatory absent feature)")
    lines.append("A feature that is OBLIGATORY (present in >90% of cases) for rank-1 is explicitly absent in this patient.")
    lines.append("")
    lines.append("Verification gate — ALL THREE must be true before applying Condition A:")
    lines.append("  1. CONFIRMED ABSENT: The feature must appear in the 'Negative phenotypes (explicitly absent)' list below,")
    lines.append("     OR be a direct clinical parent of a listed negative phenotype.")
    lines.append("     Features simply not listed among positive phenotypes are UNREPORTED, not absent.")
    lines.append("     Unreported ≠ absent. NEVER trigger Condition A on an unreported feature.")
    lines.append("  2. TRULY OBLIGATORY: The feature must be present in >90% of published cases —")
    lines.append("     not hallmark, typical, common, characteristic, or frequently seen. Only >90% penetrance counts.")
    lines.append("  3. NOT NAME-INFERRED: Obligatory status must NOT be inferred from the disease name.")
    lines.append("     Phenotype words in disease names (e.g. 'optic atrophy' in 'Dystonia with optic atrophy and basal ganglia abnormalities',")
    lines.append("     'arachnodactyly' in 'Contractural arachnodactyly', 'cutis laxa' in 'Cutis laxa type ID')")
    lines.append("     are NOT evidence of obligatory penetrance. Disease names are historical labels, not penetrance statistics.")
    lines.append("")
    lines.append("## Condition B — COVERAGE GAP (biological impossibility only)")
    lines.append("Rank-1 is BIOLOGICALLY INCAPABLE of explaining a specific positive phenotype present in this patient")
    lines.append("(i.e., that phenotype is never observed in rank-1 in any published cases),")
    lines.append("AND a challenger candidate specifically explains that phenotype,")
    lines.append("AND the challenger explains at least as many of the patient's other positive phenotypes as rank-1.")
    lines.append("")
    lines.append("Condition B is NOT met by any of the following — these are INVALID reasons to demote rank-1:")
    lines.append("  - A challenger is a broader syndrome that 'explains more organ systems in general'.")
    lines.append("    More features in the disease description does NOT mean a better match for this patient.")
    lines.append("  - A challenger explains the same phenotypes differently or more specifically.")
    lines.append("  - A challenger adds features the patient did NOT explicitly report as positive.")
    lines.append("  - Rank-1 has a narrower or more specific label than the challenger.")
    lines.append("  - The challenger is a well-known syndrome and rank-1 is a rare specific condition.")
    lines.append("The gap must be a phenotype rank-1 CANNOT produce at all — not one it explains less impressively.")
    lines.append("")
    lines.append("## Numbered-subtype rule")
    lines.append("When two or more candidates are numbered subtypes of the same disease family")
    lines.append("(e.g., NBIA 1 vs NBIA 4, Retinitis pigmentosa 11 vs 18, Developmental and epileptic encephalopathy 4 vs 14,")
    lines.append(" Spinocerebellar ataxia 15 vs 49, Loeys-Dietz syndrome 1 vs 3, Noonan syndrome 1 vs 6,")
    lines.append(" Kabuki syndrome 1 vs 2, Bardet-Biedl syndrome 1 vs 4),")
    lines.append("phenotype data alone CANNOT reliably distinguish between them.")
    lines.append("These are genetically heterogeneous but phenotypically overlapping by design.")
    lines.append("If the candidates include numbered subtypes of the same family: keep rank-1 UNCONDITIONALLY")
    lines.append("unless a gene finding in this patient directly matches rank-2 but not rank-1.")
    lines.append("Clinical phenotype reasoning alone is NOT a valid basis for switching between same-family numbered subtypes.")
    lines.append("")
    lines.append("## Additional rules")
    lines.append("- Negative phenotypes exclude a disease ONLY when the absent feature passes ALL THREE checks in the Condition A gate.")
    lines.append("  Variable-penetrance features (50-80% of cases) are NOT grounds for exclusion under any circumstances.")
    lines.append("- Multi-system coherence wins over single-organ specificity.")
    lines.append("  A disease explaining cardiac + limb findings together beats one explaining only the limb findings more precisely.")
    if opts.include_genes:
        lines.append("- Gene evidence is strong supporting evidence when consistent.")
        lines.append("  For same-family numbered subtypes, gene evidence is the ONLY valid basis for switching.")
    lines.append("- Do not switch based on disease-name wording, lexical overlap with one phenotype, or apparent subtype specificity.")
    lines.append("- Copy the exact candidate ID and exact candidate name from the list. Do not invent IDs or names.")
    lines.append("")
    lines.append("## Required output")
    lines.append("First write a brief clinical reasoning note (3-5 sentences) stating:")
    lines.append("  (1) the score gap between rank-1 and rank-2, and whether it is LARGE (>0.05) or small,")
    lines.append("  (2) whether Condition A is met — run the verification gate explicitly,")
    lines.append("  (3) whether Condition B is met — name the specific phenotype rank-1 cannot produce,")
    lines.append("  (4) whether the numbered-subtype rule applies,")
    lines.append("  (5) your final decision.")
    lines.append("Then output the JSON block. Do not add any other text.")
    lines.append("")
    lines.append("{")
    lines.append('  "selected_candidate": {"id": "...", "name": "..."},')
    lines.append('  "ranking": [')
    lines.append('    {"rank": 1, "id": "...", "name": "..."},')
    lines.append('    {"rank": 2, "id": "...", "name": "..."}')
    lines.append("  ]")
    lines.append("}")
    lines.append(f'Return exactly {output_top_k} ranking items ordered from best to worst.')
    lines.append("")

    if case.description:
        lines.append(f"Patient description: {case.description}")
    if opts.include_demographics:
        if case.sex:
            lines.append(f"Sex: {case.sex}")
        if case.age:
            lines.append(f"Age: {case.age}")

    positive_lines = _format_pairs(case.phenotype_ids, case.phenotype_labels, opts.max_phenotypes)
    lines.append("Positive phenotypes:")
    lines.extend(positive_lines or ["- None provided"])

    if opts.include_negative_phenotypes:
        negative_lines = _format_pairs(case.neg_phenotype_ids, case.neg_phenotype_labels, opts.max_negative_phenotypes)
        lines.append("Negative phenotypes (explicitly absent):")
        lines.extend(negative_lines or ["- None provided"])

    if opts.include_genes:
        gene_list = case.genes[: max(0, int(opts.max_genes))]
        lines.append("Gene findings:")
        lines.append(f"- {', '.join(gene_list)}" if gene_list else "- None provided")

    patient_pos_ids: Set[str] = set(case.phenotype_ids)
    patient_neg_ids: Set[str] = set(case.neg_phenotype_ids)

    lines.append("")
    lines.append("Candidate diseases:")
    for index, candidate in enumerate(prompt_candidates, start=1):
        score_bits = [f"retrieval_score={candidate.score:.6f}", f"retrieval_rank={candidate.retrieval_rank}"]
        if candidate.metadata.get("raw_total_similarity") is not None:
            score_bits.append(f"phenodp_total_similarity={float(candidate.metadata['raw_total_similarity']):.6f}")
        if candidate.metadata.get("gene_overlap"):
            score_bits.append(f"gene_overlap={candidate.metadata['gene_overlap']}")
        lines.append(
            f"{index}. id={candidate.disease_id} | name={candidate.disease_name} | "
            + " | ".join(score_bits)
        )
        if has_annotations and annotation_store is not None:
            ann_lines = annotation_store.format_for_prompt(
                disease_id=candidate.disease_id,
                hpo_names=hpo_names or {},
                patient_pos_hpo_ids=patient_pos_ids,
                patient_neg_hpo_ids=patient_neg_ids,
                max_annotations=opts.max_annotations_per_candidate,
            )
            lines.extend(ann_lines)

    return "\n".join(lines)


def _build_prompt_v5_text(
    case: PatientCase,
    candidates: List[DiseaseCandidate],
    opts: PromptOptions,
    annotation_store: Optional[HPOAnnotationStore] = None,
    hpo_names: Optional[Dict[str, str]] = None,
) -> str:
    """Prompt v5: v4 + stricter name-inference (4th check), incomplete-record caveat, absolute protection for gap>0.15."""
    prompt_candidates = candidates[: max(0, int(opts.candidate_count_in_prompt))]
    output_top_k = min(int(opts.output_top_k), len(prompt_candidates))
    has_annotations = opts.include_hpo_annotations and annotation_store is not None

    lines: List[str] = []
    lines.append("You are a rare disease expert reranking a short list of candidate diagnoses for a single patient.")
    lines.append("The candidates were retrieved by a phenotype-similarity model. Your job is to rerank them using clinical reasoning.")
    lines.append("Choose only from the candidate list provided below.")
    lines.append("")
    lines.append("## Core principle")
    lines.append("The retrieval model is well-calibrated. Its rank-1 candidate is correct more than half the time.")
    lines.append("Preserve rank-1 unless you find a specific, named clinical reason to change it.")
    lines.append("The cost of incorrectly demoting rank-1 is higher than the cost of missing a promotion.")
    lines.append("When in doubt, keep rank-1.")
    lines.append("")
    lines.append("## Score gap hard gate")
    lines.append("Compute: gap = rank-1 retrieval_score minus rank-2 retrieval_score.")
    lines.append("If gap > 0.15 (VERY LARGE GAP): keep rank-1 UNCONDITIONALLY.")
    lines.append("  A gap this large means the retrieval model is highly confident. Do NOT demote rank-1 regardless of conditions.")
    lines.append("  The only exception is if rank-1 is biologically impossible for this patient (see Condition B — biological impossibility).")
    lines.append("If gap > 0.05 and <= 0.15 (LARGE GAP): BOTH Condition A AND Condition B must be clearly met simultaneously to demote rank-1.")
    lines.append("  One condition alone is NOT sufficient.")
    lines.append("If gap <= 0.05 (small gap): either Condition A or Condition B alone is sufficient.")
    lines.append("")
    lines.append("## Condition A — EXCLUSION (obligatory absent feature)")
    lines.append("A feature that is OBLIGATORY (present in >90% of cases) for rank-1 is explicitly absent in this patient.")
    lines.append("")
    lines.append("Verification gate — ALL FOUR must be true before applying Condition A:")
    lines.append("  1. CONFIRMED ABSENT: The feature must appear in the 'Negative phenotypes (explicitly absent)' list below,")
    lines.append("     OR be a direct clinical parent of a listed negative phenotype.")
    lines.append("     Features simply not listed among positive phenotypes are UNREPORTED, not absent.")
    lines.append("     Unreported ≠ absent. NEVER trigger Condition A on an unreported feature.")
    lines.append("  2. TRULY OBLIGATORY: The feature must be present in >90% of published cases —")
    lines.append("     not hallmark, typical, common, characteristic, or frequently seen. Only >90% penetrance counts.")
    lines.append("  3. NOT NAME-INFERRED: Obligatory status must NOT be inferred from the disease name.")
    lines.append("     STRICT RULE: If the absent feature's exact term (or a direct synonym) appears as a word")
    lines.append("     in the rank-1 disease name, it IS name-inferred — do not claim otherwise.")
    lines.append("     Examples of name-inferred (all INVALID for Condition A):")
    lines.append("       - 'optic atrophy' absent, disease = 'Dystonia with optic atrophy and basal ganglia abnormalities'")
    lines.append("       - 'macrocephaly' absent, disease = 'Intellectual developmental disorder with autism and macrocephaly'")
    lines.append("       - 'ectopia lentis' absent, disease = 'Ectopia lentis, familial'")
    lines.append("       - 'hip dysplasia' absent, disease = 'Craniometadiaphyseal osteosclerosis with hip dysplasia'")
    lines.append("       - 'neurofibroma' absent, disease = 'Neurofibromatosis type 1'  (neurofibromas are the namesake feature)")
    lines.append("       - 'cutis laxa' absent, disease = 'Cutis laxa type ID'")
    lines.append("     Disease names are historical labels, not penetrance statistics.")
    lines.append("  4. NOT AGE-DEPENDENT OR INCOMPLETELY ASSESSED: Phenopackets are derived from published case reports,")
    lines.append("     which capture positive findings but frequently omit features that:")
    lines.append("       (a) had not yet developed at the time of reporting (age-dependent penetrance), or")
    lines.append("       (b) were not assessed or documented in that particular clinical encounter.")
    lines.append("     If a feature has known age-dependent onset or variable expressivity, its confirmed absence in a single")
    lines.append("     case report does NOT establish that rank-1 is excluded.")
    lines.append("     Examples: neurofibromas in NF1 (develop over decades), cataracts in metabolic disorders,")
    lines.append("     seizures in neurodegenerative diseases, cardiomyopathy in mitochondrial disorders.")
    lines.append("     When in doubt about whether a feature is age-dependent, treat it as potentially age-dependent.")
    lines.append("")
    lines.append("## Condition B — COVERAGE GAP (biological impossibility only)")
    lines.append("Rank-1 is BIOLOGICALLY INCAPABLE of explaining a specific positive phenotype present in this patient")
    lines.append("(i.e., that phenotype is never observed in rank-1 in any published cases),")
    lines.append("AND a challenger candidate specifically explains that phenotype,")
    lines.append("AND the challenger explains at least as many of the patient's other positive phenotypes as rank-1.")
    lines.append("")
    lines.append("Condition B is NOT met by any of the following — these are INVALID reasons to demote rank-1:")
    lines.append("  - A challenger is a broader syndrome that 'explains more organ systems in general'.")
    lines.append("    More features in the disease description does NOT mean a better match for this patient.")
    lines.append("  - A challenger explains the same phenotypes differently or more specifically.")
    lines.append("  - A challenger adds features the patient did NOT explicitly report as positive.")
    lines.append("  - Rank-1 has a narrower or more specific label than the challenger.")
    lines.append("  - The challenger is a well-known syndrome and rank-1 is a rare specific condition.")
    lines.append("The gap must be a phenotype rank-1 CANNOT produce at all — not one it explains less impressively.")
    lines.append("")
    lines.append("## Numbered-subtype rule")
    lines.append("When two or more candidates are numbered subtypes of the same disease family")
    lines.append("(e.g., NBIA 1 vs NBIA 4, Retinitis pigmentosa 11 vs 18, Developmental and epileptic encephalopathy 4 vs 14,")
    lines.append(" Spinocerebellar ataxia 15 vs 49, Loeys-Dietz syndrome 1 vs 3, Noonan syndrome 1 vs 6,")
    lines.append(" Kabuki syndrome 1 vs 2, Bardet-Biedl syndrome 1 vs 4),")
    lines.append("phenotype data alone CANNOT reliably distinguish between them.")
    lines.append("If the candidates include numbered subtypes of the same family: keep rank-1 UNCONDITIONALLY")
    lines.append("unless a gene finding in this patient directly matches rank-2 but not rank-1.")
    lines.append("")
    lines.append("## Additional rules")
    lines.append("- Negative phenotypes exclude a disease ONLY when the absent feature passes ALL FOUR checks in the Condition A gate.")
    lines.append("  Variable-penetrance features (50-80% of cases) are NOT grounds for exclusion under any circumstances.")
    lines.append("- Multi-system coherence wins over single-organ specificity.")
    lines.append("  A disease explaining cardiac + limb findings together beats one explaining only the limb findings more precisely.")
    if opts.include_genes:
        lines.append("- Gene evidence is strong supporting evidence when consistent.")
        lines.append("  For same-family numbered subtypes, gene evidence is the ONLY valid basis for switching.")
    lines.append("- Do not switch based on disease-name wording, lexical overlap with one phenotype, or apparent subtype specificity.")
    lines.append("- Copy the exact candidate ID and exact candidate name from the list. Do not invent IDs or names.")
    lines.append("")
    lines.append("## Required output")
    lines.append("First write a brief clinical reasoning note (3-5 sentences) stating:")
    lines.append("  (1) the score gap between rank-1 and rank-2, and whether it is VERY LARGE (>0.15), LARGE (>0.05), or small,")
    lines.append("  (2) whether Condition A is met — run ALL FOUR verification checks explicitly,")
    lines.append("  (3) whether Condition B is met — name the specific phenotype rank-1 cannot produce,")
    lines.append("  (4) whether the numbered-subtype rule applies,")
    lines.append("  (5) your final decision.")
    lines.append("Then output the JSON block. Do not add any other text.")
    lines.append("")
    lines.append("{")
    lines.append('  "selected_candidate": {"id": "...", "name": "..."},')
    lines.append('  "ranking": [')
    lines.append('    {"rank": 1, "id": "...", "name": "..."},')
    lines.append('    {"rank": 2, "id": "...", "name": "..."}')
    lines.append("  ]")
    lines.append("}")
    lines.append(f'Return exactly {output_top_k} ranking items ordered from best to worst.')
    lines.append("")

    if case.description:
        lines.append(f"Patient description: {case.description}")
    if opts.include_demographics:
        if case.sex:
            lines.append(f"Sex: {case.sex}")
        if case.age:
            lines.append(f"Age: {case.age}")

    positive_lines = _format_pairs(case.phenotype_ids, case.phenotype_labels, opts.max_phenotypes)
    lines.append("Positive phenotypes:")
    lines.extend(positive_lines or ["- None provided"])

    if opts.include_negative_phenotypes:
        negative_lines = _format_pairs(case.neg_phenotype_ids, case.neg_phenotype_labels, opts.max_negative_phenotypes)
        lines.append("Negative phenotypes (explicitly absent):")
        lines.extend(negative_lines or ["- None provided"])

    if opts.include_genes:
        gene_list = case.genes[: max(0, int(opts.max_genes))]
        lines.append("Gene findings:")
        lines.append(f"- {', '.join(gene_list)}" if gene_list else "- None provided")

    patient_pos_ids: Set[str] = set(case.phenotype_ids)
    patient_neg_ids: Set[str] = set(case.neg_phenotype_ids)

    lines.append("")
    lines.append("Candidate diseases:")
    for index, candidate in enumerate(prompt_candidates, start=1):
        score_bits = [f"retrieval_score={candidate.score:.6f}", f"retrieval_rank={candidate.retrieval_rank}"]
        if candidate.metadata.get("raw_total_similarity") is not None:
            score_bits.append(f"phenodp_total_similarity={float(candidate.metadata['raw_total_similarity']):.6f}")
        if candidate.metadata.get("gene_overlap"):
            score_bits.append(f"gene_overlap={candidate.metadata['gene_overlap']}")
        lines.append(
            f"{index}. id={candidate.disease_id} | name={candidate.disease_name} | "
            + " | ".join(score_bits)
        )
        if has_annotations and annotation_store is not None:
            ann_lines = annotation_store.format_for_prompt(
                disease_id=candidate.disease_id,
                hpo_names=hpo_names or {},
                patient_pos_hpo_ids=patient_pos_ids,
                patient_neg_hpo_ids=patient_neg_ids,
                max_annotations=opts.max_annotations_per_candidate,
            )
            lines.extend(ann_lines)

    return "\n".join(lines)


def _build_prompt_v6_text(
    case: PatientCase,
    candidates: List[DiseaseCandidate],
    opts: PromptOptions,
    annotation_store: Optional[HPOAnnotationStore] = None,
    hpo_names: Optional[Dict[str, str]] = None,
) -> str:
    """Prompt v6: v5 + same-gene spectrum rule, tighter gap gate (<=0.03 small), extra name-inference examples, demotion self-check."""
    prompt_candidates = candidates[: max(0, int(opts.candidate_count_in_prompt))]
    output_top_k = min(int(opts.output_top_k), len(prompt_candidates))
    has_annotations = opts.include_hpo_annotations and annotation_store is not None

    lines: List[str] = []
    lines.append("You are a rare disease expert reranking a short list of candidate diagnoses for a single patient.")
    lines.append("The candidates were retrieved by a phenotype-similarity model. Your job is to rerank them using clinical reasoning.")
    lines.append("Choose only from the candidate list provided below.")
    lines.append("")
    lines.append("## Core principle")
    lines.append("The retrieval model is well-calibrated. Its rank-1 candidate is correct more than half the time.")
    lines.append("Preserve rank-1 unless you find a specific, named clinical reason to change it.")
    lines.append("The cost of incorrectly demoting rank-1 is higher than the cost of missing a promotion.")
    lines.append("When in doubt, keep rank-1.")
    lines.append("")
    lines.append("## Score gap hard gate")
    lines.append("Compute: gap = rank-1 retrieval_score minus rank-2 retrieval_score.")
    lines.append("If gap > 0.15 (VERY LARGE GAP): keep rank-1 UNCONDITIONALLY.")
    lines.append("  A gap this large means the retrieval model is highly confident. Do NOT demote rank-1 regardless of conditions.")
    lines.append("  The only exception is if rank-1 is biologically impossible for this patient (see Condition B — biological impossibility).")
    lines.append("If gap > 0.03 and <= 0.15 (LARGE GAP): BOTH Condition A AND Condition B must be clearly met simultaneously to demote rank-1.")
    lines.append("  One condition alone is NOT sufficient.")
    lines.append("If gap <= 0.03 (small gap): either Condition A or Condition B alone is sufficient.")
    lines.append("Note: most gaps between 0.03 and 0.15 should be treated as LARGE. Only gaps of 0.03 or smaller permit single-condition demotion.")
    lines.append("")
    lines.append("## Same-gene spectrum rule")
    lines.append("When rank-1 and the proposed replacement challenger are caused by variants in the SAME gene,")
    lines.append("they represent different presentations of the same molecular disease — phenotype variation alone cannot distinguish them.")
    lines.append("Keep rank-1 UNCONDITIONALLY in this case, even if Condition A or Condition B appears met.")
    lines.append("Examples of same-gene families where this rule applies:")
    lines.append("  - NF1 gene: Neurofibromatosis type 1, NF-Noonan syndrome, Watson syndrome")
    lines.append("  - TSC1/TSC2 genes: Tuberous sclerosis complex subtypes")
    lines.append("  - COL6A1/COL6A2/COL6A3 genes: Bethlem myopathy and Ullrich congenital muscular dystrophy")
    lines.append("  - LRRK2, SNCA, PINK1, PARK2 and other Parkinson disease genes: Parkinson disease subtypes")
    lines.append("  - Any pair where gene_overlap is listed for both rank-1 and challenger in the candidate list below")
    lines.append("To apply this rule: if both rank-1 and the proposed challenger have the same gene in their gene_overlap field,")
    lines.append("or if you know they share the same causal gene from medical knowledge, keep rank-1.")
    lines.append("")
    lines.append("## Condition A — EXCLUSION (obligatory absent feature)")
    lines.append("A feature that is OBLIGATORY (present in >90% of cases) for rank-1 is explicitly absent in this patient.")
    lines.append("")
    lines.append("Verification gate — ALL FOUR must be true before applying Condition A:")
    lines.append("  1. CONFIRMED ABSENT: The feature must appear in the 'Negative phenotypes (explicitly absent)' list below,")
    lines.append("     OR be a direct clinical parent of a listed negative phenotype.")
    lines.append("     Features simply not listed among positive phenotypes are UNREPORTED, not absent.")
    lines.append("     Unreported ≠ absent. NEVER trigger Condition A on an unreported feature.")
    lines.append("  2. TRULY OBLIGATORY: The feature must be present in >90% of published cases —")
    lines.append("     not hallmark, typical, common, characteristic, or frequently seen. Only >90% penetrance counts.")
    lines.append("  3. NOT NAME-INFERRED: Obligatory status must NOT be inferred from the disease name.")
    lines.append("     STRICT RULE: If the absent feature's exact term (or a direct synonym) appears as a word")
    lines.append("     in the rank-1 disease name, it IS name-inferred — do not claim otherwise.")
    lines.append("     Examples of name-inferred (all INVALID for Condition A):")
    lines.append("       - 'optic atrophy' absent, disease = 'Dystonia with optic atrophy and basal ganglia abnormalities'")
    lines.append("       - 'macrocephaly' absent, disease = 'Intellectual developmental disorder with autism and macrocephaly'")
    lines.append("       - 'ectopia lentis' absent, disease = 'Ectopia lentis, familial'")
    lines.append("       - 'hip dysplasia' absent, disease = 'Craniometadiaphyseal osteosclerosis with hip dysplasia'")
    lines.append("       - 'neurofibroma' absent, disease = 'Neurofibromatosis type 1'  (neurofibromas are the namesake feature)")
    lines.append("       - 'cutis laxa' absent, disease = 'Cutis laxa type ID'")
    lines.append("       - 'parkinsonism' or 'tremor' absent, disease = 'Parkinson disease' or any 'Parkinson disease N' subtype")
    lines.append("     Disease names are historical labels, not penetrance statistics.")
    lines.append("  4. NOT AGE-DEPENDENT OR INCOMPLETELY ASSESSED: Phenopackets are derived from published case reports,")
    lines.append("     which capture positive findings but frequently omit features that:")
    lines.append("       (a) had not yet developed at the time of reporting (age-dependent penetrance), or")
    lines.append("       (b) were not assessed or documented in that particular clinical encounter.")
    lines.append("     If a feature has known age-dependent onset or variable expressivity, its confirmed absence in a single")
    lines.append("     case report does NOT establish that rank-1 is excluded.")
    lines.append("     Examples: neurofibromas in NF1 (develop over decades), cataracts in metabolic disorders,")
    lines.append("     seizures in neurodegenerative diseases, cardiomyopathy in mitochondrial disorders.")
    lines.append("     When in doubt about whether a feature is age-dependent, treat it as potentially age-dependent.")
    lines.append("")
    lines.append("## Condition B — COVERAGE GAP (biological impossibility only)")
    lines.append("Rank-1 is BIOLOGICALLY INCAPABLE of explaining a specific positive phenotype present in this patient")
    lines.append("(i.e., that phenotype is never observed in rank-1 in any published cases),")
    lines.append("AND a challenger candidate specifically explains that phenotype,")
    lines.append("AND the challenger explains at least as many of the patient's other positive phenotypes as rank-1.")
    lines.append("")
    lines.append("Condition B is NOT met by any of the following — these are INVALID reasons to demote rank-1:")
    lines.append("  - A challenger is a broader syndrome that 'explains more organ systems in general'.")
    lines.append("    More features in the disease description does NOT mean a better match for this patient.")
    lines.append("  - A challenger explains the same phenotypes differently or more specifically.")
    lines.append("  - A challenger adds features the patient did NOT explicitly report as positive.")
    lines.append("  - Rank-1 has a narrower or more specific label than the challenger.")
    lines.append("  - The challenger is a well-known syndrome and rank-1 is a rare specific condition.")
    lines.append("The gap must be a phenotype rank-1 CANNOT produce at all — not one it explains less impressively.")
    lines.append("")
    lines.append("## Numbered-subtype rule")
    lines.append("When two or more candidates are numbered subtypes of the same disease family")
    lines.append("(e.g., NBIA 1 vs NBIA 4, Retinitis pigmentosa 11 vs 18, Developmental and epileptic encephalopathy 4 vs 14,")
    lines.append(" Spinocerebellar ataxia 15 vs 49, Loeys-Dietz syndrome 1 vs 3, Noonan syndrome 1 vs 6,")
    lines.append(" Kabuki syndrome 1 vs 2, Bardet-Biedl syndrome 1 vs 4),")
    lines.append("phenotype data alone CANNOT reliably distinguish between them.")
    lines.append("If the candidates include numbered subtypes of the same family: keep rank-1 UNCONDITIONALLY")
    lines.append("unless a gene finding in this patient directly matches rank-2 but not rank-1.")
    lines.append("")
    lines.append("## Additional rules")
    lines.append("- Negative phenotypes exclude a disease ONLY when the absent feature passes ALL FOUR checks in the Condition A gate.")
    lines.append("  Variable-penetrance features (50-80% of cases) are NOT grounds for exclusion under any circumstances.")
    lines.append("- Multi-system coherence wins over single-organ specificity.")
    lines.append("  A disease explaining cardiac + limb findings together beats one explaining only the limb findings more precisely.")
    if opts.include_genes:
        lines.append("- Gene evidence is strong supporting evidence when consistent.")
        lines.append("  For same-family numbered subtypes, gene evidence is the ONLY valid basis for switching.")
    lines.append("- Do not switch based on disease-name wording, lexical overlap with one phenotype, or apparent subtype specificity.")
    lines.append("- Copy the exact candidate ID and exact candidate name from the list. Do not invent IDs or names.")
    lines.append("")
    lines.append("## Required output")
    lines.append("First write a brief clinical reasoning note (3-5 sentences) stating:")
    lines.append("  (1) the score gap between rank-1 and rank-2, and whether it is VERY LARGE (>0.15), LARGE (>0.03), or small (<=0.03),")
    lines.append("  (2) whether the same-gene spectrum rule applies (check gene_overlap fields for rank-1 and challenger),")
    lines.append("  (3) whether Condition A is met — run ALL FOUR verification checks explicitly,")
    lines.append("  (4) whether Condition B is met — name the specific phenotype rank-1 cannot produce,")
    lines.append("  (5) whether the numbered-subtype rule applies,")
    lines.append("  (6) DEMOTION SELF-CHECK (only if you are about to demote rank-1): explicitly state —")
    lines.append("       - which gap tier applies and whether it permits demotion,")
    lines.append("       - whether the same-gene rule blocks the demotion,")
    lines.append("       - whether the absent feature passes all 4 Condition A checks (especially name-inference check),")
    lines.append("       - whether the biological impossibility in Condition B is truly 'never observed' (not just 'rarely observed'),")
    lines.append("  (7) your final decision.")
    lines.append("Then output the JSON block. Do not add any other text.")
    lines.append("")
    lines.append("{")
    lines.append('  "selected_candidate": {"id": "...", "name": "..."},')
    lines.append('  "ranking": [')
    lines.append('    {"rank": 1, "id": "...", "name": "..."},')
    lines.append('    {"rank": 2, "id": "...", "name": "..."}')
    lines.append("  ]")
    lines.append("}")
    lines.append(f'Return exactly {output_top_k} ranking items ordered from best to worst.')
    lines.append("")

    if case.description:
        lines.append(f"Patient description: {case.description}")
    if opts.include_demographics:
        if case.sex:
            lines.append(f"Sex: {case.sex}")
        if case.age:
            lines.append(f"Age: {case.age}")

    positive_lines = _format_pairs(case.phenotype_ids, case.phenotype_labels, opts.max_phenotypes)
    lines.append("Positive phenotypes:")
    lines.extend(positive_lines or ["- None provided"])

    if opts.include_negative_phenotypes:
        negative_lines = _format_pairs(case.neg_phenotype_ids, case.neg_phenotype_labels, opts.max_negative_phenotypes)
        lines.append("Negative phenotypes (explicitly absent):")
        lines.extend(negative_lines or ["- None provided"])

    if opts.include_genes:
        gene_list = case.genes[: max(0, int(opts.max_genes))]
        lines.append("Gene findings:")
        lines.append(f"- {', '.join(gene_list)}" if gene_list else "- None provided")

    patient_pos_ids: Set[str] = set(case.phenotype_ids)
    patient_neg_ids: Set[str] = set(case.neg_phenotype_ids)

    lines.append("")
    lines.append("Candidate diseases:")
    for index, candidate in enumerate(prompt_candidates, start=1):
        score_bits = [f"retrieval_score={candidate.score:.6f}", f"retrieval_rank={candidate.retrieval_rank}"]
        if candidate.metadata.get("raw_total_similarity") is not None:
            score_bits.append(f"phenodp_total_similarity={float(candidate.metadata['raw_total_similarity']):.6f}")
        if candidate.metadata.get("gene_overlap"):
            score_bits.append(f"gene_overlap={candidate.metadata['gene_overlap']}")
        lines.append(
            f"{index}. id={candidate.disease_id} | name={candidate.disease_name} | "
            + " | ".join(score_bits)
        )
        if has_annotations and annotation_store is not None:
            ann_lines = annotation_store.format_for_prompt(
                disease_id=candidate.disease_id,
                hpo_names=hpo_names or {},
                patient_pos_hpo_ids=patient_pos_ids,
                patient_neg_hpo_ids=patient_neg_ids,
                max_annotations=opts.max_annotations_per_candidate,
            )
            lines.extend(ann_lines)

    return "\n".join(lines)


def _build_prompt_v7_text(
    case: PatientCase,
    candidates: List[DiseaseCandidate],
    opts: PromptOptions,
    annotation_store: Optional[HPOAnnotationStore] = None,
    hpo_names: Optional[Dict[str, str]] = None,
) -> str:
    """Prompt v7: compressed v6 — same logic, no examples, no reasoning output, ~600 fewer tokens."""
    prompt_candidates = candidates[: max(0, int(opts.candidate_count_in_prompt))]
    output_top_k = min(int(opts.output_top_k), len(prompt_candidates))

    lines: List[str] = []
    lines.append("You are a rare disease expert. Rerank the candidate diagnoses below using clinical reasoning.")
    lines.append("Choose only from the provided candidate list.")
    lines.append("")
    lines.append("## Core principle")
    lines.append("The retrieval model is well-calibrated; rank-1 is correct more than half the time.")
    lines.append("Keep rank-1 unless a specific named clinical reason clearly justifies changing it.")
    lines.append("When in doubt, keep rank-1.")
    lines.append("")
    lines.append("## Score gap gate")
    lines.append("gap = rank-1 retrieval_score minus rank-2 retrieval_score.")
    lines.append("gap > 0.15: keep rank-1 UNCONDITIONALLY (except Condition B biological impossibility).")
    lines.append("0.03 < gap <= 0.15: BOTH Condition A AND Condition B must be met to demote rank-1.")
    lines.append("gap <= 0.03: either Condition A or Condition B alone is sufficient.")
    lines.append("")
    lines.append("## Same-gene spectrum rule")
    lines.append("If rank-1 and the challenger share the same causal gene (check gene_overlap fields), keep rank-1 UNCONDITIONALLY.")
    lines.append("")
    lines.append("## Condition A — obligatory absent feature")
    lines.append("ALL FOUR must be true:")
    lines.append("  1. CONFIRMED ABSENT: feature is in the 'Negative phenotypes' list (or a direct clinical parent of one). Unreported ≠ absent.")
    lines.append("  2. TRULY OBLIGATORY: present in >90% of published cases. 'Hallmark' or 'common' does not qualify.")
    lines.append("  3. NOT NAME-INFERRED: if the absent feature's term appears in the rank-1 disease name, it is name-inferred and INVALID.")
    lines.append("  4. NOT AGE-DEPENDENT: if the feature has known age-dependent onset or variable expressivity, its absence in a single case report does not exclude rank-1.")
    lines.append("")
    lines.append("## Condition B — biological impossibility")
    lines.append("Rank-1 is BIOLOGICALLY INCAPABLE of producing a specific positive phenotype (never observed in any published case),")
    lines.append("AND the challenger explains that phenotype AND covers at least as many of the patient's other phenotypes.")
    lines.append("A challenger that merely explains phenotypes more broadly or more specifically does NOT meet Condition B.")
    lines.append("")
    lines.append("## Numbered-subtype rule")
    lines.append("If candidates are numbered subtypes of the same disease family, keep rank-1 UNCONDITIONALLY unless a gene finding matches rank-2 but not rank-1.")
    lines.append("")
    lines.append("## Output")
    lines.append("Output only the JSON block below. No reasoning text.")
    lines.append("")
    lines.append("{")
    lines.append('  "selected_candidate": {"id": "...", "name": "..."},')
    lines.append('  "ranking": [')
    lines.append('    {"rank": 1, "id": "...", "name": "..."},')
    lines.append('    {"rank": 2, "id": "...", "name": "..."}')
    lines.append("  ]")
    lines.append("}")
    lines.append(f"Return exactly {output_top_k} ranking items ordered best to worst. Copy IDs and names exactly from the candidate list.")
    lines.append("")

    if case.description:
        lines.append(f"Patient description: {case.description}")
    if opts.include_demographics:
        if case.sex:
            lines.append(f"Sex: {case.sex}")
        if case.age:
            lines.append(f"Age: {case.age}")

    positive_lines = _format_pairs(case.phenotype_ids, case.phenotype_labels, opts.max_phenotypes)
    lines.append("Positive phenotypes:")
    lines.extend(positive_lines or ["- None provided"])

    if opts.include_negative_phenotypes:
        negative_lines = _format_pairs(case.neg_phenotype_ids, case.neg_phenotype_labels, opts.max_negative_phenotypes)
        lines.append("Negative phenotypes (explicitly absent):")
        lines.extend(negative_lines or ["- None provided"])

    if opts.include_genes:
        gene_list = case.genes[: max(0, int(opts.max_genes))]
        lines.append("Gene findings:")
        lines.append(f"- {', '.join(gene_list)}" if gene_list else "- None provided")

    lines.append("")
    lines.append("Candidate diseases:")
    for index, candidate in enumerate(prompt_candidates, start=1):
        score_bits = [f"retrieval_score={candidate.score:.6f}", f"retrieval_rank={candidate.retrieval_rank}"]
        if candidate.metadata.get("raw_total_similarity") is not None:
            score_bits.append(f"phenodp_total_similarity={float(candidate.metadata['raw_total_similarity']):.6f}")
        if candidate.metadata.get("gene_overlap"):
            score_bits.append(f"gene_overlap={candidate.metadata['gene_overlap']}")
        lines.append(
            f"{index}. id={candidate.disease_id} | name={candidate.disease_name} | "
            + " | ".join(score_bits)
        )

    return "\n".join(lines)


def _build_pp2prompt_text(
    case: PatientCase,
    candidates: List[DiseaseCandidate],
    opts: PromptOptions,
) -> str:
    """Load pre-generated PP2Prompt file and append candidate list for selection."""
    if not opts.pp2prompt_dir:
        raise ValueError("pp2prompt_dir must be set in PromptOptions when using prompt_version='pp2prompt'")

    prompt_file = _get_pp2prompt_file(case.patient_id, opts.pp2prompt_dir)
    if prompt_file is None:
        # No pre-generated prompt for this case — return empty string so the
        # LLM gets a blank input and scores zero rather than crashing the run.
        return ""

    base_prompt = prompt_file.read_text(encoding="utf-8").rstrip()

    prompt_candidates = candidates[: max(0, int(opts.candidate_count_in_prompt))]

    lines: List[str] = [base_prompt, ""]
    lines.append("The following are candidate diagnoses retrieved by a phenotype-similarity model.")
    lines.append("Please rerank only from these candidates, from most to least likely:")
    lines.append("")
    for index, candidate in enumerate(prompt_candidates, start=1):
        lines.append(f"{index}. {candidate.disease_name} ({candidate.disease_id})")

    return "\n".join(lines)


def _build_pp2prompt_v2_text(
    case: PatientCase,
    candidates: List[DiseaseCandidate],
    opts: PromptOptions,
) -> str:
    """PP2Prompt v2: load pre-generated prompt, append candidates with conservative reranking guidance."""
    if not opts.pp2prompt_dir:
        raise ValueError("pp2prompt_dir must be set in PromptOptions when using prompt_version='pp2prompt_v2'")

    prompt_file = _get_pp2prompt_file(case.patient_id, opts.pp2prompt_dir)
    if prompt_file is None:
        return ""

    base_prompt = prompt_file.read_text(encoding="utf-8").rstrip()

    prompt_candidates = candidates[: max(0, int(opts.candidate_count_in_prompt))]

    lines: List[str] = [base_prompt, ""]
    lines.append("The following candidate diagnoses were retrieved by a phenotype-similarity model and are already ranked by likelihood.")
    lines.append("The model is well-calibrated: its rank-1 candidate is correct more than half the time.")
    lines.append("Keep the existing ranking unless you have strong clinical evidence that a lower-ranked candidate is a better match.")
    lines.append("Choose only from these candidates:")
    lines.append("")
    for index, candidate in enumerate(prompt_candidates, start=1):
        lines.append(f"{index}. {candidate.disease_name} ({candidate.disease_id})")

    return "\n".join(lines)


def build_prompt_text(
    case: PatientCase,
    candidates: List[DiseaseCandidate],
    opts: PromptOptions,
    annotation_store: Optional[HPOAnnotationStore] = None,
    hpo_names: Optional[Dict[str, str]] = None,
) -> str:
    version = getattr(opts, "prompt_version", "v3")
    if version == "pp2prompt_v2":
        return _build_pp2prompt_v2_text(case, candidates, opts)
    if version == "pp2prompt":
        return _build_pp2prompt_text(case, candidates, opts)
    if version == "v7":
        return _build_prompt_v7_text(case, candidates, opts, annotation_store, hpo_names)
    if version == "v6":
        return _build_prompt_v6_text(case, candidates, opts, annotation_store, hpo_names)
    if version == "v5":
        return _build_prompt_v5_text(case, candidates, opts, annotation_store, hpo_names)
    if version == "v4":
        return _build_prompt_v4_text(case, candidates, opts, annotation_store, hpo_names)

    prompt_candidates = candidates[: max(0, int(opts.candidate_count_in_prompt))]
    output_top_k = min(int(opts.output_top_k), len(prompt_candidates))

    has_annotations = opts.include_hpo_annotations and annotation_store is not None

    lines: List[str] = []
    lines.append("You are a rare disease expert reranking a short list of candidate diagnoses for a single patient.")
    lines.append("The candidates were retrieved by a phenotype-similarity model. Your job is to rerank them using clinical reasoning.")
    lines.append("Choose only from the candidate list provided below.")
    lines.append("")
    lines.append("## Core principle")
    lines.append("The retrieval model is well-calibrated. Its rank-1 candidate is correct more than half the time.")
    if has_annotations:
        lines.append("Each candidate below includes HPO phenotype annotations with observed frequencies from medical literature.")
        lines.append("Use these frequencies — not your own guesses — to judge which features are obligatory (>=90%) vs variable.")
    lines.append("")
    lines.append("## The two valid reasons to change rank-1")
    if has_annotations:
        lines.append("A. EXCLUSION: A phenotype annotated at >=90% frequency for rank-1 is explicitly listed as ABSENT (negative phenotype) in this patient.")
        lines.append("   Only features tagged [OBLIGATORY, PATIENT ABSENT] in the annotations qualify for exclusion.")
        lines.append("   If the annotations show a feature at <90%, it is NOT grounds for exclusion even if absent.")
        lines.append("   CRITICAL: A disease having obligatory features that the patient simply did NOT REPORT is NOT evidence against it.")
        lines.append("   Patients rarely report all their features. Only features explicitly listed as ABSENT (negative phenotypes) count.")
    else:
        lines.append("A. EXCLUSION: A feature that is OBLIGATORY (present in >90% of cases) for rank-1 is explicitly absent in this patient.")
        lines.append("   'Hallmark', 'typical', or 'common' features are NOT sufficient — only truly obligatory features qualify.")
        lines.append("   CRITICAL: Do NOT infer obligatory features from the disease name. Phenotype words in a disease name")
        lines.append("   (e.g. 'arachnodactyly' in 'Contractural arachnodactyly', 'cutis laxa' in 'Cutis laxa type ID',")
        lines.append("   'hip dysplasia' in 'Osteosclerosis with hip dysplasia') are NOT evidence that feature is obligatory.")
        lines.append("   Disease names reflect historical descriptions, not penetrance. Use only independent medical knowledge of penetrance.")
    lines.append("B. COVERAGE GAP: Rank-1 fails to explain at least one key positive phenotype or organ system present in this patient,")
    lines.append("   AND a challenger explains that gap, AND the challenger covers at least as many of the other phenotypes as rank-1.")
    if has_annotations:
        lines.append("   Use the annotations to verify coverage: a disease 'explains' a phenotype only if it is annotated for that disease.")
        lines.append("   Compare how many of the patient's positive phenotypes are annotated for each candidate.")
        lines.append("   IMPORTANT: The fact that a challenger has more total annotations or more obligatory features does NOT mean it is a better match.")
        lines.append("   Focus ONLY on the patient's actual phenotypes — not on unreported disease features.")
    else:
        lines.append("   This is about what rank-1 is MISSING — not about which disease has the most impressive name or broadest description.")
        lines.append("   The challenger must explain phenotypes rank-1 genuinely cannot account for — not merely explain them differently.")
    lines.append("   The challenger must be a candidate from the list below — do not reason about diagnoses outside the list.")
    lines.append("If neither A nor B is clearly met, keep rank-1 at position 1.")
    lines.append("")
    lines.append("## Additional rules")
    if has_annotations:
        lines.append("- Use the frequency annotations to determine obligatory features. Do NOT override annotated frequencies with your own assumptions.")
        lines.append("- Features with frequency <90% are variable and CANNOT be used for exclusion, even if they seem important.")
        lines.append("- CRITICAL: Do NOT penalize rank-1 for having obligatory features the patient did not report. Unreported ≠ absent.")
        lines.append("  Only features explicitly listed in the 'Negative phenotypes' section are confirmed absent.")
        lines.append("- When in doubt, keep rank-1. The retrieval model's ranking is strong evidence.")
    else:
        lines.append("- Negative phenotypes exclude a disease ONLY when the absent feature is truly obligatory (>90% penetrance).")
        lines.append("  Variable-penetrance features (even if present in 50-80% of cases) are not grounds for exclusion.")
    lines.append("- Multi-system coherence wins over single-organ specificity. A disease explaining cardiac + limb findings together beats one explaining only the limb findings more precisely.")
    if opts.include_genes:
        lines.append("- Gene evidence is strong supporting evidence when consistent, but does not override an obligatory negative phenotype exclusion.")
    lines.append("- For related disease families, numbered subtypes, and broad-vs-narrow syndrome names: treat them as distinct diseases. Require explicit discriminating findings to switch between them.")
    lines.append("- Do not switch based on disease-name wording, lexical overlap with one phenotype, or apparent subtype specificity.")
    lines.append("- Copy the exact candidate ID and exact candidate name from the list. Do not invent IDs or names.")
    lines.append("")
    lines.append("## Required output")
    lines.append("First write a brief clinical reasoning note (2-3 sentences) stating:")
    if has_annotations:
        lines.append("  (1) whether rank-1 has any OBLIGATORY (>=90%) annotated feature that is absent in this patient,")
        lines.append("  (2) which candidate's annotations best match the patient's positive phenotypes,")
    else:
        lines.append("  (1) whether rank-1 is excluded by an OBLIGATORY absent feature (not name-inferred),")
        lines.append("  (2) whether rank-1 fails to explain any key positive phenotype or organ system that a challenger covers (Coverage Gap B),")
    lines.append("  (3) your final ranking decision.")
    lines.append("Then output the JSON block. Do not add any other text.")
    lines.append("")
    lines.append("{")
    lines.append('  "selected_candidate": {"id": "...", "name": "..."},')
    lines.append('  "ranking": [')
    lines.append('    {"rank": 1, "id": "...", "name": "..."},')
    lines.append('    {"rank": 2, "id": "...", "name": "..."}')
    lines.append("  ]")
    lines.append("}")
    lines.append(f'Return exactly {output_top_k} ranking items ordered from best to worst.')
    lines.append("")

    if case.description:
        lines.append(f"Patient description: {case.description}")
    if opts.include_demographics:
        if case.sex:
            lines.append(f"Sex: {case.sex}")
        if case.age:
            lines.append(f"Age: {case.age}")

    positive_lines = _format_pairs(case.phenotype_ids, case.phenotype_labels, opts.max_phenotypes)
    lines.append("Positive phenotypes:")
    lines.extend(positive_lines or ["- None provided"])

    if opts.include_negative_phenotypes:
        negative_lines = _format_pairs(case.neg_phenotype_ids, case.neg_phenotype_labels, opts.max_negative_phenotypes)
        lines.append("Negative phenotypes (explicitly absent):")
        lines.extend(negative_lines or ["- None provided"])

    if opts.include_genes:
        gene_list = case.genes[: max(0, int(opts.max_genes))]
        lines.append("Gene findings:")
        lines.append(f"- {', '.join(gene_list)}" if gene_list else "- None provided")

    # Build patient HPO sets for annotation matching
    patient_pos_ids: Set[str] = set(case.phenotype_ids)
    patient_neg_ids: Set[str] = set(case.neg_phenotype_ids)

    lines.append("")
    lines.append("Candidate diseases:")
    for index, candidate in enumerate(prompt_candidates, start=1):
        score_bits = [f"retrieval_score={candidate.score:.6f}", f"retrieval_rank={candidate.retrieval_rank}"]
        if candidate.metadata.get("raw_total_similarity") is not None:
            score_bits.append(f"phenodp_total_similarity={float(candidate.metadata['raw_total_similarity']):.6f}")
        if candidate.metadata.get("gene_overlap"):
            score_bits.append(f"gene_overlap={candidate.metadata['gene_overlap']}")
        lines.append(
            f"{index}. id={candidate.disease_id} | name={candidate.disease_name} | "
            + " | ".join(score_bits)
        )

        # Add HPO annotations if available
        if has_annotations and annotation_store is not None:
            ann_lines = annotation_store.format_for_prompt(
                disease_id=candidate.disease_id,
                hpo_names=hpo_names or {},
                patient_pos_hpo_ids=patient_pos_ids,
                patient_neg_hpo_ids=patient_neg_ids,
                max_annotations=opts.max_annotations_per_candidate,
            )
            lines.extend(ann_lines)

    return "\n".join(lines)
