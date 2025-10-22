"""Logging helpers that keep realtime audio threads lightweight."""
from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from logging import Logger
from pathlib import Path
from typing import Iterator


def configure_logging(runtime_root: Path, persistent_root: Path, level: int = logging.INFO) -> None:
    """Configure a dual-handler logger setup.

    Runtime logs stay in tmpfs as required by the specification and are only flushed
    to persistent storage on warnings/errors.
    """

    runtime_override = os.environ.get("AUTO_DJ_RUNTIME_LOG_ROOT")
    persistent_override = os.environ.get("AUTO_DJ_PERSISTENT_LOG_ROOT")

    if runtime_override:
        runtime_root = Path(runtime_override)
    if persistent_override:
        persistent_root = Path(persistent_override)

    def ensure_dir(path: Path, fallback_suffix: str) -> Path:
        try:
            path.mkdir(parents=True, exist_ok=True)
            return path
        except PermissionError:
            fallback = Path.home() / ".auto-dj" / "logs" / fallback_suffix
            fallback.mkdir(parents=True, exist_ok=True)
            print(
                f"[logging] Falling back to user log directory {fallback} because "
                f"{path} is not writable."
            )
            return fallback

    runtime_root = ensure_dir(runtime_root, "runtime")
    persistent_root = ensure_dir(persistent_root, "persistent")

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    runtime_handler = logging.FileHandler(runtime_root / "auto_dj.log")
    runtime_handler.setFormatter(formatter)
    runtime_handler.setLevel(level)

    persistent_handler = logging.FileHandler(persistent_root / "auto_dj.log")
    persistent_handler.setFormatter(formatter)
    persistent_handler.setLevel(logging.WARNING)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.addHandler(runtime_handler)
    root_logger.addHandler(persistent_handler)


@contextmanager
def scoped_logger(name: str, **context: object) -> Iterator[Logger]:
    """Provide a temporary logger with context metadata appended."""

    logger = logging.getLogger(name)
    if context:
        prefix = " ".join(f"{key}={value}" for key, value in context.items())
        adapter = logging.LoggerAdapter(logger, extra={"context": prefix})
        yield adapter  # type: ignore[misc]
    else:
        yield logger
