"""Runtime diagnostics for the Auto-DJ stack."""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from typing import Callable, Iterable, List, Tuple

from ..config import AutoDjConfig, load_config
from ..database.models import QueueEntry, Track
from ..database.session import Database
from ..services.dj_brain import DjBrain
from ..services.playlists import PlaylistService
from ..services.queue import QueueManager


class DiagnosticError(RuntimeError):
    """Raised when a diagnostic check fails."""


@dataclass
class DiagnosticResult:
    name: str
    success: bool
    detail: str


@dataclass
class DiagnosticContext:
    config: AutoDjConfig
    database: Database
    playlists: PlaylistService
    queue: QueueManager
    brain: DjBrain


def _ensure_database(config: AutoDjConfig) -> Database:
    database = Database(config.database)
    database.create_all()
    return database


def check_music_library(context: DiagnosticContext) -> str:
    with context.database.session() as session:
        track_count = session.query(Track).count()
        if track_count == 0:
            raise DiagnosticError(
                "Keine Titel in der Datenbank gefunden. Bitte Musikordner prüfen."
            )
        preview = (
            session.query(Track)
            .order_by(Track.added_at.desc())
            .limit(3)
            .all()
        )
        sample = ", ".join(f"{track.artist} – {track.title}" for track in preview)
    if not sample:
        sample = "Keine Vorschau verfügbar"
    return f"{track_count} Songs erkannt (Beispiel: {sample})"


def check_queue_flow(context: DiagnosticContext) -> str:
    with context.database.session() as session:
        track = session.query(Track).order_by(Track.added_at.desc()).first()
        if not track:
            raise DiagnosticError("Keine Tracks verfügbar, Warteschlange kann nicht getestet werden.")
        previous_statuses = {
            entry.id: entry.status
            for entry in session.query(QueueEntry).all()
        }

    entry = None
    try:
        try:
            entry = context.queue.enqueue(track, "diagnostic", "system-check")
        except RuntimeError as exc:
            raise DiagnosticError(
                "Warteschlange voll – bitte Einträge bereinigen und erneut testen."
            ) from exc
        context.queue.mark_playing(entry.id)
        playing = context.queue.current_track()
        if not playing or playing.id != entry.id:
            raise DiagnosticError("Warteschlange konnte Eintrag nicht als spielend markieren.")
        return f"Warteschlange funktionsfähig (Testtitel: {track.artist} – {track.title})"
    finally:
        if entry:
            try:
                context.queue.remove(entry.id)
            except ValueError:
                pass
        with context.database.session() as session:
            for entry_id, status in previous_statuses.items():
                existing = session.get(QueueEntry, entry_id)
                if existing:
                    existing.status = status


def check_dj_brain(context: DiagnosticContext) -> str:
    with context.database.session() as session:
        tracks = (
            session.query(Track)
            .order_by(Track.energy_avg.desc())
            .limit(5)
            .all()
        )
    if len(tracks) < 2:
        raise DiagnosticError(
            "Zu wenige Tracks zur Bewertung gefunden. Mindestens zwei Songs erforderlich."
        )
    reference = tracks[0]
    candidates = tracks[1:]
    score = context.brain.choose_next_track(reference, candidates)
    if not score:
        raise DiagnosticError("DJ-Brain konnte keinen passenden Titel auswählen.")
    return (
        "DJ-Brain ok – nächster Titel: "
        f"{score.to_track.artist} – {score.to_track.title} (Score {score.score:.2f})"
    )


CheckFunc = Callable[[DiagnosticContext], str]


CHECKS: List[Tuple[str, CheckFunc]] = [
    ("music_library", check_music_library),
    ("queue_flow", check_queue_flow),
    ("dj_brain", check_dj_brain),
]


def run_diagnostics(config: AutoDjConfig | None = None) -> Tuple[int, List[DiagnosticResult]]:
    config = config or load_config()
    database = _ensure_database(config)
    playlists = PlaylistService(database)
    queue = QueueManager(database, config.queue_policy, playlists)
    brain = DjBrain(config)
    context = DiagnosticContext(
        config=config,
        database=database,
        playlists=playlists,
        queue=queue,
        brain=brain,
    )

    results: List[DiagnosticResult] = []
    exit_code = 0
    for name, check in CHECKS:
        try:
            detail = check(context)
        except DiagnosticError as exc:
            results.append(DiagnosticResult(name, False, str(exc)))
            exit_code = max(exit_code, 1)
        except Exception as exc:  # pragma: no cover - defensive guard
            results.append(
                DiagnosticResult(name, False, f"Unerwarteter Fehler: {exc}")
            )
            exit_code = 2
        else:
            results.append(DiagnosticResult(name, True, detail))
    return exit_code, results


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Führt einen System-Check für Auto-DJ aus."
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Ausgabe als JSON (Maschinenlesbar).",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    exit_code, results = run_diagnostics()
    if args.json:
        import json

        payload = {
            "exit_code": exit_code,
            "checks": [result.__dict__ for result in results],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for result in results:
            status = "OK" if result.success else "FEHLER"
            print(f"[{status}] {result.name}: {result.detail}")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
