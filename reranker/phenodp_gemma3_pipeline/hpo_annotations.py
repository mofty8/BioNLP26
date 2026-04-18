"""Loader for HPO phenotype-disease frequency annotations (phenotype.hpoa)."""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set

# HPO frequency term IDs → midpoint percentages
_HPO_FREQ_TERMS: Dict[str, float] = {
    "HP:0040280": 100.0,  # Obligate
    "HP:0040281": 90.0,   # Very frequent (80-99%)
    "HP:0040282": 55.0,   # Frequent (30-79%)
    "HP:0040283": 17.0,   # Occasional (5-29%)
    "HP:0040284": 2.0,    # Very rare (<5%)
    "HP:0040285": 0.0,    # Excluded
}


@dataclass(frozen=True)
class PhenotypeAnnotation:
    hpo_id: str
    frequency_pct: Optional[float]  # None if unknown

    @property
    def is_obligatory(self) -> bool:
        return self.frequency_pct is not None and self.frequency_pct >= 90.0

    def freq_str(self) -> str:
        if self.frequency_pct is None:
            return "freq unknown"
        return f"{self.frequency_pct:.0f}%"


def _parse_frequency(raw: str) -> Optional[float]:
    """Parse HPO frequency field to a percentage (0-100)."""
    raw = raw.strip()
    if not raw:
        return None
    if "/" in raw:
        parts = raw.split("/")
        try:
            return float(parts[0]) / float(parts[1]) * 100.0
        except (ValueError, ZeroDivisionError):
            return None
    if raw in _HPO_FREQ_TERMS:
        return _HPO_FREQ_TERMS[raw]
    if "%" in raw:
        try:
            return float(raw.replace("%", ""))
        except ValueError:
            return None
    return None


class HPOAnnotationStore:
    """In-memory store of disease → phenotype annotations with frequencies."""

    def __init__(self) -> None:
        self._annotations: Dict[str, List[PhenotypeAnnotation]] = defaultdict(list)

    @classmethod
    def from_hpoa_file(cls, path: str | Path) -> "HPOAnnotationStore":
        store = cls()
        path = Path(path)
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("#") or line.startswith("database_id"):
                    continue
                parts = line.rstrip("\n").split("\t")
                if len(parts) < 8:
                    continue
                disease_id = parts[0].strip()
                qualifier = parts[2].strip().upper()
                hpo_id = parts[3].strip()
                freq_raw = parts[7].strip()
                aspect = parts[10].strip() if len(parts) > 10 else "P"
                # Skip NOT-qualified and non-phenotype aspects
                if qualifier == "NOT" or aspect != "P":
                    continue
                freq = _parse_frequency(freq_raw)
                store._annotations[disease_id].append(
                    PhenotypeAnnotation(hpo_id=hpo_id, frequency_pct=freq)
                )
        return store

    def get_annotations(self, disease_id: str) -> List[PhenotypeAnnotation]:
        return self._annotations.get(disease_id, [])

    def get_annotations_by_frequency(self, disease_id: str) -> List[PhenotypeAnnotation]:
        """Return annotations sorted by frequency (highest first), unknowns last."""
        anns = self.get_annotations(disease_id)
        with_freq = sorted([a for a in anns if a.frequency_pct is not None], key=lambda a: -a.frequency_pct)
        without_freq = [a for a in anns if a.frequency_pct is None]
        return with_freq + without_freq

    def format_for_prompt(
        self,
        disease_id: str,
        hpo_names: Dict[str, str],
        patient_pos_hpo_ids: Set[str],
        patient_neg_hpo_ids: Set[str],
        max_annotations: int = 10,
    ) -> List[str]:
        """Format annotations for inclusion in the LLM prompt.

        Returns lines like:
          - Arachnodactyly (HP:0001166): 84% [PATIENT HAS]
          - Dilated cardiomyopathy (HP:0001644): 68% [PATIENT ABSENT]
          - Knee flexion contracture (HP:0002803): 100% OBLIGATORY
        """
        anns = self.get_annotations_by_frequency(disease_id)
        if not anns:
            return ["  (no HPO frequency annotations available)"]

        # Deduplicate by HPO ID (keep highest frequency)
        seen: Dict[str, PhenotypeAnnotation] = {}
        for a in anns:
            if a.hpo_id not in seen:
                seen[a.hpo_id] = a
            elif a.frequency_pct is not None:
                existing = seen[a.hpo_id]
                if existing.frequency_pct is None or a.frequency_pct > existing.frequency_pct:
                    seen[a.hpo_id] = a
        anns = sorted(seen.values(), key=lambda a: -(a.frequency_pct if a.frequency_pct is not None else -1))

        # Prioritize: patient-relevant annotations first, then by frequency
        patient_relevant = []
        other = []
        for a in anns:
            if a.hpo_id in patient_pos_hpo_ids or a.hpo_id in patient_neg_hpo_ids:
                patient_relevant.append(a)
            else:
                other.append(a)

        selected = patient_relevant + other
        selected = selected[:max_annotations]

        lines = []
        for a in selected:
            name = hpo_names.get(a.hpo_id, a.hpo_id)
            freq = a.freq_str()
            tags = []
            if a.is_obligatory:
                tags.append("OBLIGATORY")
            if a.hpo_id in patient_pos_hpo_ids:
                tags.append("PATIENT HAS")
            elif a.hpo_id in patient_neg_hpo_ids:
                tags.append("PATIENT ABSENT")
            tag_str = f" [{', '.join(tags)}]" if tags else ""
            lines.append(f"  - {name}: {freq}{tag_str}")

        remaining = len(anns) - len(selected)
        if remaining > 0:
            lines.append(f"  ({remaining} more annotations omitted)")
        return lines
