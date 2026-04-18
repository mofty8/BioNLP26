"""Abstract inference backend interface."""

from __future__ import annotations

from abc import ABC, abstractmethod


class InferenceBackend(ABC):
    """Minimal contract: prompts in, completions out."""

    @abstractmethod
    def generate_batch(self, prompts: list[str]) -> list[str]:
        """Return one raw completion string per input prompt."""

    @abstractmethod
    def name(self) -> str:
        """Human-readable model identifier."""
