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

# Derive superuser connection details. These can be overridden via environment
# variables so the installer can authenticate with PostgreSQL even when password
# authentication is required (e.g. Debian/Raspberry Pi images).
AUTO_DJ_SUPERUSER_USER="${AUTO_DJ_SUPERUSER_USER:-postgres}"
AUTO_DJ_SUPERUSER_HOST="${AUTO_DJ_SUPERUSER_HOST:-${DB_HOST}}"
AUTO_DJ_SUPERUSER_PORT="${AUTO_DJ_SUPERUSER_PORT:-${DB_PORT}}"
AUTO_DJ_SUPERUSER_DB="${AUTO_DJ_SUPERUSER_DB:-postgres}"

if [ -z "${AUTO_DJ_SUPERUSER_DSN:-}" ]; then
  SUPERUSER_PASSWORD="${AUTO_DJ_SUPERUSER_PASSWORD:-}"
  if [ -z "${SUPERUSER_PASSWORD}" ]; then
    read -r -s -p "[install] PostgreSQL password for ${AUTO_DJ_SUPERUSER_USER}@${AUTO_DJ_SUPERUSER_HOST}:${AUTO_DJ_SUPERUSER_PORT} (leave blank to try without): " SUPERUSER_PASSWORD
    echo
  fi

  AUTO_DJ_SUPERUSER_PASSWORD="${SUPERUSER_PASSWORD}"

  AUTO_DJ_SUPERUSER_DSN="$(
    AUTO_DJ_SUPERUSER_USER="${AUTO_DJ_SUPERUSER_USER}" \
    AUTO_DJ_SUPERUSER_HOST="${AUTO_DJ_SUPERUSER_HOST}" \
    AUTO_DJ_SUPERUSER_PORT="${AUTO_DJ_SUPERUSER_PORT}" \
    AUTO_DJ_SUPERUSER_DB="${AUTO_DJ_SUPERUSER_DB}" \
    AUTO_DJ_SUPERUSER_PASSWORD="${AUTO_DJ_SUPERUSER_PASSWORD}" \
    "${PYTHON_BIN}" - <<'PY'
import os
import urllib.parse

user = os.environ["AUTO_DJ_SUPERUSER_USER"]
host = os.environ["AUTO_DJ_SUPERUSER_HOST"]
port = os.environ["AUTO_DJ_SUPERUSER_PORT"]
database = os.environ["AUTO_DJ_SUPERUSER_DB"]
password = os.environ.get("AUTO_DJ_SUPERUSER_PASSWORD", "")

def quote(value: str) -> str:
    return urllib.parse.quote(value, safe="")

dsn = f"postgresql://{quote(user)}"
if password:
    dsn += f":{quote(password)}"
dsn += f"@{host}:{port}/{quote(database)}"
print(dsn)
PY
  )"
  export AUTO_DJ_SUPERUSER_DSN
fi

# Ensure the PostgreSQL role and database exist before bootstrapping tables unless
# explicitly skipped by the caller (useful when the role/database are pre-provisioned).
SKIP_DB_INIT="${AUTO_DJ_SKIP_DB_INIT:-0}"
if [ "${SKIP_DB_INIT}" = "1" ]; then
  echo "[install] Skipping database provisioning (AUTO_DJ_SKIP_DB_INIT=1)"
else
  SETUP_ARGS=("--ensure-database")
  if [ -n "${AUTO_DJ_SUPERUSER_DSN:-}" ]; then
    SETUP_ARGS+=("--database-superuser-dsn" "${AUTO_DJ_SUPERUSER_DSN}")
  fi

  python -m auto_dj.setup "${SETUP_ARGS[@]}"
fi

# Initialize the database schema and ensure the default admin account exists.
python -m auto_dj.setup --init-db --ensure-admin

echo "[install] Setup complete. Default admin login: admin / Admin123"
