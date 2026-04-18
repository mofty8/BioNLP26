from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .models import PatientCase, Truth


_SEX_NORMALIZE = {
    "MALE": "Male",
    "FEMALE": "Female",
    "OTHER_SEX": "Other",
    "UNKNOWN_SEX": "Unknown",
}


def _get_pub_prefix(patient_id: str) -> Optional[str]:
    if patient_id and patient_id.startswith("PMID"):
        parts = patient_id.split("_")
        if len(parts) >= 2:
            return "_".join(parts[:2])
    return None


def _safe_get(payload: Dict[str, Any], *keys: str) -> Optional[Any]:
    current: Any = payload
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current


def extract_truth(payload: Dict[str, Any]) -> Truth:
    disease_ids: List[str] = []
    disease_labels: List[str] = []

    for interpretation in payload.get("interpretations") or []:
        diagnosis = (interpretation or {}).get("diagnosis") or {}
        disease = diagnosis.get("disease") or {}
        disease_id = disease.get("id")
        disease_label = disease.get("label")
        if disease_id:
            disease_ids.append(str(disease_id))
            if disease_label:
                disease_labels.append(str(disease_label))

    for disease_entry in payload.get("diseases") or []:
        term = (disease_entry or {}).get("term") or (disease_entry or {}).get("disease") or {}
        disease_id = term.get("id")
        disease_label = term.get("label")
        if disease_id:
            disease_ids.append(str(disease_id))
            if disease_label:
                disease_labels.append(str(disease_label))

    seen_ids = set()
    uniq_ids: List[str] = []
    for disease_id in disease_ids:
        if disease_id not in seen_ids:
            uniq_ids.append(disease_id)
            seen_ids.add(disease_id)

    seen_labels = set()
    uniq_labels: List[str] = []
    for disease_label in disease_labels:
        if disease_label not in seen_labels:
            uniq_labels.append(disease_label)
            seen_labels.add(disease_label)

    return Truth(disease_ids=uniq_ids, disease_labels=uniq_labels)


def extract_phenotypes_pos_neg(payload: Dict[str, Any]) -> Tuple[List[str], List[str], List[str], List[str]]:
    pos_ids: List[str] = []
    pos_labels: List[str] = []
    neg_ids: List[str] = []
    neg_labels: List[str] = []

    for feature in payload.get("phenotypicFeatures") or []:
        feature = feature or {}
        phenotype = feature.get("type") or {}
        phenotype_id = phenotype.get("id")
        if not phenotype_id:
            continue
        phenotype_label = str(phenotype.get("label") or phenotype_id)
        if feature.get("excluded"):
            neg_ids.append(str(phenotype_id))
            neg_labels.append(phenotype_label)
        else:
            pos_ids.append(str(phenotype_id))
            pos_labels.append(phenotype_label)

    return pos_ids, pos_labels, neg_ids, neg_labels


def extract_genes(payload: Dict[str, Any]) -> List[str]:
    genes = set()

    for interpretation in payload.get("interpretations") or []:
        diagnosis = (interpretation or {}).get("diagnosis") or {}
        genomic_interpretations = diagnosis.get("genomicInterpretations") or []
        for genomic_interpretation in genomic_interpretations:
            genomic_interpretation = genomic_interpretation or {}
            variant = genomic_interpretation.get("variantInterpretation") or {}
            descriptor = variant.get("variationDescriptor") or variant.get("variantDescriptor") or {}
            gene_context = descriptor.get("geneContext") or {}
            symbol = gene_context.get("symbol")
            if symbol:
                genes.add(str(symbol))
            gene_descriptor = genomic_interpretation.get("geneDescriptor") or {}
            gene_symbol = gene_descriptor.get("symbol")
            if gene_symbol:
                genes.add(str(gene_symbol))

    for genomic_interpretation in payload.get("genomicInterpretations") or []:
        genomic_interpretation = genomic_interpretation or {}
        gene_descriptor = genomic_interpretation.get("geneDescriptor") or {}
        gene_symbol = gene_descriptor.get("symbol")
        if gene_symbol:
            genes.add(str(gene_symbol))

    return sorted(genes)


def extract_case_text(payload: Dict[str, Any]) -> str:
    for key_path in [("subject", "description"), ("description",)]:
        value = _safe_get(payload, *key_path) if len(key_path) > 1 else payload.get(key_path[0])
        if value:
            return str(value)
    return ""


def extract_sex(payload: Dict[str, Any]) -> Optional[str]:
    sex = _safe_get(payload, "subject", "sex")
    if isinstance(sex, str) and sex:
        return _SEX_NORMALIZE.get(sex, sex)
    if isinstance(sex, dict):
        label = sex.get("label") or sex.get("id")
        if label:
            return str(label)
    return None


def extract_age(payload: Dict[str, Any]) -> Optional[str]:
    age = _safe_get(payload, "subject", "age")
    if isinstance(age, str) and age:
        return age
    if isinstance(age, dict):
        duration = age.get("iso8601duration") or age.get("duration")
        if duration:
            return str(duration)
        nested = age.get("age")
        if isinstance(nested, dict):
            nested_duration = nested.get("iso8601duration") or nested.get("duration")
            if nested_duration:
                return str(nested_duration)
        if isinstance(nested, str) and nested:
            return nested
    return None


def extract_patient_id(payload: Dict[str, Any], file_path: str) -> str:
    return Path(file_path).stem


def load_phenopackets(
    root_dir: str,
    logger,
    include_excluded_phenotypes: bool = False,
    min_phenotypes: int = 1,
) -> List[Dict[str, Any]]:
    root = Path(root_dir)
    if not root.exists():
        raise FileNotFoundError(f"Dataset directory not found: {root_dir}")

    dataset: List[Dict[str, Any]] = []
    n_files = 0
    n_errors = 0
    n_skipped_no_truth = 0
    n_skipped_no_phenotype = 0

    for dirpath, _, filenames in os.walk(root_dir):
        for filename in filenames:
            if not filename.endswith(".json"):
                continue
            n_files += 1
            path = os.path.join(dirpath, filename)
            try:
                with open(path, "r", encoding="utf-8") as handle:
                    payload = json.load(handle)

                patient_id = extract_patient_id(payload, path)
                truth = extract_truth(payload)
                if not truth.disease_ids:
                    n_skipped_no_truth += 1
                    continue

                pos_ids, pos_labels, neg_ids, neg_labels = extract_phenotypes_pos_neg(payload)
                phenotype_ids = pos_ids + neg_ids if include_excluded_phenotypes else pos_ids
                phenotype_labels = pos_labels + neg_labels if include_excluded_phenotypes else pos_labels
                if len(phenotype_ids) < int(min_phenotypes):
                    n_skipped_no_phenotype += 1
                    continue

                case = PatientCase(
                    patient_id=patient_id,
                    description=extract_case_text(payload),
                    phenotype_ids=phenotype_ids,
                    phenotype_labels=phenotype_labels,
                    neg_phenotype_ids=neg_ids,
                    neg_phenotype_labels=neg_labels,
                    genes=extract_genes(payload),
                    sex=extract_sex(payload),
                    age=extract_age(payload),
                    source_prefix=_get_pub_prefix(patient_id),
                    file_path=path,
                )
                dataset.append({"case": case, "truth": truth})
            except Exception:
                n_errors += 1

    logger.info(
        "Loaded phenopackets: files=%d cases=%d skipped(no_truth)=%d skipped(no_phenotype)=%d errors=%d",
        n_files,
        len(dataset),
        n_skipped_no_truth,
        n_skipped_no_phenotype,
        n_errors,
    )
    logger.info("Cases with genes: %d / %d", sum(1 for row in dataset if row["case"].genes), len(dataset))
    return dataset
