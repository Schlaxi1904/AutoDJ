# Auto-DJ + Daslight 5 (OSC) – Implementierungs-Spezifikation

## 0. Ziel & Kontext

Das System spielt automatisch passende Musik, mischt Übergänge musikalisch sauber und steuert Licht über OSC an Daslight 5.

* Gäste reichen Songwünsche über eine Web-Seite ein (kein Login).
* Prioritäten: Stabilität, geringe Latenz, saubere Übergänge, einfache Bedienung.
* Zielumgebung: Raspberry Pi 4 (8 GB), dediziert für Auto-DJ.

## 1. Hardware & Betriebssystem

* Raspberry Pi 4 im aktiven Lüftergehäuse, Overclock bis ~2.0 GHz (Thermik < 75 °C).
* Audio-Ausgang: HiFiBerry XLR (Hardware-Revision 3), Class-Compliant; Samplerate 48 kHz, interne Verarbeitung in 32-bit float.
* Storage: USB3-SSD (1 TB), gesamte Musik in **einem** Ordner auf der SSD.
* Netzwerk: primär LAN, feste IPs für Pi und Daslight-PC.
* Boot-Policy: Beim Neustart kein Resume – frischer Start, erneuter Scan.

## 2. Audio-Engine (Realtime)

* Samplerate: 48 kHz, intern 32-bit float.
* Puffer: 256 Frames / 3 Perioden (Fallback 512/3).
* Formate: FLAC bevorzugt; zusätzlich MP3 und WAV abspielbar.
* Lautheit: „maximal laut“ – transparenter Limiter (True-Peak Ceiling −1.0 dBTP, Lookahead ~6 ms).
* Übergänge/Moves: Volume (Crossfade / FadeIn / FadeOut / Swap), Bass (Crossfade / FadeIn / FadeOut / Swap, Crossover ~120 Hz LR24), Filter (HP→LP / LP→HP mit exponentiellen Kurven), Time-Stretch optional pro Mix (max. ±6 %, bevorzugt im Break und nur auf incoming Track).
* Fehler-Panik: Soft-Mute/Fade-Out 500 ms.

## 3. Musik-Analyse & Bibliothek

* Ablage: `/media/music/` (ein Ordner).
* Beim Start: Vollscan & Analyse, erst danach UI vom Lade- in den Normalmodus wechseln.
* Pro Track speichern: Dauer, Lautheit (LUFS-I), True-Peak, BPM, Beatgrid (Downbeats), Key (Camelot), Genre, Energie (0–1), Artist, Titel, Cover.
* Cover: extrahieren und als Datei speichern (Original + Thumbs 256 px / 64 px); in der DB nur Pfade und Checksums.
* Fehlerhafte Dateien: nach `_quarantine/` verschieben, im Admin-UI auflisten.

## 4. Datenbank & Datenmodell

* Datenbank: PostgreSQL (WAL aktiv).
* Tabellen (Minimum):
  * `tracks(id, path, artist, title, duration_ms, lufs_i, true_peak_db, bpm, key_camelot, genre, energy_avg, cover_path, added_at, flags)`
  * `track_features(track_id, beatgrid_json, energy_curve_json, structure_json)`
  * `queue(id, track_id, source{auto|request|admin}, guest_session, created_at, status)`
  * `requests(id, track_id, guest_session, created_at, status)`
  * `settings(key, value_json)`
  * `blacklist(type{artist|title|track}, pattern, created_at)`
  * `audit(id, ts, svc, event, payload_json)`
* Persistenz-Policy: Blacklist dauerhaft.

## 5. DJ-Brain (Planungslogik)

* Ziele: harmonische Übergänge (Key/BPM/Energie), flexible „Soft-Spacing“ (ein Zwischen-Song bevorzugt, aber nicht erzwungen), Wünsche zeitnah, Flow bleibt intakt.
* Gewichte: Admin-konfigurierbar (Key/BPM/Energy/Genre/Recency/Request).
* Zonen: Warmup / Peak / Cooldown – dynamisch aus Songprofilen abgeleitet; Wünsche dürfen die Zone kreativ überbrücken (Bridge-Track).
* Lernen: Feedback speicherbar („Übergang gut/schlecht“, verbotene Track-Paare), künftig bei Auswahl berücksichtigen.
* Queue-Limits: max. 20 Einträge. Pro Gast mehrere Wünsche zulässig.
* Blacklist: global & dauerhaft; blockt Wunsch/Play automatisch.

## 6. Wünsche (Guests)

* Frontend: Suche in Bibliothek (Cover, Artist, Titel, Dauer).
* Kein Login, Session-Cookie ausreichend.
* Sichtbarkeit: Gäste sehen gesamte Queue; eigene Wünsche markiert.
* Rückmeldung: Sofort-Toast + ETA-Spanne (z. B. ~7–10 min).
* Spam-Schutz: Rate-Limit ~6/min/IP, sanftes Captcha bei Überschreitung.

## 7. Web-UI

### Gäste-UI

* Dark-First, mobil; Now Playing + Beat-Puls; Suchfeld; Queue-Preview; klare Microcopy.

### Admin-UI (neutral, sachlich)

* Dashboard: Now/Next, Queue (Drag&Drop), Mix-Profil, Spacing-Policy (Bevorzugt/Aus/Immer), Panic, System-Kacheln (CPU/Temp/XRUN/OSC), Nebel-Freigabe.
* Analyse-Modul (pro Song): Waveform + Beatgrid, Marker 🔵Break / 🟢Build / 🔴Drop (drag&drop), Regler für Empfindlichkeit (Break/Build/Drop), Genre/Tags, Effekt-Flags (Strobe/Fog/Superscene), Song-Profil speichern.
* Wünsche: Priorisieren, sperren (Blacklist), sofort spielen.
* Licht/OSC: Ziel-IP, Port, Status, Genre-Override, Superscenes Enable Toggle, Re-Sync (Bar-Reset).
* Netz/Erreichbarkeit: Toggle „Öffentlich erreichbar“ (optional SSL), Standard lokal/HTTP.

## 8. OSC ↔ Daslight 5

### 8.1 Adressraum (Pi → Daslight)

* `/beat` (float 0..1) – ¼-Beat-Phase
* `/bar` (int) – Downbeat-Zähler (nur auf Taktwechsel)
* `/energy` (0..1)
* `/mood/break` (0|1)
* `/mood/drop` (0|1)
* `/master/dimmer` (0..1)
* `/master/strobe` (0..1) – Duty-Cap beachten
* `/color/hue` (0..1), `/color/sat` (0..1)
* `/effect/speed` (0..1)
* `/fog` (0..1) – nur senden, wenn Admin Nebel freigegeben hat
* `/cue/<bank>/<scene>` (1=start, 0=stop)
* Superscenes (Bank 99): `/superscene/enable` (0|1), `/cue/99/<scene>` (1|0) – Autostart nur bei Titel-Match + enable=1 (bar-aligned, max. 1 gleichzeitig)

### 8.2 Adressraum (Daslight → Pi) – Inbound Whitelist

* Erlaubt: `genre/override`, `superscene/enable`, `superscene/stop`, `bar/reset`, optional `master/dimmer`.
* Rate-Limit & Debounce, keine Fluten; nur LAN.

### 8.3 Bank-Belegung (Genre)

* Bank 1: Techno
* Bank 2: Hardstyle
* Bank 3: House
* Bank 4: Pop
* Slots je Genre-Bank: 1=Idle, 2=Break, 3=Build, 4=Drop, 5=Outro.
* Bank 99: Superscenes (Songtitel-basiert; Normalisierung & Alias-Mapping im Admin pflegbar).

*Fixture-Programmierung erfolgt vollständig in Daslight. Der Pi triggert Cues & Master-Parameter.*

### 8.4 Betriebs-Regeln

* Bar-Align Pflicht für Build/Drop/Superscene-Starts.
* Strobe: nur Impact/Bursts, max. 2 Takte, Frequenz ≤ 10 Hz; Duty-Cap: Normal ≤ 0.30, „Reduziert“ ≤ 0.15.
* Fog: Auto-DJ darf kurz pulsen (z. B. Drops), nur wenn Admin „Nebelmaschine aktiv“ gesetzt hat.
* Pause/Break: Bei Energie-Schwelle unterschritten → keine `/beat`-Ticks; Cue → Break, Dimmer runter.
* Netz-Fallback: Bei Timeout → `/cue/<genre>/1` (Idle), Dimmer ~0.5; Sende-Rate drosseln, Auto-Recovery.

## 9. Superscenes (Bank 99)

* Globaler Toggle: `/superscene/enable` nur Admin.
* Autostart nur bei aktivem Toggle und Titel-Match (normalisiert; Alias-Tabelle nutzbar).
* Start immer am Downbeat; Standard-Dauer 16 Takte; max. 1 gleichzeitig; Rückkehr zur aktiven Genre-Szene nach Ende.
* Während Superscene: Genre-Cues pausieren oder gedimmt.

## 10. Sicherheit & Betrieb

* Admin-Login: Passwort (neutraler Admin-Bereich).
* Öffentlich/Lokal: Standard lokal/HTTP; optional öffentlich + SSL (Reverse-Proxy Caddy), Schalter im Admin.
* Blacklist: dauerhaft; auf Track/Artist/Title.
* Neustart: keine Wiederherstellung alter Sessions/Queue.

## 11. Logging, Monitoring, Qualität

* Live-Logs (RAM): 60 min Rolling; Audio/DSP (XRUN), Brain-Entscheide (Scores), OSC-Jitter, Wünsche/ETA.
* Persistenz: Bei WARN/ERROR Snapshot −5/+1 min auf SSD; Admin-Export möglich.
* Rote Hinweise im Admin bei: XRUN>0, Temp>75 °C, OSC-Timeout, DB-Fehler.
* Kleine Verbesserungs-Analyse im UI (z. B. „3 Drops zu früh“, „2 XRUNs“, „ETA p95 ±2 min“).

## 12. Deployment (Variante A – Nativ, empfohlen)

* systemd-Dienste: `auto-dj-engine.service`, `auto-dj-brain.service`, `auto-dj-osc.service`, `auto-dj-web.service`, `postgresql.service`, optional `caddy.service`.
* Start-Order: Postgres → Engine → Brain → OSC → Web → Caddy.
* Pfade: Musik `/media/music/`, Covers `/var/lib/auto-dj/covers/`, Cache `/var/lib/auto-dj/`, Config `/etc/auto-dj/`, Logs `/run/auto-dj/logs/` (persist auf Fehler → `/var/log/auto-dj/`).
* Updates: Online (signiertes Paket) + Offline (USB-Archiv) + Rollback (N-1).
* FS & Stromausfall: ext4 journaling, noatime, kein Swap; WAL aktiv; Integritätscheck beim Boot.

## 13. Tests & Abnahme (Must-Pass)

* Audio-Stabilität: 6 h Playback, XRUN=0, Temp < 75 °C.
* Licht-Sync: Beat-Jitter p95 < 2 ms, Bar-Align korrekt; Netz-Pull-Test → Fallback in ≤ 1 s.
* Wünsche: Queue-Limit 20 enforced; Mehrfach-Wünsche ok; ETA-Abweichung p95 ≤ ±2 min.
* Superscenes: nur bei Enable + Titel-Match; 1 gleichzeitig; Rückkehr zur Genre-Szene.
* Boot-Flow: Startscan → Ladebildschirm → Normalmodus erst bei konsistenter Analyse (≥ 98 % i. O. + mind. 1 spielbarer Track).

## 14. UX-Kernregeln

* Gäste: 2 Klicks bis Wunsch, unmittelbare Rückmeldung; Queue sichtbar.
* Admin: Alle kritischen Aktionen ≤ 2 Klicks (Priorisieren, Panic, Nebel-Enable, Profilwechsel).
* Barrierefreiheit: gute Kontraste, große Touch-Zonen; responsive (mobil-first).

## 15. Offene Implementierungsdetails (Codex umsetzen)

* Titel-Normalisierung für Superscenes (entferne Klammern, „feat./ft./with“, „radio edit/extended/remix“, Jahreszahlen; lowercasing, Diakritika entfernen, Sonderzeichen filtern).
* Alias-Mapping im Admin (optional) eingangstitel → szenen-slug.
* Learning-Store: Merke Admin-Feedback pro Song & Übergang; beeinflusst Scoring zukünftiger Planungen.
* Soft-Spacing: Standard: bevorzugt 1 Zwischen-Song zwischen Wünschen; Brain darf bei musikalisch passendem Flow back-to-back spielen (kein harter Zwang).

*Hinweis: Die Bank-Belegung für Genres (1–4) und Bank 99 für Superscenes ist strikt einzuhalten. OSC nur die genannten Pfade nutzen (inbound nur Whitelist). Realtime-Audio hat höchste Priorität (RT-Prio/Nice/CPU-Affinity), Logging-Overhead gering halten (TRACE nur temporär). UI-Zustände sauber trennen: Boot/Analyse → Normalmodus. Frischer Start nach Reboot (kein Resume von Queue/States).* 
