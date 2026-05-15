from __future__ import annotations

import logging
from pathlib import Path

from .utils import ensure_dir


def setup_logging(name: str, level: str, log_dir: str | Path, run_id: str) -> logging.Logger:
    ensure_dir(log_dir)
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.propagate = False

    if logger.handlers:
        return logger

    formatter = logging.Formatter("%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    console.setLevel(getattr(logging, level.upper(), logging.INFO))

    file_handler = logging.FileHandler(Path(log_dir) / f"{run_id}.log", encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.setLevel(getattr(logging, level.upper(), logging.INFO))

    logger.addHandler(console)
    logger.addHandler(file_handler)
    return logger

