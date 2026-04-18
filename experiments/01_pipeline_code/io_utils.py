from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List


def write_jsonl(path: str, records: Iterable[Dict[str, Any]], mode: str = "w") -> None:
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open(mode, encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def read_jsonl(path: str) -> List[Dict[str, Any]]:
    in_path = Path(path)
    if not in_path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    with in_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def write_csv(path: str, rows: List[Dict[str, Any]]) -> None:
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        out_path.write_text("", encoding="utf-8")
        return
    header = list(rows[0].keys())
    with out_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=header)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_markdown_examples(path: str, examples: List[Dict[str, Any]]) -> None:
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    lines: List[str] = ["# Qualitative Examples", ""]
    for example in examples:
        lines.append(f"## {example.get('patient_id', '')}")
        lines.append("")
        lines.append(f"Truth IDs: `{example.get('truth_ids', '')}`")
        lines.append("")
        lines.append("### Prompt")
        lines.append("```text")
        lines.append(example.get("prompt") or "")
        lines.append("```")
        lines.append("")
        lines.append("### Raw Output")
        lines.append("```text")
        lines.append(example.get("raw_output") or "")
        lines.append("```")
        lines.append("")
        lines.append("### Parsed Output")
        lines.append("```json")
        lines.append(json.dumps(example.get("parsed_output") or {}, indent=2, ensure_ascii=False))
        lines.append("```")
        lines.append("")
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
