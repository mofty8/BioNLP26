"""Mondo ontology resolver: OMIM ID → Mondo ID with ancestor-aware matching."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class MondoResolver:
    """Maps OMIM IDs to Mondo IDs and checks equivalence via shared Mondo concept.

    Uses oaklib with a local mondo.db (SQLite) for fast lookups.
    Caches all mappings aggressively since the ontology is static within a run.
    """

    def __init__(self, mondo_db_path: Optional[str] = None) -> None:
        from oaklib import get_adapter
        from oaklib.datamodels.vocabulary import IS_A

        self._IS_A = IS_A
        self._omim_to_mondo: dict[str, Optional[str]] = {}
        self._text_to_mondo: dict[str, Optional[str]] = {}
        self._ancestor_cache: dict[str, set[str]] = {}

        if mondo_db_path and Path(mondo_db_path).exists():
            logger.info("Loading Mondo from local DB: %s", mondo_db_path)
            self._adapter = get_adapter(f"sqlite:{mondo_db_path}")
        else:
            logger.warning(
                "Mondo DB not found at %s — using remote ubergraph (slow!)",
                mondo_db_path,
            )
            self._adapter = get_adapter("ubergraph:mondo")

    def omim_to_mondo(self, omim_id: str) -> Optional[str]:
        """Map OMIM:XXXXXX → MONDO:XXXXXXX."""
        if omim_id in self._omim_to_mondo:
            return self._omim_to_mondo[omim_id]

        mondo_id = None
        try:
            # Try to find Mondo term that has this OMIM as a cross-reference
            candidates = list(self._adapter.curies_by_label(omim_id))
            for c in candidates:
                if c.startswith("MONDO"):
                    mondo_id = c
                    break
        except Exception:
            pass

        # Fallback: try mapping via xref if available
        if mondo_id is None:
            try:
                for mapping in self._adapter.sssom_mappings([omim_id]):
                    obj_id = str(mapping.object_id) if mapping.object_id else ""
                    subj_id = str(mapping.subject_id) if mapping.subject_id else ""
                    if obj_id.startswith("MONDO"):
                        mondo_id = obj_id
                        break
                    if subj_id.startswith("MONDO"):
                        mondo_id = subj_id
                        break
            except Exception:
                pass

        self._omim_to_mondo[omim_id] = mondo_id
        return mondo_id

    def text_to_mondo(self, disease_name: str) -> Optional[str]:
        """Map a disease name string → MONDO ID."""
        if disease_name in self._text_to_mondo:
            return self._text_to_mondo[disease_name]

        mondo_id = None
        try:
            matches = list(self._adapter.curies_by_label(disease_name))
            for m in matches:
                if m.startswith("MONDO"):
                    mondo_id = m
                    break
        except Exception:
            pass

        self._text_to_mondo[disease_name] = mondo_id
        return mondo_id

    def _get_ancestors(self, mondo_id: str) -> set[str]:
        """Get all IS_A ancestors of a Mondo term (cached)."""
        if mondo_id in self._ancestor_cache:
            return self._ancestor_cache[mondo_id]

        ancestors: set[str] = set()
        try:
            ancestors = set(self._adapter.ancestors(mondo_id, predicates=[self._IS_A]))
        except Exception:
            pass

        self._ancestor_cache[mondo_id] = ancestors
        return ancestors

    def is_match(self, predicted_mondo: Optional[str], gold_mondo: Optional[str]) -> bool:
        """Check if predicted and gold Mondo IDs refer to the same or related concept.

        Matches if:
        1. Exact same Mondo ID
        2. One is an ancestor of the other (handles allelic series)
        """
        if predicted_mondo is None or gold_mondo is None:
            return False

        if predicted_mondo == gold_mondo:
            return True

        # Check ancestor relationship in both directions
        gold_ancestors = self._get_ancestors(gold_mondo)
        if predicted_mondo in gold_ancestors:
            return True

        pred_ancestors = self._get_ancestors(predicted_mondo)
        if gold_mondo in pred_ancestors:
            return True

        return False

    def resolve_diagnosis(
        self,
        predicted_id: Optional[str],
        resolved_id: Optional[str],
        disease_name: str,
    ) -> Optional[str]:
        """Best-effort Mondo resolution for a single diagnosis.

        Tries (in order): predicted OMIM → Mondo, resolved OMIM → Mondo,
        disease name → Mondo.
        """
        for omim_id in [predicted_id, resolved_id]:
            if omim_id:
                mondo = self.omim_to_mondo(omim_id)
                if mondo:
                    return mondo

        return self.text_to_mondo(disease_name)
