#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/Schlaxi1904/AutoDJ.git}"
BRANCH="${BRANCH:-codex/implement-auto-dj-with-daslight-5-and-osc}"
APP_DIR="${APP_DIR:-$HOME/autodj}"
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"

log(){ printf "\n\033[1;32m[INFO]\033[0m %s\n" "$*"; }
warn(){ printf "\n\033[1;33m[WARN]\033[0m %s\n" "$*"; }

if command -v apt >/dev/null 2>&1; then
  log "Installiere Systemvoraussetzungen…"
  sudo apt-get update -y
  sudo apt-get install -y python3 python3-venv python3-pip python3-dev build-essential libffi-dev libssl-dev libpq-dev postgresql postgresql-client git acl
fi

log "Stoppe laufende Instanzen…"
pkill -f "python.*auto_dj web" 2>/dev/null || true
pkill -f "uvicorn.*auto_dj" 2>/dev/null || true
systemctl --user stop autodj-web.service 2>/dev/null || true

if [ -d "$APP_DIR" ]; then
  TS="$(date +%F-%H%M%S)"
  log "Backup → ${APP_DIR}.bak-${TS}"
  mv "$APP_DIR" "${APP_DIR}.bak-${TS}"
fi

log "Clone ${REPO_URL}#${BRANCH} → ${APP_DIR}"
git clone --branch "$BRANCH" --depth 1 "$REPO_URL" "$APP_DIR"
cd "$APP_DIR"

log "Venv anlegen + Pip tooling aktualisieren…"
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip setuptools wheel

log "Sicherheitsdeps (bcrypt/cffi) vorab installieren…"
pip install cffi bcrypt

log "Bootstrap (inkl. DB-Provisioning mit Fallback)…"
python scripts/bootstrap.py

log "Install…"
chmod +x ./scripts/install.sh
./scripts/install.sh

log "Systemcheck…"
python ./scripts/system_check.py || true

log "Systemd-User-Service schreiben/aktivieren…"
mkdir -p "$HOME/.config/systemd/user"
cat > "$HOME/.config/systemd/user/autodj-web.service" <<UNIT
[Unit]
Description=AutoDJ Web (FastAPI/Uvicorn)
After=network-online.target

[Service]
Type=simple
WorkingDirectory=${APP_DIR}
Environment=AUTO_DJ_RUNTIME_LOG_ROOT=${HOME}/.auto-dj/logs/runtime
Environment=AUTO_DJ_PERSISTENT_LOG_ROOT=${HOME}/.auto-dj/logs/persistent
# Optional: expliziter Superuser-DSN, sonst macht bootstrap den Fallback
# Environment=AUTO_DJ_SUPERUSER_DSN=postgresql://postgres@/postgres?host=/var/run/postgresql
ExecStart=${APP_DIR}/.venv/bin/python -m auto_dj web --host ${HOST} --port ${PORT}
Restart=on-failure
RestartSec=3

[Install]
WantedBy=default.target
UNIT

systemctl --user daemon-reload
systemctl --user enable --now autodj-web.service

log "Fertig. Web: http://${HOST}:${PORT}/   Login: admin / Admin123"
