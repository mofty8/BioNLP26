"""vLLM-based inference backend."""

from __future__ import annotations

import logging
import os
from typing import Optional

from vllm import LLM, SamplingParams

from .base import InferenceBackend

logger = logging.getLogger(__name__)


class VLLMBackend(InferenceBackend):

    def __init__(
        self,
        model_name: str,
        max_tokens: int = 512,
        temperature: float = 0.0,
        top_p: float = 1.0,
        seed: int = 42,
        tensor_parallel_size: int = 1,
        gpu_memory_utilization: float = 0.90,
        revision: Optional[str] = None,
        gpu_ids: Optional[list[int]] = None,
    ) -> None:
        # Set CUDA_VISIBLE_DEVICES before importing/initializing vLLM.
        # Must happen before LLM() is constructed — vLLM reads this at init time.
        if gpu_ids is not None:
            visible = ",".join(str(g) for g in gpu_ids)
            os.environ["CUDA_VISIBLE_DEVICES"] = visible
            logger.info("CUDA_VISIBLE_DEVICES set to: %s", visible)
            # tensor_parallel_size must not exceed the number of visible GPUs
            if tensor_parallel_size > len(gpu_ids):
                logger.warning(
                    "tensor_parallel_size (%d) > len(gpu_ids) (%d); "
                    "clamping to %d",
                    tensor_parallel_size,
                    len(gpu_ids),
                    len(gpu_ids),
                )
                tensor_parallel_size = len(gpu_ids)

        self._model_name = model_name
        self._sampling_params = SamplingParams(
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            seed=seed,
        )
        logger.info(
            "Loading vLLM model: %s (tp=%d, gpus=%s)",
            model_name,
            tensor_parallel_size,
            gpu_ids,
        )
        self._llm = LLM(
            model=model_name,
            tensor_parallel_size=tensor_parallel_size,
            gpu_memory_utilization=gpu_memory_utilization,
            revision=revision,
            trust_remote_code=True,
            seed=seed,
        )
        logger.info("Model loaded successfully")

    def generate_batch(self, prompts: list[str]) -> list[str]:
        outputs = self._llm.generate(prompts, self._sampling_params)
        # vLLM returns outputs in the same order as prompts
        results = []
        for output in outputs:
            text = output.outputs[0].text if output.outputs else ""
            results.append(text)
        return results

    def name(self) -> str:
        return self._model_name
