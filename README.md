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
# Das Skript legt standardmäßig Log-Verzeichnisse unter ./logs an. Für eigene
# Pfade können vorab z. B. gesetzt werden:
# export AUTO_DJ_RUNTIME_LOG_ROOT="/home/pi/autodj/logs/runtime"
# export AUTO_DJ_PERSISTENT_LOG_ROOT="/home/pi/autodj/logs/persistent"
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
`AUTO_DJ_DB_PASSWORD` vor dem Aufruf von `install.sh` überschrieben werden. Laufzeit- und
Persistenz-Logs lassen sich jederzeit über `AUTO_DJ_RUNTIME_LOG_ROOT` sowie
`AUTO_DJ_PERSISTENT_LOG_ROOT` auf eigene, beschreibbare Verzeichnisse umbiegen. Falls keine
Overrides gesetzt sind und die Standardpfade unter `/run/auto-dj` bzw. `/var/log/auto-dj`
nicht beschreibbar sind, fällt die Anwendung automatisch auf `~/.auto-dj/logs/runtime` und
`~/.auto-dj/logs/persistent` zurück.

Wer das Setup ohne das Shell-Skript ausführt (`python -m auto_dj.setup --ensure-database`),
erhält die gleiche Passwort-Abfrage. Alternativ können `AUTO_DJ_SUPERUSER_DSN` oder
`AUTO_DJ_SUPERUSER_PASSWORD` zur Authentifizierung gesetzt werden.

Der initiale Admin-Login lautet `admin` / `Admin123` und wird direkt unter dem Formular auf
der Admin-Anmeldeseite angezeigt. Über den Link mit dem ⚙️-Symbol im Footer der Gäste-Seite
gelangst du zum Login. Zusätzlich findest du im Admin-Dashboard unter **Protokolle & Diagnose →
Admin-Zugänge** jederzeit eine Übersicht aller vorhandenen Accounts inklusive letzter
Anmeldung. Sollte das Passwort verloren gehen, kannst du über den Button
**„Passwort zurücksetzen“** auf der Login-Seite mit dem Sicherheitscode `19042005` ein neues
Kennwort vergeben. Der Code lässt sich bei Bedarf über die Umgebungsvariable
`AUTO_DJ_ADMIN_RESET_CODE` anpassen.

Nach erfolgreichem Login steht ein moduliertes Kontrollzentrum mit folgenden Bereichen bereit:

* **Systemübersicht** – Now-/Next-Ansicht, Queue-Verwaltung, Echtzeit-Metriken (CPU, RAM,
  Temperatur, XRUNs, OSC-Status, Netzmodus) sowie Schalter für „Nebelmaschine aktiv“,
  „Superscenes erlaubt“ und „Öffentlich erreichbar“.
* **Audio & Mixer** – Scan und Auswahl der verfügbaren ALSA/Pulse-Ausgabegeräte inklusive
  Neustart-Hinweis sowie Konfiguration von Crossfade, Lautstärke- und Bass-Kurven,
  Filter-Übergängen und Time-Stretch-Modi.
* **Musikbibliothek** – Überblick über analysierte Tracks, Quarantänepfad und anpassbare Pfad-
  bzw. Datenbank-Einstellungen.
  * Hinweis: Der Begriff `DATABASE_URL` steht für die vollständige PostgreSQL-Verbindungs-
    zeichenkette im Format `postgresql://benutzer:passwort@host:5432/datenbank`. Darüber stellt der
    Auto-DJ die Verbindung zur Datenbank her.
* **Autoplay-Playlisten** – Kuratiere Playlisten, füge Titel direkt aus der Bibliothek hinzu und
  bestimme, welche Sammlung automatisch einspringt, sobald die Queue leer ist. Die Tracks werden
  in Listenreihenfolge abgespielt und der Durchlauf nach Änderungen automatisch zurückgesetzt.
* **Licht & Daslight 5** – Verwaltung der OSC-Zielparameter, Superscene- und Nebel-Toggles
  sowie ein Bar-Reset-Trigger für die Daslight-Synchronisation.
* **Analyse & KI** – Feinjustierung der DJ-Brain-Gewichtungen (Key/BPM/Energie/Genre/Recency/
  Requests) inklusive Soft-Spacing-Konfiguration.
* **Protokolle & Diagnose** – Pfade für Runtime-/Persistenz-Logs, Cache und Konfiguration,
  letzte Fehlermeldung sowie Passwortpflege und Übersicht für alle Admin-Accounts.

Die Gäste-Oberfläche verweist über ein dezentes ⚙️-Icon im Footer direkt auf die Admin-Anmeldung.
