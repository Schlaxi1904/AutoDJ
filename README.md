# AutoDJ

Dieses Repository enthält sowohl die Implementierungs-Spezifikation als auch einen ersten
Programmierungs-Entwurf für den Auto-DJ mit Daslight-5-Integration.

## Projektüberblick

* Die vollständigen funktionalen, technischen und betrieblichen Anforderungen sind in
  [docs/implementation_spec.md](docs/implementation_spec.md) dokumentiert.
* Unter `src/auto_dj/` befindet sich eine Python-Codebasis, die zentrale Dienste als
  lauffähige Skeletons bereitstellt (Audio-Engine, Musik-Analyse, DJ-Brain,
  Queue-Verwaltung, OSC-Anbindung und Web-API).
* Das Projekt wird über `pyproject.toml` konfiguriert und nutzt FastAPI, SQLAlchemy und
  python-osc als Kernbibliotheken.

## Quickstart

```bash
# Abhängigkeiten installieren, Datenbanktabellen erstellen und Standard-Admin anlegen
# (legt standardmäßig den PostgreSQL-User "auto-dj" mit dem Passwort "auto-dj" an)
#
# Falls PostgreSQL Superuser-Zugangsdaten erforderlich sind, fragt das Skript das
# Passwort interaktiv ab. Für einen nicht-interaktiven Betrieb können die Werte
# vorab gesetzt werden, z. B.:
# export AUTO_DJ_SUPERUSER_PASSWORD="<PASSWORD>"
# export AUTO_DJ_SUPERUSER_USER="postgres"
# export AUTO_DJ_SUPERUSER_HOST="localhost"
# export AUTO_DJ_SUPERUSER_PORT="5432"
# export AUTO_DJ_SUPERUSER_DB="postgres"
# (alternativ kann weiterhin AUTO_DJ_SUPERUSER_DSN gesetzt werden)
#
# Ist die Datenbank bereits provisioniert, kann der Rollendialog übersprungen werden:
# export AUTO_DJ_SKIP_DB_INIT=1
./scripts/install.sh

# Dienste starten (Beispiel)
python -m auto_dj web    # Startet die Web-API (FastAPI/Uvicorn)
python -m auto_dj engine # Startet den Audio-Engine-Skeleton
python -m auto_dj brain  # Initialisiert die Brain-Komponenten
```

Der Installer exportiert automatisch eine `AUTO_DJ_DATABASE_DSN`, sodass sich der Python-Code
mit dem Datenbank-Benutzer `auto-dj` und dem gleichnamigen Passwort verbindet. Host, Port,
Datenbankname, Benutzername und Passwort können bei Bedarf über die Umgebungsvariablen
`AUTO_DJ_DB_HOST`, `AUTO_DJ_DB_PORT`, `AUTO_DJ_DB_NAME`, `AUTO_DJ_DB_USER` und
`AUTO_DJ_DB_PASSWORD` vor dem Aufruf von `install.sh` überschrieben werden.

Der initiale Admin-Login lautet `admin` / `Admin123` und kann nach der Anmeldung im
Admin-Frontend (`/admin`) geändert werden.
