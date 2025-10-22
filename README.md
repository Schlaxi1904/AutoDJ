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
./scripts/install.sh

# Dienste starten (Beispiel)
python -m auto_dj web    # Startet die Web-API (FastAPI/Uvicorn)
python -m auto_dj engine # Startet den Audio-Engine-Skeleton
python -m auto_dj brain  # Initialisiert die Brain-Komponenten
```

Vor dem ersten Start sollten PostgreSQL-Zugangsdaten im Konfigurationsmodul angepasst und
abhängige Dienste bereitgestellt werden. Der initiale Admin-Login lautet `admin` / `Admin123`
und kann nach der Anmeldung im Admin-Frontend (`/admin`) geändert werden.
