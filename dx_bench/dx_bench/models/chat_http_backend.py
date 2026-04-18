"""OpenAI-compatible chat-completions backend for chat-tuned models."""

from __future__ import annotations

import json
import logging
from typing import Optional
from urllib import error, request

from .base import InferenceBackend

logger = logging.getLogger(__name__)


class ChatHTTPBackend(InferenceBackend):
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

        logger.info(
            "Using OpenAI-compatible chat backend: %s (model=%s)",
            self._api_base_url,
            self._model_name,
        )

    def _post_chat_completion(self, prompt: str) -> str:
        payload = {
            "model": self._model_name,
            "messages": [{"role": "user", "content": prompt}],
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
            url=f"{self._api_base_url}/chat/completions",
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
                f"HTTP {exc.code} from chat inference server: {details}"
            ) from exc
        except error.URLError as exc:
            raise RuntimeError(
                f"Could not reach chat inference server at {self._api_base_url}: {exc}"
            ) from exc

        data = json.loads(response_body.decode("utf-8"))
        choices = data.get("choices", [])
        if len(choices) != 1:
            raise RuntimeError(
                f"Chat inference server returned {len(choices)} completions for one prompt"
            )

        message = choices[0].get("message", {})
        return message.get("content", "") or ""

    def generate_batch(self, prompts: list[str]) -> list[str]:
        results: list[str] = []
        for idx, prompt in enumerate(prompts, start=1):
            text = ""
            for attempt in range(self._empty_completion_retries + 1):
                text = self._post_chat_completion(prompt)
                if text.strip():
                    break
                if attempt < self._empty_completion_retries:
                    logger.warning(
                        "Retrying empty chat completion %d/%d (attempt %d/%d)",
                        idx,
                        len(prompts),
                        attempt + 1,
                        self._empty_completion_retries,
                    )
            results.append(text)
        return results

    def name(self) -> str:
        return self._model_name
