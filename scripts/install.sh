#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"
VENV_PATH="${PROJECT_ROOT}/.venv"
PYTHON_BIN="${PYTHON:-python3}"

if [ ! -d "${VENV_PATH}" ]; then
  echo "[install] Creating virtual environment at ${VENV_PATH}"
  "${PYTHON_BIN}" -m venv "${VENV_PATH}"
fi

# shellcheck disable=SC1090
source "${VENV_PATH}/bin/activate"

pip install --upgrade pip
pip install -e "${PROJECT_ROOT}"

# Default database connection values for the Auto-DJ service. These can be
# overridden via environment variables before invoking the installer.
DB_USER="${AUTO_DJ_DB_USER:-auto-dj}"
DB_PASSWORD="${AUTO_DJ_DB_PASSWORD:-auto-dj}"
DB_NAME="${AUTO_DJ_DB_NAME:-auto_dj}"
DB_HOST="${AUTO_DJ_DB_HOST:-localhost}"
DB_PORT="${AUTO_DJ_DB_PORT:-5432}"

export AUTO_DJ_DATABASE_DSN="postgresql+psycopg://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}"

# Ensure the PostgreSQL role and database exist before bootstrapping tables.
SETUP_ARGS=("--ensure-database")
if [ -n "${AUTO_DJ_SUPERUSER_DSN:-}" ]; then
  SETUP_ARGS+=("--database-superuser-dsn" "${AUTO_DJ_SUPERUSER_DSN}")
fi

python -m auto_dj.setup "${SETUP_ARGS[@]}"

# Initialize the database schema and ensure the default admin account exists.
python -m auto_dj.setup --init-db --ensure-admin

echo "[install] Setup complete. Default admin login: admin / Admin123"
