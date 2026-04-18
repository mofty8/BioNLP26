from __future__ import annotations

import dataclasses
import json
import logging
import os
import platform
import random
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

try:
    from importlib import metadata as importlib_metadata
except Exception:  # pragma: no cover
    import importlib_metadata  # type: ignore


def utc_now_compact() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def safe_slug(text: str, max_len: int = 120) -> str:
    value = re.sub(r"[^a-zA-Z0-9._-]+", "-", text.strip()).strip("-").lower()
    if not value:
        return "run"
    return value[:max_len]


def ensure_dir(path: str | Path) -> str:
    Path(path).mkdir(parents=True, exist_ok=True)
    return str(path)


def make_run_dir(output_root: str | Path, run_name: str) -> str:
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    run_dir = root / f"{safe_slug(run_name)}_{utc_now_compact()}"
    run_dir.mkdir(parents=True, exist_ok=False)
    return str(run_dir)


def atomic_write_text(path: str | Path, text: str, encoding: str = "utf-8") -> None:
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = out_path.with_suffix(out_path.suffix + ".tmp")
    tmp_path.write_text(text, encoding=encoding)
    tmp_path.replace(out_path)


def write_json(path: str | Path, obj: Any, indent: int = 2) -> None:
    def default(value: Any) -> Any:
        if dataclasses.is_dataclass(value):
            return dataclasses.asdict(value)
        if isinstance(value, Path):
            return str(value)
        if isinstance(value, set):
            return sorted(value)
        if isinstance(value, tuple):
            return list(value)
        if hasattr(value, "__dict__"):
            return dict(value.__dict__)
        raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")

    atomic_write_text(path, json.dumps(obj, indent=indent, ensure_ascii=False, default=default) + "\n")


def read_lines(path: str | Path) -> list[str]:
    file_path = Path(path)
    if not file_path.exists():
        return []
    return [line.strip() for line in file_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def seed_everything(seed: int) -> None:
    random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)


def configure_logging(log_path: str | Path, verbose: bool = True) -> logging.Logger:
    logger = logging.getLogger("phenodp_gemma3_pipeline")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")

    file_handler = logging.FileHandler(str(log_path), encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    if verbose:
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setLevel(logging.INFO)
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

    logger.propagate = False
    return logger


def _pkg_version(package: str) -> Optional[str]:
    try:
        return importlib_metadata.version(package)
    except Exception:
        return None


def capture_environment(extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.version,
        "platform": platform.platform(),
        "executable": sys.executable,
        "cwd": os.getcwd(),
        "env": {
            "CUDA_VISIBLE_DEVICES": os.environ.get("CUDA_VISIBLE_DEVICES"),
        },
        "packages": {
            "pandas": _pkg_version("pandas"),
            "rapidfuzz": _pkg_version("rapidfuzz"),
            "pyhpo": _pkg_version("pyhpo"),
            "torch": _pkg_version("torch"),
            "vllm": _pkg_version("vllm"),
        },
    }
    try:
        git_rev = subprocess.check_output(["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL).decode().strip()
        payload["git_commit"] = git_rev
    except Exception:
        payload["git_commit"] = None
    try:
        smi = subprocess.check_output(["nvidia-smi", "-L"], stderr=subprocess.DEVNULL).decode().strip().splitlines()
        payload["gpus"] = smi
    except Exception:
        payload["gpus"] = None
    if extra:
        payload.update(extra)
    return payload
