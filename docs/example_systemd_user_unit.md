# Beispiel: systemd-User-Service für den Auto-DJ

```ini
[Unit]
Description=AutoDJ Web (FastAPI/Uvicorn)
After=network-online.target

[Service]
Type=simple
WorkingDirectory=/home/pi/autodj
ExecStart=/home/pi/autodj/.venv/bin/python -m auto_dj web --host 0.0.0.0 --port 8000
Restart=on-failure
RestartSec=3
Environment=AUTO_DJ_DATABASE_DSN=postgresql://auto-dj:auto-dj@localhost:5432/auto_dj
# Optional: Superuser-Phase überspringen, wenn die Datenbank bereits existiert
# Environment=AUTO_DJ_SKIP_DB_INIT=1

[Install]
WantedBy=default.target
```

> Hinweis: Passe Pfade und Ports bei Bedarf an deine Umgebung an. Wird kein eigener
> Superuser verwendet, genügt die App-DSN in Kombination mit dem Skip-Flag – die
> Anwendung führt beim Start automatisch `alembic upgrade head` aus und prüft das
> Schema. Bleibt die App-DSN leer, gelten die bestehenden Fallbacks aus `scripts/bootstrap.py`.
