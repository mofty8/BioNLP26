#!/usr/bin/env python3
"""Evaluate Gemma-3-27b on PP2Prompt free-form prompts for cases
where truth is NOT in the PhenoDP top-10 retrieval window.

Sends each clinical narrative to the LLM and checks whether the
truth disease name appears in the ranked differential diagnosis.
"""
from __future__ import annotations

import csv
import json
import os
import re
import time
import concurrent.futures as _cf
from pathlib import Path

from openai import OpenAI
from tqdm import tqdm

# ── Config ────────────────────────────────────────────────────────────────────
API_BASE   = "http://127.0.0.1:8000/v1"
API_KEY    = "local-token"
API_MODEL  = "google/gemma-3-27b-it"
MAX_TOKENS = 800
MAX_WORKERS = 16

PROMPT_DIR     = Path("/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/PP2Prompt/prompts/en")
NOT_IN_TOP10   = Path("/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/phenodp_gemma3_candidate_ranking/not_in_top10_ids.txt")
CANDIDATES_JSONL = Path("/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/phenodp_gemma3_candidate_ranking/runs/phenodp_medllama70b_v7_full_rerank_20260405_104044/methods/reranker_medllama70b_top10/candidates.jsonl")
RESULTS_CSV    = Path("/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/phenodp_gemma3_candidate_ranking/runs/phenodp_medllama70b_v7_full_rerank_20260405_104044/methods/reranker_medllama70b_top10/results.csv")
OUTPUT_DIR     = Path("/vol/home-vol3/wbi/elmoftym/Mofty/PhenoPacket/phenodp_gemma3_candidate_ranking/runs/pp2prompt_gemma3_eval")


# ── Helpers ───────────────────────────────────────────────────────────────────

def normalize_id(pid: str) -> str:
    return re.sub(r'[-/\s]', '_', pid).lower()


def load_matched_cases():
    ids = [l for l in NOT_IN_TOP10.read_text().splitlines() if l]
    prompt_files = {f: f for f in os.listdir(PROMPT_DIR) if f.endswith("_en-prompt.txt")}
    prompt_norm = {normalize_id(f.replace("_en-prompt.txt", "")): f for f in prompt_files}

    truth_map = {}
    with open(CANDIDATES_JSONL) as f:
        for line in f:
            rec = json.loads(line)
            truth_map[rec['patient_id']] = rec['truth_ids']

    truth_labels = {}
    with open(RESULTS_CSV) as f:
        for row in csv.DictReader(f):
            truth_labels[row['patient_id']] = row['truth_labels']

    matched = []
    for pid in ids:
        key = normalize_id(pid)
        if key in prompt_norm:
            fname = prompt_norm[key]
            matched.append({
                'patient_id': pid,
                'prompt_path': str(PROMPT_DIR / fname),
                'truth_ids': truth_map.get(pid, []),
                'truth_labels': truth_labels.get(pid, ''),
            })
    return matched


def normalize_name(name: str) -> str:
    return re.sub(r'[\s\-,\.]+', ' ', name.lower()).strip()


def check_hit(response_text: str, truth_labels: str, k: int) -> bool:
    """Check if any truth label appears within the first k lines of the response."""
    lines = [l.strip() for l in response_text.splitlines() if l.strip()][:k + 5]
    text_block = ' '.join(lines[:k + 5])
    norm_text = normalize_name(text_block)

    for label in truth_labels.split('|'):
        label = label.strip()
        if not label:
            continue
        # Try progressively shorter prefixes
        parts = label.split(',')
        for i in range(len(parts), 0, -1):
            fragment = normalize_name(','.join(parts[:i]))
            if len(fragment) > 4 and fragment in norm_text:
                # Check approximate position
                rank = _approx_rank(response_text, fragment, k)
                if rank is not None and rank <= k:
                    return True
    return False


def _approx_rank(text: str, fragment: str, k: int) -> int | None:
    norm_text = normalize_name(text)
    # Find numbered lines
    numbered = re.findall(r'^\s*(\d+)[.)]\s*(.+)', text, re.MULTILINE)
    for rank_str, line in numbered[:k]:
        if fragment in normalize_name(line):
            return int(rank_str)
    # Fallback: line number
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    for i, line in enumerate(lines[:k], 1):
        if fragment in normalize_name(line):
            return i
    return None


def call_api(client: OpenAI, prompt_text: str) -> str:
    try:
        resp = client.chat.completions.create(
            model=API_MODEL,
            messages=[{"role": "user", "content": prompt_text}],
            max_tokens=MAX_TOKENS,
            temperature=0.0,
        )
        return resp.choices[0].message.content or ""
    except Exception as e:
        return f"API_ERROR: {e}"


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    logs_dir = OUTPUT_DIR / "logs"
    logs_dir.mkdir(exist_ok=True)

    cases = load_matched_cases()
    print(f"Cases to evaluate: {len(cases)}")

    client = OpenAI(base_url=API_BASE, api_key=API_KEY)

    # Skip already done
    done = {f.stem for f in logs_dir.iterdir() if f.suffix == ".txt"}
    pending = [c for c in cases if normalize_id(c['patient_id']) not in done]
    print(f"Already done: {len(done)}  |  Pending: {len(pending)}")

    raw_outputs: dict[str, str] = {}

    def _run(case):
        prompt_text = Path(case['prompt_path']).read_text(encoding='utf-8')
        return case['patient_id'], call_api(client, prompt_text), prompt_text

    with _cf.ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(_run, c): c for c in pending}
        for future in tqdm(_cf.as_completed(futures), total=len(futures), unit="case", desc="PP2Prompt eval"):
            pid, raw_output, prompt_text = future.result()
            raw_outputs[pid] = raw_output
            log_path = logs_dir / f"{normalize_id(pid)}.txt"
            log_path.write_text(
                f"PATIENT_ID: {pid}\n"
                f"TRUTH: {next(c['truth_labels'] for c in cases if c['patient_id'] == pid)}\n\n"
                f"PROMPT:\n{prompt_text}\n\n"
                f"RAW OUTPUT:\n{raw_output}\n",
                encoding='utf-8'
            )

    # ── Evaluate ──────────────────────────────────────────────────────────────
    print("\nEvaluating...")
    results = []
    hit_counts = {1: 0, 3: 0, 5: 0, 10: 0}
    truth_in_response = 0

    for case in cases:
        pid = case['patient_id']
        log_path = logs_dir / f"{normalize_id(pid)}.txt"
        if not log_path.exists():
            continue
        text = log_path.read_text(encoding='utf-8')
        raw = text.split("RAW OUTPUT:")[-1].strip()

        hits = {}
        for k in [1, 3, 5, 10]:
            h = check_hit(raw, case['truth_labels'], k)
            hits[k] = h
            if h:
                hit_counts[k] += 1

        results.append({
            'patient_id': pid,
            'truth_labels': case['truth_labels'],
            'hit@1': hits[1],
            'hit@3': hits[3],
            'hit@5': hits[5],
            'hit@10': hits[10],
            'api_error': raw.startswith('API_ERROR'),
        })

    n = len(results)
    errors = sum(r['api_error'] for r in results)
    print(f"\n{'='*50}")
    print(f"PP2Prompt Gemma-3-27b — {n} cases ({errors} API errors)")
    print(f"{'='*50}")
    for k in [1, 3, 5, 10]:
        print(f"  hit@{k:2d} = {hit_counts[k]/n:.4f}  ({hit_counts[k]}/{n})")

    # Save results
    with open(OUTPUT_DIR / "results.csv", 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=results[0].keys())
        writer.writeheader()
        writer.writerows(results)

    with open(OUTPUT_DIR / "summary.json", 'w') as f:
        json.dump({
            'n_cases': n,
            'api_errors': errors,
            'hit@1':  hit_counts[1] / n,
            'hit@3':  hit_counts[3] / n,
            'hit@5':  hit_counts[5] / n,
            'hit@10': hit_counts[10] / n,
        }, f, indent=2)

    print(f"\nResults saved to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
