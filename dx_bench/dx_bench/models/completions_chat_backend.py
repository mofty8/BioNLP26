"""Batched /v1/completions backend with client-side chat-template rendering.

Combines the throughput of the raw completions endpoint (batched prompts in a
single HTTP request) with the quality of chat-template formatting.  The HF
tokenizer is loaded once at init time, and each prompt is wrapped in the
model's chat template before being sent to ``/v1/completions``.

This is the recommended backend for instruction-tuned models (e.g. MedGemma)
whose chat template is not correctly handled by vLLM's ``/v1/chat/completions``
endpoint.
"""

from __future__ import annotations

import json
import logging
from typing import Optional
from urllib import error, request

from .base import InferenceBackend

logger = logging.getLogger(__name__)


def _load_tokenizer(model_name: str):
    from transformers import AutoTokenizer
    return AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)


class CompletionsChatBackend(InferenceBackend):
    """Batched completions with client-side chat template."""

    def __init__(
        self,
        model_name: str,
        api_base_url: str,
        api_key: Optional[str] = None,
        max_tokens: int = 512,
        temperature: float = 0.0,
        top_p: float = 1.0,
        seed: Optional[int] = 42,
        request_timeout_s: int = 600,
        empty_completion_retries: int = 2,
        tokenizer_name: Optional[str] = None,
    ) -> None:
        self._model_name = model_name
        self._api_base_url = api_base_url.rstrip("/")
        self._api_key = api_key
        self._max_tokens = max_tokens
        self._temperature = temperature
        self._top_p = top_p
        self._seed = seed
        self._request_timeout_s = request_timeout_s
        self._empty_completion_retries = empty_completion_retries

        tok_name = tokenizer_name or model_name
        logger.info(
            "Loading tokenizer '%s' for client-side chat template rendering",
            tok_name,
        )
        self._tokenizer = _load_tokenizer(tok_name)

        logger.info(
            "Using completions+chat backend: %s (model=%s, tokenizer=%s)",
            self._api_base_url,
            self._model_name,
            tok_name,
        )

    def _apply_chat_template(self, text: str) -> str:
        messages = [{"role": "user", "content": text}]
        return self._tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )

    def _post_completions(self, prompts: list[str]) -> list[str]:
        payload = {
            "model": self._model_name,
            "prompt": prompts,
            "max_tokens": self._max_tokens,
            "temperature": self._temperature,
            "top_p": self._top_p,
        }
        if self._seed is not None:
            payload["seed"] = self._seed

        body = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        req = request.Request(
            url=f"{self._api_base_url}/completions",
            data=body,
            headers=headers,
            method="POST",
        )

        try:
            with request.urlopen(req, timeout=self._request_timeout_s) as resp:
                response_body = resp.read()
        except error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"HTTP {exc.code} from inference server: {details}"
            ) from exc
        except error.URLError as exc:
            raise RuntimeError(
                f"Could not reach inference server at {self._api_base_url}: {exc}"
            ) from exc

        data = json.loads(response_body.decode("utf-8"))
        choices = data.get("choices", [])
        results = [""] * len(prompts)

        for choice in choices:
            index = choice.get("index", 0)
            if not 0 <= index < len(prompts):
                raise RuntimeError(
                    f"Server returned out-of-range completion index {index} "
                    f"for batch of size {len(prompts)}"
                )
            results[index] = choice.get("text", "")

        if len(choices) != len(prompts):
            raise RuntimeError(
                f"Inference server returned {len(choices)} completions for "
                f"{len(prompts)} prompts"
            )

        return results

    def generate_batch(self, prompts: list[str]) -> list[str]:
        if not prompts:
            return []

        # Apply chat template to each prompt
        rendered = [self._apply_chat_template(p) for p in prompts]

        results = [""] * len(rendered)
        pending = list(range(len(rendered)))

        for attempt in range(self._empty_completion_retries + 1):
            if not pending:
                break

            batch_prompts = [rendered[idx] for idx in pending]
            batch_results = self._post_completions(batch_prompts)

            next_pending: list[int] = []
            for idx, text in zip(pending, batch_results):
                if text.strip():
                    results[idx] = text
                else:
                    next_pending.append(idx)

            if next_pending and attempt < self._empty_completion_retries:
                logger.warning(
                    "Retrying %d empty completions (attempt %d/%d)",
                    len(next_pending),
                    attempt + 1,
                    self._empty_completion_retries,
                )
            pending = next_pending

        return results

    def name(self) -> str:
        return self._model_name
