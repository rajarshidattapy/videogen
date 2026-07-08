"""Logging setup and a stage-timing context manager.

Every pipeline stage logs a start, a completion with duration, or an error,
e.g.:

    [Research] Started
    [Research] Completed in 18.2s
"""

import logging
import time
from contextlib import contextmanager
from typing import Iterator

from config import get_settings

_configured = False


def get_logger(name: str = "videogen") -> logging.Logger:
    global _configured
    logger = logging.getLogger(name)

    if not _configured:
        settings = get_settings()
        formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)

        file_handler = logging.FileHandler(settings.log_dir / "app.log", encoding="utf-8")
        file_handler.setFormatter(formatter)

        root = logging.getLogger("videogen")
        root.setLevel(logging.INFO)
        root.addHandler(stream_handler)
        root.addHandler(file_handler)
        _configured = True

    return logger


@contextmanager
def stage(name: str) -> Iterator[None]:
    """Logs '[name] Started' / '[name] Completed in Xs' / '[name] Failed: err' around a block."""
    logger = get_logger()
    logger.info("[%s] Started", name)
    started_at = time.monotonic()
    try:
        yield
    except Exception as exc:
        logger.error("[%s] Failed: %s", name, exc)
        raise
    else:
        logger.info("[%s] Completed in %.1fs", name, time.monotonic() - started_at)
