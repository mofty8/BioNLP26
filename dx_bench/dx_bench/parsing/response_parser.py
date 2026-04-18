"""Parse LLM responses into structured ranked diagnosis lists."""

from __future__ import annotations

import re
import logging

from dx_bench.data.schema import Diagnosis

logger = logging.getLogger(__name__)

# Matches lines like:
#   1. OMIM:123456 - Disease name
#   2) Disease name
#   3. OMIM:123456 — Disease name
#   4. Disease name (no OMIM ID)
#   **1. OMIM:123456 - Disease name**  (markdown bold)
_LINE_RE = re.compile(
    r"^\s*\**\s*(\d+)\s*[.\)]\s*\**\s*"       # rank number with optional bold
    r"(?:(OMIM:\d+)\s*[-–—:]\s*)?"              # optional OMIM ID
    r"(.+?)\s*\**\s*$",                         # disease name
    re.MULTILINE,
)

# Noise patterns to skip
_NOISE_PATTERNS = [
    re.compile(r"^(n/?a|none|unknown|not applicable)", re.IGNORECASE),
    re.compile(r"^(i cannot|i('m| am) (unable|not)|based on|note:)", re.IGNORECASE),
    re.compile(r"^(the (above|following|patient)|please|disclaimer)", re.IGNORECASE),
]

MAX_DIAGNOSES = 30


def parse_response(raw_response: str) -> tuple[list[Diagnosis], list[str]]:
    """Parse a raw LLM response into a ranked list of Diagnosis objects.

    Returns:
        (diagnoses, warnings) — warnings are non-fatal parse issues.
    """
    warnings: list[str] = []

    if not raw_response or not raw_response.strip():
        return [], ["empty_response"]

    matches = _LINE_RE.findall(raw_response)

    if not matches:
        warnings.append(
            f"no_numbered_lines_found (response length: {len(raw_response)})"
        )
        return [], warnings

    diagnoses: list[Diagnosis] = []
    seen_names: set[str] = set()

    for rank_str, omim_id, disease_name in matches:
        # Clean up disease name
        disease_name = disease_name.strip().rstrip(".")

        # Skip noise
        if any(pat.match(disease_name) for pat in _NOISE_PATTERNS):
            continue

        # Skip empty
        if not disease_name:
            continue

        # Deduplicate by lowercased name
        name_key = disease_name.lower()
        if name_key in seen_names:
            warnings.append(f"duplicate_removed: {disease_name}")
            continue
        seen_names.add(name_key)

        # Clean OMIM ID
        predicted_id = omim_id.strip() if omim_id else None

        diagnoses.append(
            Diagnosis(
                rank=len(diagnoses) + 1,  # re-rank sequentially
                raw_text=f"{rank_str}. {omim_id + ' - ' if omim_id else ''}{disease_name}",
                disease_name=disease_name,
                predicted_id=predicted_id,
            )
        )

        if len(diagnoses) >= MAX_DIAGNOSES:
            warnings.append(f"truncated_at_{MAX_DIAGNOSES}")
            break

    # Check rank consistency with original numbering
    original_ranks = [int(m[0]) for m in matches]
    expected = list(range(1, len(original_ranks) + 1))
    if original_ranks != expected[: len(original_ranks)]:
        warnings.append(f"non_sequential_ranks: {original_ranks[:10]}")

    if not diagnoses:
        warnings.append("all_lines_filtered_as_noise")

    return diagnoses, warnings
