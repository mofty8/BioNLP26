#!/usr/bin/env python3
"""
Publication-level dataset characterization for the BioNLP @ ACL 2026 paper
"Phenotype Retrieval Outperforms LLM Reasoning for Rare Disease Diagnosis".

Compares five rare-disease datasets
  - Phenopacket (all JSONs under PP_LLM/phenopackets_extracted/0.1.25)
  - Phenopacket (6,901 phenodp-compatible subset)
  - RAMEDIS, LIRICAL, HMS, MME (RareBench_min jsonl)

against the complete HPO disease ontology (phenotype.hpoa + hp.obo).

Outputs: tables/*.csv, figures/*.png, summary.md
"""
from __future__ import annotations

import json
import logging
import math
import os
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns


ROOT = Path("/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket")
OUT_DIR = ROOT / "datasets_analysis_20260410"
TABLES_DIR = OUT_DIR / "tables"
FIGURES_DIR = OUT_DIR / "figures"
CACHE_DIR = OUT_DIR / "cache"

HP_OBO = ROOT / "PehnoPacketPhenoDP/PhenoDP/data/hpo_latest/hp.obo"
PHENOTYPE_HPOA = ROOT / "PehnoPacketPhenoDP/PhenoDP/data/hpo_latest/phenotype.hpoa"
PHENOPACKET_DIR = ROOT / "PP_LLM/phenopackets_extracted/0.1.25"
BENCHMARK_IDS = ROOT / "phenodp_gemma3_candidate_ranking/benchmark_ids_6901_phenodp_compatible_min3hpo.txt"
RAREBENCH_DIR = ROOT / "datasets/RareBench_min/data"

PHENO_ABNORMALITY_ROOT = "HP:0000118"

DATASET_ORDER = [
    "phenopacket_all",
    "phenopacket_6901",
    "RAMEDIS",
    "LIRICAL",
    "HMS",
    "MME",
]
DATASET_DISPLAY = {
    "phenopacket_all": "Phenopacket (all)",
    "phenopacket_6901": "Phenopacket (6,901)",
    "RAMEDIS": "RAMEDIS",
    "LIRICAL": "LIRICAL",
    "HMS": "HMS",
    "MME": "MME",
}
DATASET_ORIGIN = {
    "phenopacket_all": "Literature",
    "phenopacket_6901": "Literature",
    "RAMEDIS": "Structured",
    "LIRICAL": "Literature",
    "HMS": "Clinical",
    "MME": "Clinical",
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("datasets_analysis")


# =====================================================================
# Data classes
# =====================================================================

@dataclass
class Case:
    dataset: str
    case_id: str
    disease_ids: List[str]
    hpo_pos: List[str]
    hpo_neg: List[str]
    source_prefix: Optional[str] = None


# =====================================================================
# HPO ontology loading (manual hp.obo parser)
# =====================================================================

def parse_hp_obo(path: Path) -> Tuple[Dict[str, Dict], Dict[str, str]]:
    """Parse hp.obo → (terms, alt_id_map).

    terms[hp_id] = {"id", "name", "parents": [hp_id], "obsolete": bool}
    alt_id_map[alt_hp_id] = canonical_hp_id
    Obsolete terms are excluded from `terms` but their alt_ids still map.
    """
    terms: Dict[str, Dict] = {}
    alt_map: Dict[str, str] = {}
    current: Optional[Dict] = None
    in_term = False

    def commit(cur: Optional[Dict]) -> None:
        if not cur:
            return
        if cur.get("obsolete"):
            return
        tid = cur.get("id")
        if not tid:
            return
        terms[tid] = cur
        for alt in cur.get("alt_ids", []):
            alt_map[alt] = tid

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if line.startswith("[") and line.endswith("]"):
                commit(current)
                if line == "[Term]":
                    current = {"parents": [], "alt_ids": []}
                    in_term = True
                else:
                    current = None
                    in_term = False
                continue
            if not in_term or current is None:
                continue
            if line.startswith("id: "):
                current["id"] = line[4:].strip()
            elif line.startswith("name: "):
                current["name"] = line[6:].strip()
            elif line.startswith("is_a: "):
                rest = line[6:].strip()
                pid = rest.split(" !", 1)[0].strip()
                current["parents"].append(pid)
            elif line.startswith("alt_id: "):
                current["alt_ids"].append(line[8:].strip())
            elif line.startswith("is_obsolete: true"):
                current["obsolete"] = True
        commit(current)

    log.info("parsed hp.obo: %d terms, %d alt_ids", len(terms), len(alt_map))
    return terms, alt_map


def resolve_hpo(term_id: str, terms: Dict, alt_map: Dict) -> Optional[str]:
    if term_id in terms:
        return term_id
    if term_id in alt_map:
        return alt_map[term_id]
    return None


def compute_ancestors(terms: Dict[str, Dict]) -> Dict[str, Set[str]]:
    """Inclusive ancestor closure for each term."""
    ancestors: Dict[str, Set[str]] = {}

    def dfs(tid: str, stack: Set[str]) -> Set[str]:
        if tid in ancestors:
            return ancestors[tid]
        if tid in stack:
            return {tid}
        stack = stack | {tid}
        result = {tid}
        for p in terms.get(tid, {}).get("parents", []):
            if p in terms:
                result |= dfs(p, stack)
        ancestors[tid] = result
        return result

    for tid in list(terms.keys()):
        dfs(tid, set())
    return ancestors


def compute_depths_from_root(
    terms: Dict[str, Dict], root: str = PHENO_ABNORMALITY_ROOT
) -> Dict[str, int]:
    children: Dict[str, List[str]] = defaultdict(list)
    for tid, info in terms.items():
        for p in info.get("parents", []):
            children[p].append(tid)
    depths: Dict[str, int] = {}
    if root not in terms:
        return depths
    depths[root] = 0
    frontier = [root]
    while frontier:
        nxt: List[str] = []
        for t in frontier:
            for c in children.get(t, []):
                if c not in depths:
                    depths[c] = depths[t] + 1
                    nxt.append(c)
        frontier = nxt
    return depths


def compute_top_categories(
    terms: Dict[str, Dict],
    ancestors: Dict[str, Set[str]],
    root: str = PHENO_ABNORMALITY_ROOT,
) -> Dict[str, Set[str]]:
    """For each term, return the set of direct children of `root` (top-level
    organ-system categories) that are ancestors of the term."""
    top_level = [
        tid
        for tid, info in terms.items()
        if root in info.get("parents", [])
    ]
    top_set = set(top_level)
    term_to_cats: Dict[str, Set[str]] = {}
    for tid in terms:
        anc = ancestors.get(tid, {tid})
        cats = anc & top_set
        if cats:
            term_to_cats[tid] = cats
    return term_to_cats


# =====================================================================
# phenotype.hpoa loading + Information Content
# =====================================================================

def load_hpoa(path: Path) -> Dict[str, Set[str]]:
    """disease_id → set of HPO term ids (aspect P, non-NOT annotations)."""
    disease_to_hpos: Dict[str, Set[str]] = defaultdict(set)
    header: Optional[List[str]] = None
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("#"):
                continue
            parts = line.rstrip("\n").split("\t")
            if header is None:
                header = parts
                continue
            if len(parts) < len(header):
                continue
            row = dict(zip(header, parts))
            if row.get("aspect") != "P":
                continue
            if (row.get("qualifier") or "").strip():
                continue
            disease_id = (row.get("database_id") or "").strip()
            hpo_id = (row.get("hpo_id") or "").strip()
            if disease_id and hpo_id:
                disease_to_hpos[disease_id].add(hpo_id)
    log.info("loaded phenotype.hpoa: %d diseases with P annotations", len(disease_to_hpos))
    return dict(disease_to_hpos)


def propagate_annotations(
    disease_to_hpos: Dict[str, Set[str]],
    ancestors: Dict[str, Set[str]],
) -> Dict[str, Set[str]]:
    """Propagate each disease's HPOs to all ancestors (true-path rule)."""
    propagated: Dict[str, Set[str]] = {}
    for d, hpos in disease_to_hpos.items():
        closure: Set[str] = set()
        for h in hpos:
            closure |= ancestors.get(h, {h})
        propagated[d] = closure
    return propagated


def compute_ic(propagated: Dict[str, Set[str]]) -> Dict[str, float]:
    """IC(t) = -log(freq(t) / N)  with propagated frequencies."""
    freq: Counter = Counter()
    for closure in propagated.values():
        for t in closure:
            freq[t] += 1
    N = len(propagated)
    ic: Dict[str, float] = {}
    for t, f in freq.items():
        p = f / N if N else 0.0
        ic[t] = -math.log(p) if p > 0 else 0.0
    return ic


# =====================================================================
# Dataset loaders
# =====================================================================

NAMESPACE_RE = re.compile(r"^([A-Za-z]+):0*(\d+)$")


def normalize_id(raw: str) -> str:
    s = (raw or "").strip()
    if not s:
        return ""
    m = NAMESPACE_RE.match(s)
    if m:
        return f"{m.group(1).upper()}:{m.group(2)}"
    return s.upper()


def namespace_of(disease_id: str) -> str:
    if not disease_id:
        return "NONE"
    if ":" not in disease_id:
        return "UNPREFIXED"
    return disease_id.split(":", 1)[0]


def load_phenopacket_cases(
    root: Path,
    dataset_key: str,
    allowed_ids: Optional[Set[str]] = None,
) -> List[Case]:
    cases: List[Case] = []
    n_seen = 0
    for dirpath, _, filenames in os.walk(root):
        for fn in filenames:
            if not fn.endswith(".json"):
                continue
            n_seen += 1
            path = Path(dirpath) / fn
            patient_id = path.stem
            if allowed_ids is not None and patient_id not in allowed_ids:
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            disease_ids: List[str] = []
            for interp in payload.get("interpretations") or []:
                d = (interp or {}).get("diagnosis") or {}
                dis = d.get("disease") or {}
                did = dis.get("id")
                if did:
                    disease_ids.append(normalize_id(did))
            for d in payload.get("diseases") or []:
                term = (d or {}).get("term") or (d or {}).get("disease") or {}
                did = term.get("id")
                if did:
                    disease_ids.append(normalize_id(did))
            seen: Set[str] = set()
            unique: List[str] = []
            for d in disease_ids:
                if d and d not in seen:
                    seen.add(d)
                    unique.append(d)
            if not unique:
                continue
            pos: List[str] = []
            neg: List[str] = []
            for feat in payload.get("phenotypicFeatures") or []:
                feat = feat or {}
                t = (feat.get("type") or {}).get("id")
                if not t:
                    continue
                if feat.get("excluded"):
                    neg.append(t)
                else:
                    pos.append(t)
            if not pos:
                continue
            source_prefix: Optional[str] = None
            if patient_id.startswith("PMID"):
                parts = patient_id.split("_")
                if len(parts) >= 2:
                    source_prefix = "_".join(parts[:2])
            cases.append(
                Case(
                    dataset=dataset_key,
                    case_id=patient_id,
                    disease_ids=unique,
                    hpo_pos=pos,
                    hpo_neg=neg,
                    source_prefix=source_prefix,
                )
            )
    log.info(
        "loaded %s: %d cases (from %d json files)",
        dataset_key,
        len(cases),
        n_seen,
    )
    return cases


def load_rarebench_cases(path: Path, dataset_key: str) -> List[Case]:
    cases: List[Case] = []
    with open(path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            diseases_raw = rec.get("RareDisease") or []
            diseases: List[str] = []
            seen: Set[str] = set()
            for d in diseases_raw:
                nd = normalize_id(d)
                if nd and nd not in seen:
                    seen.add(nd)
                    diseases.append(nd)
            pos = [h for h in (rec.get("Phenotype") or []) if h]
            if not diseases or not pos:
                continue
            cases.append(
                Case(
                    dataset=dataset_key,
                    case_id=f"{dataset_key}_{i:05d}",
                    disease_ids=diseases,
                    hpo_pos=pos,
                    hpo_neg=[],
                    source_prefix=None,
                )
            )
    log.info("loaded %s: %d cases", dataset_key, len(cases))
    return cases


def load_benchmark_ids(path: Path) -> Set[str]:
    with open(path, "r", encoding="utf-8") as f:
        return {line.strip() for line in f if line.strip()}


# =====================================================================
# Per-dataset statistics
# =====================================================================

def quantile_summary(values: Iterable[int]) -> Dict[str, float]:
    arr = np.array(list(values), dtype=float)
    if arr.size == 0:
        return {k: 0.0 for k in ("n", "min", "p05", "p25", "p50", "p75", "p95", "max", "mean")}
    return {
        "n": int(arr.size),
        "min": float(arr.min()),
        "p05": float(np.percentile(arr, 5)),
        "p25": float(np.percentile(arr, 25)),
        "p50": float(np.percentile(arr, 50)),
        "p75": float(np.percentile(arr, 75)),
        "p95": float(np.percentile(arr, 95)),
        "max": float(arr.max()),
        "mean": float(arr.mean()),
    }


def resolve_case_hpos(
    case: Case,
    terms: Dict[str, Dict],
    alt_map: Dict[str, str],
) -> List[str]:
    resolved: List[str] = []
    for h in case.hpo_pos:
        r = resolve_hpo(h, terms, alt_map)
        if r is not None:
            resolved.append(r)
    return resolved


def build_overview_row(
    cases: List[Case],
    dataset_key: str,
    terms: Dict[str, Dict],
    alt_map: Dict[str, str],
) -> Dict:
    n = len(cases)
    n_multi = sum(1 for c in cases if len(c.disease_ids) > 1)
    n_any_neg = sum(1 for c in cases if c.hpo_neg)

    ns_truth: Counter = Counter()
    primary_ns: Counter = Counter()
    for c in cases:
        for d in c.disease_ids:
            ns_truth[namespace_of(d)] += 1
        if c.disease_ids:
            primary_ns[namespace_of(c.disease_ids[0])] += 1

    n_with_omim = sum(
        1 for c in cases if any(namespace_of(d) == "OMIM" for d in c.disease_ids)
    )
    n_with_orpha = sum(
        1 for c in cases if any(namespace_of(d) == "ORPHA" for d in c.disease_ids)
    )
    n_only_omim = sum(
        1
        for c in cases
        if c.disease_ids and all(namespace_of(d) == "OMIM" for d in c.disease_ids)
    )
    n_only_orpha = sum(
        1
        for c in cases
        if c.disease_ids and all(namespace_of(d) == "ORPHA" for d in c.disease_ids)
    )

    pos_counts = [len(c.hpo_pos) for c in cases]
    neg_counts = [len(c.hpo_neg) for c in cases]
    dis_counts = [len(c.disease_ids) for c in cases]

    unique_diseases: Set[str] = set()
    unique_hpos: Set[str] = set()
    unique_hpos_resolved: Set[str] = set()
    for c in cases:
        unique_diseases.update(c.disease_ids)
        unique_hpos.update(c.hpo_pos)
        for h in c.hpo_pos:
            r = resolve_hpo(h, terms, alt_map)
            if r:
                unique_hpos_resolved.add(r)

    unresolved_hpo = len(unique_hpos) - len(unique_hpos_resolved)

    row = {
        "dataset": dataset_key,
        "origin": DATASET_ORIGIN.get(dataset_key, ""),
        "n_cases": n,
        "n_unique_truth_diseases": len(unique_diseases),
        "n_cases_multi_truth": n_multi,
        "pct_cases_multi_truth": round(100 * n_multi / n, 2) if n else 0.0,
        "n_cases_with_any_neg_hpo": n_any_neg,
        "pct_cases_with_any_neg_hpo": round(100 * n_any_neg / n, 2) if n else 0.0,
        "n_cases_with_any_omim_truth": n_with_omim,
        "n_cases_with_any_orpha_truth": n_with_orpha,
        "n_cases_only_omim_truth": n_only_omim,
        "n_cases_only_orpha_truth": n_only_orpha,
        "n_unique_hpo_terms_raw": len(unique_hpos),
        "n_unique_hpo_terms_resolved": len(unique_hpos_resolved),
        "n_unique_hpo_terms_unresolved": unresolved_hpo,
    }
    for k, v in quantile_summary(pos_counts).items():
        row[f"pos_hpo_per_case_{k}"] = round(v, 3)
    for k, v in quantile_summary(neg_counts).items():
        row[f"neg_hpo_per_case_{k}"] = round(v, 3)
    for k, v in quantile_summary(dis_counts).items():
        row[f"diseases_per_case_{k}"] = round(v, 3)
    for ns, count in ns_truth.most_common():
        row[f"truth_ns_{ns}"] = count
    return row


def build_phenotype_count_table(cases_by_ds: Dict[str, List[Case]]) -> pd.DataFrame:
    rows = []
    for ds in DATASET_ORDER:
        cases = cases_by_ds.get(ds, [])
        q = quantile_summary([len(c.hpo_pos) for c in cases])
        rows.append(
            {
                "dataset": ds,
                "display": DATASET_DISPLAY[ds],
                "origin": DATASET_ORIGIN.get(ds, ""),
                "n_cases": q["n"],
                "pos_hpo_min": int(q["min"]),
                "pos_hpo_p05": round(q["p05"], 1),
                "pos_hpo_p25": round(q["p25"], 1),
                "pos_hpo_p50": round(q["p50"], 1),
                "pos_hpo_p75": round(q["p75"], 1),
                "pos_hpo_p95": round(q["p95"], 1),
                "pos_hpo_max": int(q["max"]),
                "pos_hpo_mean": round(q["mean"], 2),
            }
        )
    return pd.DataFrame(rows)


# =====================================================================
# HPO specificity (depth + IC)
# =====================================================================

def build_specificity_table(
    cases_by_ds: Dict[str, List[Case]],
    terms: Dict[str, Dict],
    alt_map: Dict[str, str],
    depths: Dict[str, int],
    ic: Dict[str, float],
) -> Tuple[pd.DataFrame, Dict[str, List[float]], Dict[str, List[float]]]:
    """Returns summary dataframe + per-case-mean arrays (for plotting)."""
    rows = []
    case_mean_ic_by_ds: Dict[str, List[float]] = {}
    case_mean_depth_by_ds: Dict[str, List[float]] = {}
    for ds in DATASET_ORDER:
        cases = cases_by_ds.get(ds, [])
        term_depths: List[int] = []
        term_ics: List[float] = []
        case_mean_ic: List[float] = []
        case_mean_depth: List[float] = []
        for c in cases:
            this_depths: List[int] = []
            this_ics: List[float] = []
            for h in c.hpo_pos:
                r = resolve_hpo(h, terms, alt_map)
                if r is None:
                    continue
                d = depths.get(r)
                if d is not None:
                    this_depths.append(d)
                    term_depths.append(d)
                i = ic.get(r)
                if i is not None:
                    this_ics.append(i)
                    term_ics.append(i)
            if this_depths:
                case_mean_depth.append(float(np.mean(this_depths)))
            if this_ics:
                case_mean_ic.append(float(np.mean(this_ics)))
        case_mean_ic_by_ds[ds] = case_mean_ic
        case_mean_depth_by_ds[ds] = case_mean_depth
        rows.append(
            {
                "dataset": ds,
                "display": DATASET_DISPLAY[ds],
                "n_cases": len(cases),
                "n_term_occurrences": len(term_depths),
                "term_depth_mean": round(float(np.mean(term_depths)), 3) if term_depths else 0.0,
                "term_depth_median": round(float(np.median(term_depths)), 3) if term_depths else 0.0,
                "term_ic_mean": round(float(np.mean(term_ics)), 3) if term_ics else 0.0,
                "term_ic_median": round(float(np.median(term_ics)), 3) if term_ics else 0.0,
                "case_mean_depth_mean": round(float(np.mean(case_mean_depth)), 3) if case_mean_depth else 0.0,
                "case_mean_ic_mean": round(float(np.mean(case_mean_ic)), 3) if case_mean_ic else 0.0,
            }
        )
    return pd.DataFrame(rows), case_mean_ic_by_ds, case_mean_depth_by_ds


# =====================================================================
# Ontology coverage
# =====================================================================

def build_coverage_table(
    cases_by_ds: Dict[str, List[Case]],
    disease_to_hpos: Dict[str, Set[str]],
    terms: Dict[str, Dict],
    alt_map: Dict[str, str],
) -> pd.DataFrame:
    hpoa_diseases = set(disease_to_hpos.keys())
    hpoa_omim = {d for d in hpoa_diseases if namespace_of(d) == "OMIM"}
    hpoa_orpha = {d for d in hpoa_diseases if namespace_of(d) == "ORPHA"}
    hpoa_decipher = {d for d in hpoa_diseases if namespace_of(d) == "DECIPHER"}
    # HPO term universe = any term ever used in an hpoa annotation
    hpoa_terms: Set[str] = set()
    for s in disease_to_hpos.values():
        hpoa_terms.update(s)

    rows = []
    for ds in DATASET_ORDER:
        cases = cases_by_ds.get(ds, [])
        covered_diseases = {d for c in cases for d in c.disease_ids}
        cov_omim = covered_diseases & hpoa_omim
        cov_orpha = covered_diseases & hpoa_orpha
        cov_decipher = covered_diseases & hpoa_decipher
        case_truth_in_hpoa = sum(
            1
            for c in cases
            if any(d in hpoa_diseases for d in c.disease_ids)
        )
        used_hpos_resolved: Set[str] = set()
        for c in cases:
            for h in c.hpo_pos:
                r = resolve_hpo(h, terms, alt_map)
                if r:
                    used_hpos_resolved.add(r)
        covered_hpos = used_hpos_resolved & hpoa_terms
        rows.append(
            {
                "dataset": ds,
                "display": DATASET_DISPLAY[ds],
                "n_cases": len(cases),
                "n_unique_truth_diseases": len(covered_diseases),
                "cases_with_truth_in_hpoa": case_truth_in_hpoa,
                "cases_with_truth_in_hpoa_pct": round(100 * case_truth_in_hpoa / len(cases), 2) if cases else 0.0,
                "hpoa_omim_covered": len(cov_omim),
                "hpoa_omim_total": len(hpoa_omim),
                "hpoa_omim_coverage_pct": round(100 * len(cov_omim) / len(hpoa_omim), 3) if hpoa_omim else 0.0,
                "hpoa_orpha_covered": len(cov_orpha),
                "hpoa_orpha_total": len(hpoa_orpha),
                "hpoa_orpha_coverage_pct": round(100 * len(cov_orpha) / len(hpoa_orpha), 3) if hpoa_orpha else 0.0,
                "hpoa_decipher_covered": len(cov_decipher),
                "n_unique_hpo_terms_used": len(used_hpos_resolved),
                "hpoa_hpo_terms_total": len(hpoa_terms),
                "hpoa_hpo_term_coverage_pct": round(100 * len(covered_hpos) / len(hpoa_terms), 3) if hpoa_terms else 0.0,
            }
        )
    return pd.DataFrame(rows)


# =====================================================================
# Per-case signal density (phenotypes per case vs annotation depth of truth)
# =====================================================================

def build_signal_density_table(
    cases_by_ds: Dict[str, List[Case]],
    disease_to_hpos: Dict[str, Set[str]],
) -> pd.DataFrame:
    rows = []
    for ds in DATASET_ORDER:
        cases = cases_by_ds.get(ds, [])
        case_pheno: List[int] = []
        disease_annot: List[int] = []
        ratios: List[float] = []
        for c in cases:
            n_pheno = len(c.hpo_pos)
            case_pheno.append(n_pheno)
            # take max annotation count across truth ids (most generous)
            annot_sizes = [
                len(disease_to_hpos.get(d, set())) for d in c.disease_ids
            ]
            if annot_sizes:
                n_annot = max(annot_sizes)
                disease_annot.append(n_annot)
                if n_annot > 0:
                    ratios.append(n_pheno / n_annot)
        rows.append(
            {
                "dataset": ds,
                "display": DATASET_DISPLAY[ds],
                "n_cases": len(cases),
                "case_hpo_mean": round(float(np.mean(case_pheno)), 2) if case_pheno else 0.0,
                "case_hpo_median": round(float(np.median(case_pheno)), 2) if case_pheno else 0.0,
                "truth_annotation_mean": round(float(np.mean(disease_annot)), 2) if disease_annot else 0.0,
                "truth_annotation_median": round(float(np.median(disease_annot)), 2) if disease_annot else 0.0,
                "coverage_ratio_mean": round(float(np.mean(ratios)), 3) if ratios else 0.0,
                "coverage_ratio_median": round(float(np.median(ratios)), 3) if ratios else 0.0,
            }
        )
    return pd.DataFrame(rows)


# =====================================================================
# Cross-dataset disease / HPO overlap
# =====================================================================

def build_pairwise_overlap(
    cases_by_ds: Dict[str, List[Case]],
    terms: Dict[str, Dict],
    alt_map: Dict[str, str],
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    diseases_by_ds: Dict[str, Set[str]] = {
        ds: {d for c in cases_by_ds.get(ds, []) for d in c.disease_ids}
        for ds in DATASET_ORDER
    }
    hpos_by_ds: Dict[str, Set[str]] = {}
    for ds in DATASET_ORDER:
        s: Set[str] = set()
        for c in cases_by_ds.get(ds, []):
            for h in c.hpo_pos:
                r = resolve_hpo(h, terms, alt_map)
                if r:
                    s.add(r)
        hpos_by_ds[ds] = s

    def jaccard(a: Set[str], b: Set[str]) -> float:
        if not a and not b:
            return 0.0
        return len(a & b) / len(a | b)

    def overlap_df(sets: Dict[str, Set[str]]) -> pd.DataFrame:
        order = DATASET_ORDER
        data = np.zeros((len(order), len(order)))
        for i, a in enumerate(order):
            for j, b in enumerate(order):
                data[i, j] = jaccard(sets[a], sets[b])
        return pd.DataFrame(data, index=order, columns=order)

    return overlap_df(diseases_by_ds), overlap_df(hpos_by_ds)


# =====================================================================
# Top-level category distribution
# =====================================================================

def build_category_distribution(
    cases_by_ds: Dict[str, List[Case]],
    terms: Dict[str, Dict],
    alt_map: Dict[str, str],
    term_to_cats: Dict[str, Set[str]],
) -> pd.DataFrame:
    cat_names: Dict[str, str] = {
        cid: terms[cid].get("name", cid)
        for cats in term_to_cats.values()
        for cid in cats
        if cid in terms
    }
    rows = []
    for ds in DATASET_ORDER:
        cases = cases_by_ds.get(ds, [])
        per_case_cats: Counter = Counter()
        total_cases = 0
        for c in cases:
            seen_cats: Set[str] = set()
            for h in c.hpo_pos:
                r = resolve_hpo(h, terms, alt_map)
                if not r:
                    continue
                for cat in term_to_cats.get(r, ()):
                    seen_cats.add(cat)
            if seen_cats:
                total_cases += 1
                for cat in seen_cats:
                    per_case_cats[cat] += 1
        row = {
            "dataset": ds,
            "display": DATASET_DISPLAY[ds],
            "n_cases_with_any_category": total_cases,
        }
        for cid, name in sorted(cat_names.items(), key=lambda kv: kv[1]):
            row[f"pct__{name}"] = round(100 * per_case_cats.get(cid, 0) / total_cases, 2) if total_cases else 0.0
        rows.append(row)
    return pd.DataFrame(rows)


# =====================================================================
# Figures
# =====================================================================

def set_style() -> None:
    sns.set_context("paper", font_scale=1.1)
    sns.set_style("whitegrid")


def plot_phenotypes_per_case(
    cases_by_ds: Dict[str, List[Case]], path: Path
) -> None:
    records = []
    for ds in DATASET_ORDER:
        for c in cases_by_ds.get(ds, []):
            records.append({"dataset": DATASET_DISPLAY[ds], "n_pos_hpo": len(c.hpo_pos)})
    df = pd.DataFrame(records)
    fig, ax = plt.subplots(figsize=(8, 4.5))
    order = [DATASET_DISPLAY[d] for d in DATASET_ORDER]
    sns.boxplot(
        data=df,
        x="dataset",
        y="n_pos_hpo",
        order=order,
        ax=ax,
        showfliers=False,
        palette="Set2",
    )
    ax.set_xlabel("")
    ax.set_ylabel("Positive HPO terms per case")
    ax.set_title("Phenotype count per case across datasets")
    plt.setp(ax.get_xticklabels(), rotation=20, ha="right")
    fig.tight_layout()
    fig.savefig(path, dpi=220)
    plt.close(fig)


def plot_ic_distribution(
    case_mean_ic_by_ds: Dict[str, List[float]], path: Path
) -> None:
    records = []
    for ds in DATASET_ORDER:
        for v in case_mean_ic_by_ds.get(ds, []):
            records.append({"dataset": DATASET_DISPLAY[ds], "mean_ic": v})
    df = pd.DataFrame(records)
    fig, ax = plt.subplots(figsize=(8, 4.5))
    order = [DATASET_DISPLAY[d] for d in DATASET_ORDER]
    sns.violinplot(
        data=df, x="dataset", y="mean_ic", order=order, ax=ax, inner="quartile",
        palette="Set2", cut=0,
    )
    ax.set_xlabel("")
    ax.set_ylabel("Mean IC of HPO terms per case")
    ax.set_title("Per-case phenotype information content")
    plt.setp(ax.get_xticklabels(), rotation=20, ha="right")
    fig.tight_layout()
    fig.savefig(path, dpi=220)
    plt.close(fig)


def plot_ontology_coverage(coverage_df: pd.DataFrame, path: Path) -> None:
    df = coverage_df.copy()
    df["display"] = df["dataset"].map(DATASET_DISPLAY)
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.3), sharey=False)
    for ax, col, title in zip(
        axes,
        ["hpoa_omim_coverage_pct", "hpoa_orpha_coverage_pct", "hpoa_hpo_term_coverage_pct"],
        ["OMIM disease coverage (%)", "ORPHANET disease coverage (%)", "HPO term coverage (%)"],
    ):
        sns.barplot(
            data=df,
            x="display",
            y=col,
            ax=ax,
            palette="Set2",
            order=[DATASET_DISPLAY[d] for d in DATASET_ORDER],
        )
        ax.set_title(title)
        ax.set_xlabel("")
        ax.set_ylabel("% of HPOA universe")
        plt.setp(ax.get_xticklabels(), rotation=25, ha="right")
        for p, v in zip(ax.patches, df[col].values):
            ax.annotate(
                f"{v:.1f}",
                (p.get_x() + p.get_width() / 2, p.get_height()),
                ha="center",
                va="bottom",
                fontsize=8,
            )
    fig.suptitle("Dataset coverage of the HPO disease ontology (phenotype.hpoa)")
    fig.tight_layout()
    fig.savefig(path, dpi=220)
    plt.close(fig)


def plot_overlap_heatmap(df: pd.DataFrame, title: str, path: Path) -> None:
    labels = [DATASET_DISPLAY[d] for d in df.index]
    fig, ax = plt.subplots(figsize=(6.5, 5.5))
    sns.heatmap(
        df.values,
        annot=True,
        fmt=".2f",
        xticklabels=labels,
        yticklabels=labels,
        cmap="viridis",
        vmin=0,
        vmax=1,
        ax=ax,
        cbar_kws={"label": "Jaccard"},
    )
    ax.set_title(title)
    plt.setp(ax.get_xticklabels(), rotation=25, ha="right")
    plt.setp(ax.get_yticklabels(), rotation=0)
    fig.tight_layout()
    fig.savefig(path, dpi=220)
    plt.close(fig)


def plot_category_heatmap(df: pd.DataFrame, path: Path) -> None:
    cat_cols = [c for c in df.columns if c.startswith("pct__")]
    if not cat_cols:
        return
    mat = df.set_index("display")[cat_cols].copy()
    mat.columns = [c.replace("pct__", "") for c in cat_cols]
    # sort columns by mean frequency
    col_order = mat.mean(axis=0).sort_values(ascending=False).index.tolist()
    mat = mat[col_order]
    fig, ax = plt.subplots(figsize=(max(10, 0.4 * len(col_order)), 4.5))
    sns.heatmap(
        mat.values,
        annot=False,
        cmap="magma",
        xticklabels=col_order,
        yticklabels=mat.index,
        ax=ax,
        cbar_kws={"label": "% of cases with ≥1 term in category"},
    )
    ax.set_title("Top-level HPO category presence per case, by dataset")
    plt.setp(ax.get_xticklabels(), rotation=55, ha="right")
    fig.tight_layout()
    fig.savefig(path, dpi=220)
    plt.close(fig)


def plot_signal_density(sig_df: pd.DataFrame, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(8, 4.5))
    labels = sig_df["display"].tolist()
    x = np.arange(len(labels))
    width = 0.38
    ax.bar(x - width / 2, sig_df["case_hpo_mean"], width, label="Mean HPOs per case", color="#4C72B0")
    ax.bar(x + width / 2, sig_df["truth_annotation_mean"], width, label="Mean HPOs annotated on truth disease", color="#DD8452")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=20, ha="right")
    ax.set_ylabel("Number of HPO terms")
    ax.set_title("Case phenotype signal vs truth-disease annotation depth")
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=220)
    plt.close(fig)


# =====================================================================
# Markdown summary
# =====================================================================

def write_summary_md(
    overview_df: pd.DataFrame,
    phen_df: pd.DataFrame,
    spec_df: pd.DataFrame,
    coverage_df: pd.DataFrame,
    sig_df: pd.DataFrame,
    disease_overlap: pd.DataFrame,
    hpo_overlap: pd.DataFrame,
    category_df: pd.DataFrame,
    hpoa_diseases: Dict[str, Set[str]],
    hpoa_term_total: int,
    path: Path,
) -> None:
    lines: List[str] = []
    lines.append("# Dataset Characterization for BioNLP @ ACL 2026 Paper")
    lines.append("")
    lines.append("*Generated: 2026-04-10 by `run_analysis.py`*")
    lines.append("")
    lines.append(
        "Compares Phenopacket (all and 6,901 phenodp-compatible subset), "
        "RAMEDIS, LIRICAL, HMS, and MME against the complete HPO disease "
        "ontology (phenotype.hpoa, hp-version 2025-09-01)."
    )
    lines.append("")
    lines.append("## Reference ontology")
    lines.append("")
    omim_n = sum(1 for d in hpoa_diseases if namespace_of(d) == "OMIM")
    orpha_n = sum(1 for d in hpoa_diseases if namespace_of(d) == "ORPHA")
    decipher_n = sum(1 for d in hpoa_diseases if namespace_of(d) == "DECIPHER")
    lines.append(
        f"- phenotype.hpoa contains **{len(hpoa_diseases):,}** rare diseases with phenotype (P aspect) annotations "
        f"({omim_n:,} OMIM, {orpha_n:,} ORPHANET, {decipher_n:,} DECIPHER)."
    )
    lines.append(f"- **{hpoa_term_total:,}** distinct HPO terms are used across those annotations.")
    lines.append("")
    lines.append("---")
    lines.append("## 1. Per-dataset overview  →  Paper Section 2 (Experimental Setup)")
    lines.append("")
    lines.append(
        "Cells report per-dataset counts and phenotype/disease distributions. "
        "The origin column reflects the paper's categorization (Literature / "
        "Structured / Clinical) and is validated by the namespace and phenotype-"
        "count distributions below."
    )
    lines.append("")
    lines.append(overview_df.to_markdown(index=False))
    lines.append("")
    lines.append("### Phenotype count per case  →  supports dataset-sensitivity argument")
    lines.append("")
    lines.append(phen_df.to_markdown(index=False))
    lines.append("")
    lines.append(
        "*Interpretation cue:* datasets with low median phenotype counts "
        "have weaker retrieval signal per case. Compare the medians against "
        "the paper's per-dataset Hit@1 numbers."
    )
    lines.append("")
    lines.append("---")
    lines.append("## 2. HPO term specificity  →  reviewer-anticipated ablation")
    lines.append("")
    lines.append(
        "`term_depth` = shortest distance from HP:0000118 (Phenotypic abnormality). "
        "`term_ic` = Shannon IC computed from propagated frequencies over the "
        f"{len(hpoa_diseases):,} annotated diseases. Higher depth / IC = more "
        "specific phenotypes."
    )
    lines.append("")
    lines.append(spec_df.to_markdown(index=False))
    lines.append("")
    lines.append(
        "*Interpretation cue:* if MME / HMS use shallower or lower-IC terms than "
        "RAMEDIS, that is a plausible structural reason for the 20× dataset-"
        "sensitivity swing and belongs in the Discussion."
    )
    lines.append("")
    lines.append("---")
    lines.append("## 3. Ontology coverage  →  Section 2 one-sentence framing")
    lines.append("")
    lines.append(coverage_df.to_markdown(index=False))
    lines.append("")
    lines.append(
        "*Interpretation cue:* coverage of the hpoa universe tells the reader "
        "how representative each benchmark is of the true rare-disease long "
        "tail. A benchmark that covers <5% of OMIM is a narrow slice."
    )
    lines.append("")
    lines.append("---")
    lines.append("## 4. Signal density (case HPOs vs truth annotation depth)")
    lines.append("")
    lines.append(sig_df.to_markdown(index=False))
    lines.append("")
    lines.append(
        "*Interpretation cue:* `coverage_ratio` = fraction of the truth "
        "disease's hpoa annotation that is actually observed in the case. "
        "Low ratio = the case only mentions a handful of the phenotypes "
        "that typically define the disease — harder for any retriever."
    )
    lines.append("")
    lines.append("---")
    lines.append("## 5. Cross-dataset overlap  →  benchmark-independence check")
    lines.append("")
    lines.append("### Truth-disease Jaccard overlap")
    lines.append("")
    lines.append(disease_overlap.round(3).to_markdown())
    lines.append("")
    lines.append("### Observed HPO-term Jaccard overlap")
    lines.append("")
    lines.append(hpo_overlap.round(3).to_markdown())
    lines.append("")
    lines.append(
        "*Interpretation cue:* low truth-disease overlap supports the claim "
        "that these datasets are independent benchmarks; high HPO-term overlap "
        "is expected because HPO vocabulary is shared even when diseases differ."
    )
    lines.append("")
    lines.append("---")
    lines.append("## 6. Top-level HPO category distribution")
    lines.append("")
    lines.append(category_df.to_markdown(index=False))
    lines.append("")
    lines.append(
        "*Interpretation cue:* category profiles reveal organ-system bias. If "
        "all datasets look similar here, report it as a null result; if MME and "
        "HMS concentrate on a narrow set of categories, that is a publishable "
        "finding."
    )
    lines.append("")
    lines.append("---")
    lines.append("## Figures")
    lines.append("")
    for name, caption in [
        ("fig_phenotypes_per_case.png", "Phenotype count per case across datasets (boxplot)."),
        ("fig_hpo_ic_distribution.png", "Per-case mean HPO information content (violin)."),
        ("fig_ontology_coverage.png", "Coverage of the hpoa disease+HPO-term universe per dataset."),
        ("fig_disease_overlap_heatmap.png", "Pairwise Jaccard overlap of truth-disease sets."),
        ("fig_hpo_overlap_heatmap.png", "Pairwise Jaccard overlap of observed HPO-term sets."),
        ("fig_category_heatmap.png", "Top-level HPO category presence per case per dataset."),
        ("fig_signal_density.png", "Per-case HPO count vs truth-disease hpoa annotation depth."),
    ]:
        lines.append(f"- **{name}** — {caption}")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


# =====================================================================
# Main
# =====================================================================

def main() -> None:
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    set_style()

    # --- HPO ontology ---
    log.info("parsing HPO ontology...")
    terms, alt_map = parse_hp_obo(HP_OBO)
    log.info("computing ancestor closure...")
    ancestors = compute_ancestors(terms)
    log.info("computing depths from HP:0000118...")
    depths = compute_depths_from_root(terms, PHENO_ABNORMALITY_ROOT)
    log.info("computing top-level categories...")
    term_to_cats = compute_top_categories(terms, ancestors, PHENO_ABNORMALITY_ROOT)

    # --- hpoa ---
    log.info("loading phenotype.hpoa...")
    disease_to_hpos = load_hpoa(PHENOTYPE_HPOA)
    log.info("propagating annotations...")
    propagated = propagate_annotations(disease_to_hpos, ancestors)
    log.info("computing IC...")
    ic = compute_ic(propagated)
    hpoa_term_universe: Set[str] = set()
    for s in disease_to_hpos.values():
        hpoa_term_universe.update(s)

    # --- datasets ---
    log.info("loading phenopacket (all)...")
    pp_all = load_phenopacket_cases(PHENOPACKET_DIR, "phenopacket_all")
    log.info("loading phenopacket (6,901)...")
    benchmark_ids = load_benchmark_ids(BENCHMARK_IDS)
    pp_6901 = [Case(**{**c.__dict__, "dataset": "phenopacket_6901"})
               for c in pp_all if c.case_id in benchmark_ids]
    log.info("  phenopacket_6901: %d cases (benchmark_ids has %d ids)", len(pp_6901), len(benchmark_ids))

    cases_by_ds: Dict[str, List[Case]] = {
        "phenopacket_all": pp_all,
        "phenopacket_6901": pp_6901,
    }
    for ds in ("RAMEDIS", "LIRICAL", "HMS", "MME"):
        cases_by_ds[ds] = load_rarebench_cases(RAREBENCH_DIR / f"{ds}.jsonl", ds)

    # --- per-dataset overview ---
    log.info("building per-dataset overview...")
    overview_rows = [
        build_overview_row(cases_by_ds[ds], ds, terms, alt_map) for ds in DATASET_ORDER
    ]
    overview_df = pd.DataFrame(overview_rows)
    overview_df.to_csv(TABLES_DIR / "table_per_dataset_overview.csv", index=False)

    phen_df = build_phenotype_count_table(cases_by_ds)
    phen_df.to_csv(TABLES_DIR / "table_phenotype_counts.csv", index=False)

    spec_df, case_mean_ic_by_ds, case_mean_depth_by_ds = build_specificity_table(
        cases_by_ds, terms, alt_map, depths, ic
    )
    spec_df.to_csv(TABLES_DIR / "table_hpo_specificity.csv", index=False)

    coverage_df = build_coverage_table(cases_by_ds, disease_to_hpos, terms, alt_map)
    coverage_df.to_csv(TABLES_DIR / "table_ontology_coverage.csv", index=False)

    sig_df = build_signal_density_table(cases_by_ds, disease_to_hpos)
    sig_df.to_csv(TABLES_DIR / "table_signal_density.csv", index=False)

    disease_overlap, hpo_overlap = build_pairwise_overlap(cases_by_ds, terms, alt_map)
    disease_overlap.to_csv(TABLES_DIR / "table_disease_overlap_jaccard.csv")
    hpo_overlap.to_csv(TABLES_DIR / "table_hpo_overlap_jaccard.csv")

    category_df = build_category_distribution(cases_by_ds, terms, alt_map, term_to_cats)
    category_df.to_csv(TABLES_DIR / "table_category_distribution.csv", index=False)

    # --- figures ---
    log.info("rendering figures...")
    plot_phenotypes_per_case(cases_by_ds, FIGURES_DIR / "fig_phenotypes_per_case.png")
    plot_ic_distribution(case_mean_ic_by_ds, FIGURES_DIR / "fig_hpo_ic_distribution.png")
    plot_ontology_coverage(coverage_df, FIGURES_DIR / "fig_ontology_coverage.png")
    plot_overlap_heatmap(
        disease_overlap,
        "Pairwise truth-disease Jaccard overlap",
        FIGURES_DIR / "fig_disease_overlap_heatmap.png",
    )
    plot_overlap_heatmap(
        hpo_overlap,
        "Pairwise observed HPO-term Jaccard overlap",
        FIGURES_DIR / "fig_hpo_overlap_heatmap.png",
    )
    plot_category_heatmap(category_df, FIGURES_DIR / "fig_category_heatmap.png")
    plot_signal_density(sig_df, FIGURES_DIR / "fig_signal_density.png")

    # --- summary ---
    log.info("writing summary.md...")
    write_summary_md(
        overview_df=overview_df,
        phen_df=phen_df,
        spec_df=spec_df,
        coverage_df=coverage_df,
        sig_df=sig_df,
        disease_overlap=disease_overlap,
        hpo_overlap=hpo_overlap,
        category_df=category_df,
        hpoa_diseases=disease_to_hpos,
        hpoa_term_total=len(hpoa_term_universe),
        path=OUT_DIR / "summary.md",
    )
    log.info("done. results in %s", OUT_DIR)


if __name__ == "__main__":
    main()
