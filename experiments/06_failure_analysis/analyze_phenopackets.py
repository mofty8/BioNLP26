#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import os
import re
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median
from typing import Any, Dict, List, Optional, Sequence

from phenodp_gemma3_pipeline.data_loader import load_phenopackets
from phenodp_gemma3_pipeline.phenodp_retriever import PhenoDPOptions, PhenoDPRetriever
from phenodp_gemma3_pipeline.utils import configure_logging, ensure_dir, write_json


def normalize_truth_id(value: str) -> str:
    raw = str(value or '').strip()
    if not raw:
        return ''
    m = re.match(r'^([A-Za-z]+):0*(\d+)$', raw)
    if m:
        return f"{m.group(1).upper()}:{m.group(2)}"
    if raw.isdigit():
        return str(int(raw))
    return raw.upper()


def id_namespace(value: str) -> str:
    raw = normalize_truth_id(value)
    if not raw:
        return 'NONE'
    if ':' not in raw:
        return 'UNPREFIXED'
    return raw.split(':', 1)[0]


def quantiles(values: Sequence[int], qs: Sequence[float]) -> Dict[str, float]:
    if not values:
        return {str(q): 0.0 for q in qs}
    xs = sorted(values)
    out: Dict[str, float] = {}
    for q in qs:
        if q <= 0:
            out[str(q)] = float(xs[0])
            continue
        if q >= 1:
            out[str(q)] = float(xs[-1])
            continue
        pos = q * (len(xs) - 1)
        lo = math.floor(pos)
        hi = math.ceil(pos)
        if lo == hi:
            out[str(q)] = float(xs[lo])
        else:
            frac = pos - lo
            out[str(q)] = float(xs[lo] * (1 - frac) + xs[hi] * frac)
    return out


def summarize_counts(values: Sequence[int]) -> Dict[str, Any]:
    if not values:
        return {"n": 0, "min": 0, "max": 0, "mean": 0.0, "median": 0.0, "quantiles": {}}
    return {
        "n": len(values),
        "min": int(min(values)),
        "max": int(max(values)),
        "mean": float(sum(values) / len(values)),
        "median": float(median(values)),
        "quantiles": quantiles(values, [0.01, 0.05, 0.1, 0.25, 0.75, 0.9, 0.95, 0.99]),
    }


def top_counter(counter: Counter, limit: int = 25) -> List[Dict[str, Any]]:
    return [{"value": key, "count": int(count)} for key, count in counter.most_common(limit)]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--data-dir', required=True)
    ap.add_argument('--output-dir', required=True)
    ap.add_argument('--phenodp-repo-root', required=True)
    ap.add_argument('--phenodp-data-dir', required=True)
    ap.add_argument('--phenodp-hpo-dir', required=True)
    ap.add_argument('--phenodp-ic-type', default='omim', choices=['omim', 'orpha'])
    ap.add_argument('--phenodp-device', default='cpu', choices=['cpu', 'cuda'])
    args = ap.parse_args()

    out_dir = Path(args.output_dir)
    ensure_dir(out_dir)
    logger = configure_logging(out_dir / 'audit.log', verbose=True)

    dataset = load_phenopackets(args.data_dir, logger=logger, include_excluded_phenotypes=False, min_phenotypes=1)
    retriever = PhenoDPRetriever(
        PhenoDPOptions(
            phenodp_repo_root=args.phenodp_repo_root,
            phenodp_data_dir=args.phenodp_data_dir,
            phenodp_hpo_dir=args.phenodp_hpo_dir,
            ic_type=args.phenodp_ic_type,
            device=args.phenodp_device,
            candidate_pool_size=200,
        )
    )

    phenodp_truth_ids = set(retriever.disease_name_map.keys())
    phenodp_truth_prefixed = {retriever._canonicalize_id(x) for x in phenodp_truth_ids}

    patient_ids = []
    patient_id_counter = Counter()
    source_prefix_counter = Counter()
    disease_namespace_counter = Counter()
    disease_id_counter = Counter()
    truth_per_case = []
    phenotype_counts = []
    neg_phenotype_counts = []
    gene_counts = []
    desc_present = 0
    sex_present = 0
    age_present = 0
    neg_present = 0
    multi_truth_cases = 0
    multi_namespace_cases = 0
    only_non_omim_cases = 0
    any_non_omim_truth_cases = 0
    phenodp_compatible_cases = 0
    phenodp_incompatible_cases = 0
    no_truth_label_cases = 0

    weak_cases_lt2 = []
    weak_cases_lt3 = []
    ambiguous_cases = []
    non_omim_cases = []
    phenodp_incompatible_case_rows = []
    duplicate_patient_ids = []
    cases_rows: List[Dict[str, Any]] = []

    for row in dataset:
        case = row['case']
        truth = row['truth']
        patient_ids.append(case.patient_id)
        patient_id_counter[case.patient_id] += 1
        if patient_id_counter[case.patient_id] == 2:
            duplicate_patient_ids.append(case.patient_id)
        if case.source_prefix:
            source_prefix_counter[case.source_prefix] += 1
        truth_ids_norm = [normalize_truth_id(x) for x in truth.disease_ids if normalize_truth_id(x)]
        namespaces = sorted({id_namespace(x) for x in truth_ids_norm})
        for truth_id in truth_ids_norm:
            disease_namespace_counter[id_namespace(truth_id)] += 1
            disease_id_counter[truth_id] += 1
        truth_per_case.append(len(truth_ids_norm))
        phenotype_counts.append(len(case.phenotype_ids))
        neg_phenotype_counts.append(len(case.neg_phenotype_ids))
        gene_counts.append(len(case.genes))
        if case.description:
            desc_present += 1
        if case.sex:
            sex_present += 1
        if case.age:
            age_present += 1
        if case.neg_phenotype_ids:
            neg_present += 1
        if not truth.disease_labels:
            no_truth_label_cases += 1
        if len(truth_ids_norm) > 1:
            multi_truth_cases += 1
            ambiguous_cases.append(case.patient_id)
        if len(namespaces) > 1:
            multi_namespace_cases += 1
        if any(ns != 'OMIM' for ns in namespaces if ns not in {'NONE'}):
            any_non_omim_truth_cases += 1
        if truth_ids_norm and all(id_namespace(x) != 'OMIM' for x in truth_ids_norm):
            only_non_omim_cases += 1
            non_omim_cases.append(case.patient_id)
        compatible = any(tid in phenodp_truth_prefixed or tid.replace('OMIM:', '') in phenodp_truth_ids for tid in truth_ids_norm)
        if compatible:
            phenodp_compatible_cases += 1
        else:
            phenodp_incompatible_cases += 1
            phenodp_incompatible_case_rows.append(case.patient_id)
        if len(case.phenotype_ids) < 2:
            weak_cases_lt2.append(case.patient_id)
        if len(case.phenotype_ids) < 3:
            weak_cases_lt3.append(case.patient_id)

        cases_rows.append({
            'patient_id': case.patient_id,
            'source_prefix': case.source_prefix or '',
            'file_path': case.file_path or '',
            'n_truth_ids': len(truth_ids_norm),
            'truth_ids': '|'.join(truth_ids_norm),
            'truth_names': '|'.join(truth.disease_labels),
            'truth_namespaces': '|'.join(namespaces),
            'n_positive_phenotypes': len(case.phenotype_ids),
            'n_negative_phenotypes': len(case.neg_phenotype_ids),
            'n_genes': len(case.genes),
            'has_description': int(bool(case.description)),
            'has_sex': int(bool(case.sex)),
            'has_age': int(bool(case.age)),
            'phenodp_compatible_truth': int(compatible),
            'only_non_omim_truth': int(bool(truth_ids_norm) and all(id_namespace(x) != 'OMIM' for x in truth_ids_norm)),
            'multi_truth_case': int(len(truth_ids_norm) > 1),
            'weak_lt2_phenotypes': int(len(case.phenotype_ids) < 2),
            'weak_lt3_phenotypes': int(len(case.phenotype_ids) < 3),
        })

    recommended_filters = {
        'already_excluded_by_loader': {
            'description': 'Cases with no truth IDs or no positive phenotypes are already excluded by the loader.',
            'count_in_loaded_dataset': 0,
        },
        'filter_non_phenodp_truth_namespace': {
            'description': 'Cases whose truth IDs are entirely outside OMIM are unfair for an OMIM-only PhenoDP retriever.',
            'count': int(only_non_omim_cases),
            'example_patient_ids': non_omim_cases[:25],
        },
        'filter_multi_truth_cases_if_single-label_ranking_is_required': {
            'description': 'Cases with multiple truth disease IDs make top-1 single-candidate evaluation less clean.',
            'count': int(multi_truth_cases),
            'example_patient_ids': ambiguous_cases[:25],
        },
        'consider_filtering_very_low_signal_cases_lt2_positive_hpo': {
            'description': 'Cases with fewer than 2 positive phenotypes provide extremely weak retrieval signal.',
            'count': int(len(weak_cases_lt2)),
            'example_patient_ids': weak_cases_lt2[:25],
        },
        'consider_filtering_very_low_signal_cases_lt3_positive_hpo': {
            'description': 'More conservative low-signal filter threshold using fewer than 3 positive phenotypes.',
            'count': int(len(weak_cases_lt3)),
            'example_patient_ids': weak_cases_lt3[:25],
        },
        'do_not_filter_by_missing_description_or_demographics': {
            'description': 'Missing description, age, or sex is common and does not break retrieval; filtering on this would mainly reduce coverage without improving fairness.',
            'count_missing_description': int(len(dataset) - desc_present),
            'count_missing_sex': int(len(dataset) - sex_present),
            'count_missing_age': int(len(dataset) - age_present),
        },
    }

    summary = {
        'dataset_root': args.data_dir,
        'n_cases_loaded': len(dataset),
        'n_unique_patient_ids': len(set(patient_ids)),
        'n_duplicate_patient_ids': len(duplicate_patient_ids),
        'phenotype_counts': summarize_counts(phenotype_counts),
        'negative_phenotype_counts': summarize_counts(neg_phenotype_counts),
        'gene_counts': summarize_counts(gene_counts),
        'truth_ids_per_case': summarize_counts(truth_per_case),
        'coverage': {
            'has_negative_phenotype': int(neg_present),
            'has_negative_phenotype_rate': float(neg_present / len(dataset)) if dataset else 0.0,
            'has_description': int(desc_present),
            'has_description_rate': float(desc_present / len(dataset)) if dataset else 0.0,
            'has_sex': int(sex_present),
            'has_sex_rate': float(sex_present / len(dataset)) if dataset else 0.0,
            'has_age': int(age_present),
            'has_age_rate': float(age_present / len(dataset)) if dataset else 0.0,
            'has_truth_label': int(len(dataset) - no_truth_label_cases),
            'has_truth_label_rate': float((len(dataset) - no_truth_label_cases) / len(dataset)) if dataset else 0.0,
        },
        'truth_namespaces': {
            'per_truth_id': dict(disease_namespace_counter),
            'top_truth_ids': top_counter(disease_id_counter, 30),
            'cases_with_any_non_omim_truth': int(any_non_omim_truth_cases),
            'cases_with_only_non_omim_truth': int(only_non_omim_cases),
            'cases_with_multiple_truth_ids': int(multi_truth_cases),
            'cases_with_multiple_truth_namespaces': int(multi_namespace_cases),
        },
        'phenodp_compatibility': {
            'ic_type': args.phenodp_ic_type,
            'n_phenodp_diseases': int(len(phenodp_truth_ids)),
            'compatible_cases': int(phenodp_compatible_cases),
            'compatible_case_rate': float(phenodp_compatible_cases / len(dataset)) if dataset else 0.0,
            'incompatible_cases': int(phenodp_incompatible_cases),
            'incompatible_case_rate': float(phenodp_incompatible_cases / len(dataset)) if dataset else 0.0,
            'example_incompatible_patient_ids': phenodp_incompatible_case_rows[:25],
        },
        'publication_structure': {
            'unique_source_prefixes': int(len(source_prefix_counter)),
            'top_source_prefixes': top_counter(source_prefix_counter, 25),
        },
        'recommended_filters': recommended_filters,
    }

    write_json(out_dir / 'dataset_audit_summary.json', summary)

    import csv
    with open(out_dir / 'dataset_case_audit.csv', 'w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(cases_rows[0].keys()))
        writer.writeheader()
        for row in cases_rows:
            writer.writerow(row)

    logger.info('Wrote %s', out_dir / 'dataset_audit_summary.json')
    logger.info('Wrote %s', out_dir / 'dataset_case_audit.csv')


if __name__ == '__main__':
    main()
