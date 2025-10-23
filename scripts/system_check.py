#!/usr/bin/env python3
"""Wrapper script for the Auto-DJ diagnostics.

This helper attempts to load the project package even when the virtual
environment is not explicitly activated. The installation script installs the
package in a dedicated ``.venv`` directory, but on constrained devices it is
easy to accidentally execute the wrapper with the system interpreter. In that
case we prepend ``src`` to ``sys.path`` so ``auto_dj`` becomes importable.
"""

from __future__ import annotations

import sys
from pathlib import Path


def _resolve_main():
    try:
        from auto_dj.tools.diagnostics import main  # type: ignore import
    except ModuleNotFoundError:  # pragma: no cover - only hit outside venv
        project_root = Path(__file__).resolve().parents[1]
        src_path = project_root / "src"
        if src_path.is_dir():
            sys.path.insert(0, str(src_path))
        from auto_dj.tools.diagnostics import main  # type: ignore import

    return main


if __name__ == "__main__":
    raise SystemExit(_resolve_main()())
