#!/usr/bin/env python3
"""Convenience bootstrapper to install dependencies and prepare the database."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
VENV_DIR = PROJECT_ROOT / ".venv"


def _python_executable() -> str:
    if os.name == "nt":
        return str(VENV_DIR / "Scripts" / "python.exe")
    return str(VENV_DIR / "bin" / "python")


def _run(cmd: list[str], *, env: dict[str, str] | None = None) -> None:
    print("→", " ".join(cmd))
    subprocess.run(cmd, check=True, cwd=PROJECT_ROOT, env=env)


def ensure_virtualenv() -> str:
    if not VENV_DIR.exists():
        print("Erstelle virtuelle Umgebung in", VENV_DIR)
        import venv

        venv.EnvBuilder(with_pip=True).create(VENV_DIR)
    python = _python_executable()
    if not Path(python).exists():
        raise RuntimeError("Virtuelle Umgebung konnte nicht initialisiert werden")
    return python


def install_project(python: str) -> None:
    _run([python, "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"])
    _run([python, "-m", "pip", "install", "."])


def ensure_database(python: str) -> None:
    setup_cmd = [
        python,
        "-m",
        "auto_dj.setup",
        "--ensure-database",
        "--init-db",
    ]
    if os.environ.get("AUTO_DJ_SKIP_DB_INIT"):
        print("AUTO_DJ_SKIP_DB_INIT gesetzt – überspringe Datenbankinitialisierung")
    else:
        _run(setup_cmd)
    _run([python, "-m", "auto_dj.db_check"])
    _run([python, "-m", "auto_dj.setup", "--ensure-admin"])


def main() -> int:
    python = ensure_virtualenv()
    install_project(python)
    ensure_database(python)
    print("Installation abgeschlossen. Virtuelle Umgebung aktivieren mit:\n  source .venv/bin/activate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
