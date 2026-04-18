from __future__ import annotations

import json
import os
import re
import shutil
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from tqdm.auto import tqdm

from .data_loader import load_phenopackets
from .hpo_annotations import HPOAnnotationStore
from .io_utils import read_jsonl, write_csv, write_jsonl, write_markdown_examples
from .metrics import CRITERIA, KS, evaluate_ranked_items, summarize_evaluations
from .models import DiseaseCandidate, PatientCase, Truth
from .phenodp_retriever import PhenoDPOptions, PhenoDPRetriever
from .prompting import PromptOptions
from .rerankers import GemmaReranker, LLMOptions, VLLM_AVAILABLE
from .utils import capture_environment, configure_logging, ensure_dir, make_run_dir, read_lines, seed_everything, write_json


@dataclass
class RunConfig:
    run_name: str
    data_dir: str
    output_root: str
    phenodp_repo_root: str
    phenodp_data_dir: str
    phenodp_hpo_dir: str
    llm_options: LLMOptions
    prompt_options: PromptOptions = field(default_factory=PromptOptions)
    retrieve_k: int = 50
    rerank_cutoffs: List[int] = field(default_factory=lambda: [3, 5, 10])
    llm_batch_size: int = 8
    seed: int = 42
    max_cases: Optional[int] = None
    benchmark_ids_path: Optional[str] = None
    min_phenotypes: int = 1
    include_excluded_phenotypes: bool = False
    skip_rerank: bool = False
    qualitative_examples_n: int = 5
    phenodp_ic_type: str = "omim"
    phenodp_device: str = "cpu"
    stage: str = "all"
    resume_run_dir: Optional[str] = None
    retrieval_precision_recall_rescoring: bool = False
    retrieval_recall_weight: float = 1.0
    retrieval_precision_penalty_weight: float = 0.5


def _select_benchmark_ids(dataset: Sequence[Dict[str, Any]], max_cases: Optional[int]) -> List[str]:
    patient_ids = sorted(row["case"].patient_id for row in dataset)
    if max_cases is None or max_cases >= len(patient_ids):
        return patient_ids
    return patient_ids[: int(max_cases)]


def _safe_id(value: str) -> str:
    return "".join(char for char in value if char.isalnum() or char in ("-", "_"))


def _candidate_ranked_items(candidates: Sequence[DiseaseCandidate]) -> List[Dict[str, Any]]:
    return [{"id": candidate.disease_id, "name": candidate.disease_name} for candidate in candidates]


def _serialize_candidate_records(dataset: Sequence[Dict[str, Any]], candidates_list: Sequence[Sequence[DiseaseCandidate]]) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for row, candidates in zip(dataset, candidates_list):
        case: PatientCase = row["case"]
        truth: Truth = row["truth"]
        records.append(
            {
                "patient_id": case.patient_id,
                "truth_ids": truth.disease_ids,
                "truth_labels": truth.disease_labels,
                "phenotype_ids": case.phenotype_ids,
                "phenotype_labels": case.phenotype_labels,
                "negative_phenotype_ids": case.neg_phenotype_ids,
                "negative_phenotype_labels": case.neg_phenotype_labels,
                "genes": case.genes,
                "candidates": [candidate.to_json() for candidate in candidates],
            }
        )
    return records


def _flatten_case_metrics(metrics: Dict[str, Dict[str, float]]) -> Dict[str, Any]:
    flat: Dict[str, Any] = {}
    for criterion in CRITERIA:
        criterion_metrics = metrics.get(criterion, {})
        flat[f"{criterion}_rank"] = int(criterion_metrics.get("rank", 0.0) or 0.0)
        flat[f"{criterion}_found"] = int(criterion_metrics.get("found", 0.0) or 0.0)
        flat[f"{criterion}_mrr"] = float(criterion_metrics.get("mrr", 0.0))
        for k in KS:
            flat[f"{criterion}_hit_{k}"] = float(criterion_metrics.get(f"hit@{k}", 0.0))
    return flat


def _flatten_summary_row(summary: Dict[str, Any]) -> Dict[str, Any]:
    row = {
        "stage": summary["stage"],
        "method": summary["method"],
        "status": summary["status"],
        "n_cases": int(summary["n_cases"]),
    }
    for criterion in CRITERIA:
        criterion_summary = summary["criteria"].get(criterion, {})
        row[f"{criterion}_mrr"] = float(criterion_summary.get("mrr", 0.0))
        row[f"{criterion}_found"] = float(criterion_summary.get("found", 0.0))
        for k in KS:
            row[f"{criterion}_hit_{k}"] = float(criterion_summary.get(f"hit@{k}", 0.0))
    return row


def _build_stage_summary(stage: str, method: str, status: str, per_case_metrics: Sequence[Dict[str, Dict[str, float]]]) -> Dict[str, Any]:
    return {
        "stage": stage,
        "method": method,
        "status": status,
        "n_cases": len(per_case_metrics),
        "criteria": summarize_evaluations(per_case_metrics),
        "notes": {
            "name_match_rule": "normalized exact match or rapidfuzz token_set_ratio >= 95",
            "criteria": {
                "id_correct": "predicted ID matches any truth ID",
                "id_and_name_correct": "predicted ID matches any truth ID and predicted name matches a truth name",
                "id_or_name_correct": "predicted ID matches any truth ID or predicted name matches a truth name",
            },
        },
    }


def _load_existing_benchmark_rows(run_dir: str | Path) -> List[Dict[str, Any]]:
    summary_path = Path(run_dir) / "benchmark_summary.json"
    if not summary_path.exists():
        return []
    try:
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
    except Exception:
        return []
    rows = payload.get("rows")
    if not isinstance(rows, list):
        return []
    return [dict(row) for row in rows if isinstance(row, dict)]


def _upsert_benchmark_row(rows: List[Dict[str, Any]], row: Dict[str, Any]) -> None:
    stage = str(row.get("stage") or "")
    method = str(row.get("method") or "")
    for index, existing in enumerate(rows):
        if str(existing.get("stage") or "") == stage and str(existing.get("method") or "") == method:
            rows[index] = row
            return
    rows.append(row)


def _load_retrieval_candidates(
    shared_candidates_path: str | Path,
    dataset: Sequence[Dict[str, Any]],
) -> List[List[DiseaseCandidate]]:
    records = read_jsonl(str(shared_candidates_path))
    records_by_patient_id = {
        str(record.get("patient_id") or ""): record for record in records if record.get("patient_id")
    }
    retrieval_candidates: List[List[DiseaseCandidate]] = []
    missing_patient_ids: List[str] = []
    for row in dataset:
        patient_id = row["case"].patient_id
        record = records_by_patient_id.get(patient_id)
        if record is None:
            missing_patient_ids.append(patient_id)
            retrieval_candidates.append([])
            continue
        retrieval_candidates.append(
            [DiseaseCandidate.from_json(candidate) for candidate in (record.get("candidates") or [])]
        )
    if missing_patient_ids:
        raise FileNotFoundError(
            f"Missing retrieval candidates for {len(missing_patient_ids)} cases, "
            f"for example: {', '.join(missing_patient_ids[:5])}"
        )
    return retrieval_candidates


def run_pipeline(cfg: RunConfig, verbose: bool = True) -> str:
    seed_everything(cfg.seed)

    if cfg.resume_run_dir:
        run_dir = ensure_dir(cfg.resume_run_dir)
    else:
        run_dir = make_run_dir(cfg.output_root, cfg.run_name)
    logger = configure_logging(Path(run_dir) / "run.log", verbose=verbose)

    if cfg.resume_run_dir:
        write_json(Path(run_dir) / f"environment_{cfg.stage}.json", capture_environment())
        write_json(Path(run_dir) / f"run_config_{cfg.stage}.json", asdict(cfg))
    else:
        write_json(Path(run_dir) / "environment.json", capture_environment())
        write_json(Path(run_dir) / "run_config.json", asdict(cfg))

    dataset = load_phenopackets(
        cfg.data_dir,
        logger=logger,
        include_excluded_phenotypes=cfg.include_excluded_phenotypes,
        min_phenotypes=cfg.min_phenotypes,
    )

    if cfg.benchmark_ids_path:
        benchmark_ids = sorted(read_lines(cfg.benchmark_ids_path))
    else:
        benchmark_ids = _select_benchmark_ids(dataset, cfg.max_cases)
    benchmark_id_set = set(benchmark_ids)
    dataset = [row for row in dataset if row["case"].patient_id in benchmark_id_set]
    dataset.sort(key=lambda row: row["case"].patient_id)
    Path(run_dir, "benchmark_ids.txt").write_text("\n".join(benchmark_ids) + "\n", encoding="utf-8")

    logger.info("Benchmark cases: %d", len(dataset))

    candidate_sets_root = Path(run_dir) / "candidate_sets"
    methods_root = Path(run_dir) / "methods"
    ensure_dir(candidate_sets_root)
    ensure_dir(methods_root)
    shared_candidates_path = candidate_sets_root / f"phenodp_candidates_top{cfg.retrieve_k}.jsonl"
    retrieval_method = f"retriever_phenodp_top{cfg.retrieve_k}"
    retrieval_dir = methods_root / retrieval_method

    benchmark_rows: List[Dict[str, Any]] = _load_existing_benchmark_rows(run_dir)
    retrieval_candidates: List[List[DiseaseCandidate]]

    if cfg.stage in ("all", "retrieve"):
        retriever = PhenoDPRetriever(
            PhenoDPOptions(
                phenodp_repo_root=cfg.phenodp_repo_root,
                phenodp_data_dir=cfg.phenodp_data_dir,
                phenodp_hpo_dir=cfg.phenodp_hpo_dir,
                ic_type=cfg.phenodp_ic_type,
                device=cfg.phenodp_device,
                candidate_pool_size=max(200, int(cfg.retrieve_k)),
            )
        )

        # Load annotations for precision-recall rescoring if enabled
        retrieval_ann_store = None
        if cfg.retrieval_precision_recall_rescoring:
            hpoa_path = Path(cfg.phenodp_hpo_dir) / "phenotype.hpoa"
            if not hpoa_path.exists():
                hpoa_path = Path(cfg.data_dir).parent / "phenotype.hpoa"
            if hpoa_path.exists():
                logger.info("Loading HPO annotations for precision-recall rescoring from %s", hpoa_path)
                retrieval_ann_store = HPOAnnotationStore.from_hpoa_file(hpoa_path)
            else:
                logger.warning("Precision-recall rescoring requested but phenotype.hpoa not found at %s", hpoa_path)

        logger.info("Running PhenoDP retrieval for top-%d candidates per case", cfg.retrieve_k)
        retrieval_candidates = []
        for row in tqdm(dataset, desc="Retrieval/PhenoDP"):
            case: PatientCase = row["case"]
            retrieval_candidates.append(
                retriever.retrieve(
                    case.phenotype_ids,
                    top_k=cfg.retrieve_k,
                    annotation_store=retrieval_ann_store,
                    precision_recall_rescoring=cfg.retrieval_precision_recall_rescoring,
                    recall_weight=cfg.retrieval_recall_weight,
                    precision_penalty_weight=cfg.retrieval_precision_penalty_weight,
                )
            )

        candidate_records = _serialize_candidate_records(dataset, retrieval_candidates)
        write_jsonl(str(shared_candidates_path), candidate_records)

        ensure_dir(retrieval_dir)
        shutil.copyfile(shared_candidates_path, retrieval_dir / "candidates.jsonl")

        retrieval_results: List[Dict[str, Any]] = []
        retrieval_case_metrics: List[Dict[str, Dict[str, float]]] = []
        retrieval_pred_columns = max(10, min(int(cfg.retrieve_k), 10))

        for row, candidates in zip(dataset, retrieval_candidates):
            case: PatientCase = row["case"]
            truth: Truth = row["truth"]
            ranked_items = _candidate_ranked_items(candidates)
            metrics = evaluate_ranked_items(ranked_items, truth.disease_ids, truth.disease_labels)
            retrieval_case_metrics.append(metrics)

            result_row: Dict[str, Any] = {
                "patient_id": case.patient_id,
                "truth_ids": "|".join(truth.disease_ids),
                "truth_labels": "|".join(truth.disease_labels),
                "retrieved_ids": "|".join(candidate.disease_id for candidate in candidates),
                "retrieved_names": "|".join(candidate.disease_name for candidate in candidates),
                **_flatten_case_metrics(metrics),
            }
            for index in range(retrieval_pred_columns):
                if index < len(candidates):
                    candidate = candidates[index]
                    result_row[f"pred{index + 1}_id"] = candidate.disease_id
                    result_row[f"pred{index + 1}_name"] = candidate.disease_name
                    result_row[f"pred{index + 1}_score"] = float(candidate.score)
                else:
                    result_row[f"pred{index + 1}_id"] = ""
                    result_row[f"pred{index + 1}_name"] = ""
                    result_row[f"pred{index + 1}_score"] = 0.0
            retrieval_results.append(result_row)

        retrieval_summary = _build_stage_summary(
            stage="retriever",
            method=retrieval_method,
            status="completed",
            per_case_metrics=retrieval_case_metrics,
        )
        write_csv(str(retrieval_dir / "results.csv"), retrieval_results)
        write_json(retrieval_dir / "summary.json", retrieval_summary)
        _upsert_benchmark_row(benchmark_rows, _flatten_summary_row(retrieval_summary))
    else:
        logger.info("Loading cached retrieval candidates from %s", shared_candidates_path)
        retrieval_candidates = _load_retrieval_candidates(shared_candidates_path, dataset)

    if cfg.stage == "retrieve":
        logger.info("Stopping after retrieval stage because --stage retrieve was requested.")
    elif cfg.skip_rerank:
        logger.info("Skipping reranker stage because --skip-rerank was requested.")
    elif not VLLM_AVAILABLE:
        logger.warning("Skipping reranker stage because vLLM is unavailable.")
    else:
        # Load HPO annotations if requested
        annotation_store = None
        hpo_names: Dict[str, str] = {}
        if cfg.prompt_options.include_hpo_annotations:
            hpoa_path = Path(cfg.phenodp_hpo_dir) / "phenotype.hpoa"
            if not hpoa_path.exists():
                hpoa_path = Path(cfg.data_dir).parent / "phenotype.hpoa"
            if hpoa_path.exists():
                logger.info("Loading HPO annotations from %s", hpoa_path)
                annotation_store = HPOAnnotationStore.from_hpoa_file(hpoa_path)
                try:
                    from pyhpo import Ontology
                    Ontology()
                    hpo_names = {term.id: term.name for term in Ontology}
                    logger.info("Loaded %d HPO term names", len(hpo_names))
                except Exception:
                    logger.warning("Could not load HPO term names from pyhpo; using HPO IDs instead")
            else:
                logger.warning("HPO annotations requested but phenotype.hpoa not found at %s", hpoa_path)

        rerank_cutoffs = sorted({cutoff for cutoff in cfg.rerank_cutoffs if cutoff > 0})
        for cutoff in rerank_cutoffs:
            method_name = f"reranker_gemma3_top{cutoff}"
            method_dir = methods_root / method_name
            logs_dir = method_dir / "logs"
            ensure_dir(method_dir)
            ensure_dir(logs_dir)
            shutil.copyfile(shared_candidates_path, method_dir / "candidates.jsonl")

            prompt_opts = replace(
                cfg.prompt_options,
                output_top_k=min(int(cutoff), int(cfg.prompt_options.output_top_k), int(cutoff)),
                candidate_count_in_prompt=int(cutoff),
            )
            prompt_opts.output_top_k = int(cutoff)
            reranker = GemmaReranker(
                cfg.llm_options,
                prompt_opts,
                batch_size=cfg.llm_batch_size,
                annotation_store=annotation_store,
                hpo_names=hpo_names,
            )

            rerank_results: List[Dict[str, Any]] = []
            rerank_case_metrics: List[Dict[str, Dict[str, float]]] = []
            examples: List[Dict[str, Any]] = []

            # Resume: skip cases whose log files already exist, reconstruct their results
            already_done: set = {f.stem for f in logs_dir.iterdir() if f.suffix == ".txt"}
            if already_done:
                logger.info(
                    "Resuming top%d: %d/%d cases already processed — loading from logs",
                    cutoff, len(already_done), len(dataset),
                )
                for row, candidates_full in zip(dataset, retrieval_candidates):
                    case: PatientCase = row["case"]
                    truth: Truth = row["truth"]
                    if _safe_id(case.patient_id) not in already_done:
                        continue
                    candidates = candidates_full[:cutoff]
                    log_txt = (logs_dir / f"{_safe_id(case.patient_id)}.txt").read_text(encoding="utf-8")
                    raw_out = log_txt.split("RAW OUTPUT:", 1)[1].strip() if "RAW OUTPUT:" in log_txt else ""
                    # Parse JSON ranking from raw output
                    match = re.search(r'\{[\s\S]*?"ranking"\s*:\s*\[[\s\S]*?\]\s*\}', raw_out)
                    if match:
                        try:
                            parsed = json.loads(match.group())
                        except Exception:
                            parsed = {}
                    else:
                        parsed = {}
                    ranking = parsed.get("ranking") or []
                    selected_candidate = parsed.get("selected_candidate") or {}
                    metrics = evaluate_ranked_items(ranking, truth.disease_ids, truth.disease_labels)
                    rerank_case_metrics.append(metrics)
                    result_row: Dict[str, Any] = {
                        "patient_id": case.patient_id,
                        "truth_ids": "|".join(truth.disease_ids),
                        "truth_labels": "|".join(truth.disease_labels),
                        "candidate_cutoff": int(cutoff),
                        "parse_mode": parsed.get("parse_mode", "resumed"),
                        "selected_candidate_id": str(selected_candidate.get("id") or ""),
                        "selected_candidate_name": str(selected_candidate.get("name") or ""),
                        "retrieved_ids": "|".join(candidate.disease_id for candidate in candidates),
                        "retrieved_names": "|".join(candidate.disease_name for candidate in candidates),
                        "ranked_ids": "|".join(str(item.get("id") or "") for item in ranking),
                        "ranked_names": "|".join(str(item.get("name") or "") for item in ranking),
                        **_flatten_case_metrics(metrics),
                    }
                    for pred_index in range(int(cutoff)):
                        if pred_index < len(ranking):
                            item = ranking[pred_index]
                            result_row[f"pred{pred_index + 1}_id"] = str(item.get("id") or "")
                            result_row[f"pred{pred_index + 1}_name"] = str(item.get("name") or "")
                            result_row[f"pred{pred_index + 1}_source"] = str(item.get("source") or "")
                        else:
                            result_row[f"pred{pred_index + 1}_id"] = ""
                            result_row[f"pred{pred_index + 1}_name"] = ""
                            result_row[f"pred{pred_index + 1}_source"] = ""
                    rerank_results.append(result_row)

            # Filter dataset to only cases not yet processed
            pending_pairs = [
                (row, cands)
                for row, cands in zip(dataset, retrieval_candidates)
                if _safe_id(row["case"].patient_id) not in already_done
            ]
            logger.info("top%d: %d cases to process", cutoff, len(pending_pairs))

            pending_rows = [p[0] for p in pending_pairs]
            pending_cands = [p[1] for p in pending_pairs]

            for start in tqdm(range(0, len(pending_rows), int(reranker.batch_size)), desc=f"Rerank/top{cutoff}"):
                batch_rows = pending_rows[start : start + int(reranker.batch_size)]
                batch_cases = [row["case"] for row in batch_rows]
                batch_candidates = [candidates[:cutoff] for candidates in pending_cands[start : start + int(reranker.batch_size)]]
                parsed_outputs, plain_prompts = reranker.rerank_batch(batch_cases, batch_candidates)

                for local_index, (row, candidates, parsed_output, prompt_text) in enumerate(
                    zip(batch_rows, batch_candidates, parsed_outputs, plain_prompts)
                ):
                    case: PatientCase = row["case"]
                    truth: Truth = row["truth"]
                    ranking = parsed_output.get("ranking") or []
                    metrics = evaluate_ranked_items(ranking, truth.disease_ids, truth.disease_labels)
                    rerank_case_metrics.append(metrics)

                    safe_case_id = _safe_id(case.patient_id)
                    (logs_dir / f"{safe_case_id}.txt").write_text(
                        f"PROMPT:\n{prompt_text}\n\nRAW OUTPUT:\n{parsed_output.get('raw_output', '')}\n",
                        encoding="utf-8",
                    )

                    selected_candidate = parsed_output.get("selected_candidate") or {}
                    result_row = {
                        "patient_id": case.patient_id,
                        "truth_ids": "|".join(truth.disease_ids),
                        "truth_labels": "|".join(truth.disease_labels),
                        "candidate_cutoff": int(cutoff),
                        "parse_mode": parsed_output.get("parse_mode", ""),
                        "selected_candidate_id": str(selected_candidate.get("id") or ""),
                        "selected_candidate_name": str(selected_candidate.get("name") or ""),
                        "retrieved_ids": "|".join(candidate.disease_id for candidate in candidates),
                        "retrieved_names": "|".join(candidate.disease_name for candidate in candidates),
                        "ranked_ids": "|".join(str(item.get("id") or "") for item in ranking),
                        "ranked_names": "|".join(str(item.get("name") or "") for item in ranking),
                        **_flatten_case_metrics(metrics),
                    }
                    for pred_index in range(int(cutoff)):
                        if pred_index < len(ranking):
                            item = ranking[pred_index]
                            result_row[f"pred{pred_index + 1}_id"] = str(item.get("id") or "")
                            result_row[f"pred{pred_index + 1}_name"] = str(item.get("name") or "")
                            result_row[f"pred{pred_index + 1}_source"] = str(item.get("source") or "")
                        else:
                            result_row[f"pred{pred_index + 1}_id"] = ""
                            result_row[f"pred{pred_index + 1}_name"] = ""
                            result_row[f"pred{pred_index + 1}_source"] = ""
                    rerank_results.append(result_row)

                    if len(examples) < int(cfg.qualitative_examples_n):
                        examples.append(
                            {
                                "patient_id": case.patient_id,
                                "truth_ids": "|".join(truth.disease_ids),
                                "prompt": prompt_text,
                                "raw_output": parsed_output.get("raw_output", ""),
                                "parsed_output": {
                                    "selected_candidate": selected_candidate,
                                    "ranking": ranking,
                                    "parse_mode": parsed_output.get("parse_mode", ""),
                                },
                            }
                        )

            rerank_summary = _build_stage_summary(
                stage="reranker",
                method=method_name,
                status="completed",
                per_case_metrics=rerank_case_metrics,
            )
            rerank_summary["candidate_cutoff"] = int(cutoff)
            rerank_summary["model"] = cfg.llm_options.model

            write_csv(str(method_dir / "results.csv"), rerank_results)
            write_json(method_dir / "summary.json", rerank_summary)
            write_markdown_examples(str(method_dir / "qualitative_examples.md"), examples)
            _upsert_benchmark_row(benchmark_rows, _flatten_summary_row(rerank_summary))

    write_csv(str(Path(run_dir) / "benchmark_summary.csv"), benchmark_rows)
    write_json(Path(run_dir) / "benchmark_summary.json", {"rows": benchmark_rows})

    logger.info("Run directory: %s", run_dir)
    return run_dir
