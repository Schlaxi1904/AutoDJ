"""Logging helpers that keep realtime audio threads lightweight."""
from __future__ import annotations

import logging
from contextlib import contextmanager
from logging import Logger
from pathlib import Path
from typing import Iterator


def configure_logging(runtime_root: Path, persistent_root: Path, level: int = logging.INFO) -> None:
    """Configure a dual-handler logger setup.

    Runtime logs stay in tmpfs as required by the specification and are only flushed
    to persistent storage on warnings/errors.
    """

    runtime_root.mkdir(parents=True, exist_ok=True)
    persistent_root.mkdir(parents=True, exist_ok=True)

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
