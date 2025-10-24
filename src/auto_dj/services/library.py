"""Music library scanning and indexing helpers."""
from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from sqlalchemy import func, select

from ..audio.analyzer import Analyzer, summarize_music_directory
from ..config import AutoDjConfig
from ..database.models import Track
from ..database.session import Database
from .settings import SettingsService

try:  # pragma: no cover - dependency guaranteed in production but optional in tests
    from mutagen import File as MutagenFile  # type: ignore
except Exception:  # pragma: no cover - mutagen import failure shouldn't crash tests
    MutagenFile = None  # type: ignore

logger = logging.getLogger(__name__)


@dataclass
class TrackMetadata:
    """Normalized metadata extracted from an audio file."""

    artist: str
    title: str
    duration_ms: int
    lufs_i: float
    true_peak_db: float
    bpm: float
    key_camelot: str
    genre: str
    energy_avg: float


@dataclass
class LibraryState:
    """Snapshot of the current library configuration and statistics."""

    music_path: Path
    database_dsn: str
    track_count: int
    filesystem_count: int
    filesystem_preview: List[str]
    quarantine_path: Path


@dataclass
class LibraryScanReport:
    """Summary of a library indexing run."""

    total_files: int
    inserted: int
    updated: int
    skipped: int
    errors: List[str]


class LibraryService:
    """High level operations for the music library."""

    SETTINGS_KEY = "library.settings"
    META_KEY = "library.scan_meta"
    AUTO_ATTEMPT_COOLDOWN = timedelta(minutes=10)

    def __init__(
        self,
        database: Database,
        config: AutoDjConfig,
        settings: SettingsService,
        analyzer_factory: type[Analyzer] = Analyzer,
    ) -> None:
        self._db = database
        self._config = config
        self._settings = settings
        self._analyzer_factory = analyzer_factory

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def get_settings(self) -> Dict[str, str]:
        defaults = self._default_settings()
        stored = self._settings.get_dict(self.SETTINGS_KEY, {})
        merged: Dict[str, str] = {**defaults}
        for key, value in stored.items():
            if isinstance(value, str):
                merged[key] = value
        return merged

    def update_settings(
        self,
        *,
        music_path: Optional[str] = None,
        database_dsn: Optional[str] = None,
    ) -> LibraryState:
        updates: Dict[str, str] = {}
        if music_path is not None:
            stripped = music_path.strip()
            if stripped:
                updates["music_path"] = stripped
        if database_dsn is not None:
            stripped = database_dsn.strip()
            if stripped:
                updates["database_dsn"] = stripped
        if updates:
            self._settings.update_dict(self.SETTINGS_KEY, updates)
        return self.state(auto_index=False)

    def state(self, *, auto_index: bool = True) -> LibraryState:
        snapshot = self._gather_state()
        if (
            auto_index
            and snapshot.filesystem_count > 0
            and snapshot.track_count == 0
            and self._should_auto_index(snapshot.music_path)
        ):
            logger.info(
                "Triggering automatic library index", extra={"music_path": str(snapshot.music_path)}
            )
            report = self.scan(snapshot.music_path, auto_triggered=True)
            if report.inserted or report.updated:
                snapshot = self._gather_state()
        return snapshot

    def scan(
        self, music_path: Optional[Path] = None, *, auto_triggered: bool = False
    ) -> LibraryScanReport:
        settings = self.get_settings()
        root = Path(music_path or settings["music_path"]).expanduser()
        normalized_root = self._normalize_path(root)

        if not root.exists() or not root.is_dir():
            message = f"Musikpfad nicht gefunden: {normalized_root}"
            logger.warning(message)
            report = LibraryScanReport(0, 0, 0, 0, [message])
            self._record_scan_meta(report, normalized_root, auto_triggered)
            return report

        analyzer = self._analyzer_factory(root)

        total_files = 0
        inserted = 0
        updated = 0
        skipped = 0
        errors: List[str] = []

        with self._db.session() as session:
            existing = {
                self._normalize_path(Path(track.path)): track
                for track in session.execute(select(Track)).scalars()
            }

            for candidate in analyzer.scan():
                total_files += 1
                normalized_path = self._normalize_path(candidate)

                try:
                    metadata = self._extract_metadata(candidate)
                except Exception as exc:  # pragma: no cover - defensive logging
                    errors.append(f"{candidate.name}: {exc}")
                    logger.debug("Metadata extraction failed", exc_info=exc)
                    skipped += 1
                    continue

                track = existing.get(normalized_path)
                if track is None:
                    record = Track(
                        path=normalized_path,
                        cover_path=None,
                        flags={},
                        **asdict(metadata),
                    )
                    session.add(record)
                    inserted += 1
                    existing[normalized_path] = record
                    continue

                changed = False
                for field_name, value in asdict(metadata).items():
                    current = getattr(track, field_name)
                    if current != value:
                        setattr(track, field_name, value)
                        changed = True
                if changed:
                    updated += 1
                else:
                    skipped += 1

        report = LibraryScanReport(total_files, inserted, updated, skipped, errors)
        logger.info(
            "Library scan complete",
            extra={
                "music_path": normalized_root,
                "total": total_files,
                "inserted": inserted,
                "updated": updated,
                "skipped": skipped,
                "errors": len(errors),
            },
        )
        self._record_scan_meta(report, normalized_root, auto_triggered)
        return report

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _gather_state(self) -> LibraryState:
        settings = self.get_settings()
        music_path = Path(settings["music_path"]).expanduser()
        filesystem_count, filesystem_preview = summarize_music_directory(music_path)
        track_count = self._count_tracks()
        quarantine_path = music_path / "_quarantine"
        return LibraryState(
            music_path=music_path,
            database_dsn=settings["database_dsn"],
            track_count=track_count,
            filesystem_count=filesystem_count,
            filesystem_preview=filesystem_preview,
            quarantine_path=quarantine_path,
        )

    def _count_tracks(self) -> int:
        with self._db.session() as session:
            return int(session.execute(select(func.count(Track.id))).scalar_one())

    def _should_auto_index(self, music_path: Path) -> bool:
        meta = self._settings.get_dict(self.META_KEY, {})
        last_path = meta.get("last_scan_path")
        last_auto = meta.get("last_auto_attempt_at")
        if last_path and last_path != self._normalize_path(music_path):
            return True
        if not last_auto:
            return True
        try:
            last_auto_dt = datetime.fromisoformat(str(last_auto))
        except ValueError:
            return True
        return datetime.utcnow() - last_auto_dt >= self.AUTO_ATTEMPT_COOLDOWN

    def _record_scan_meta(
        self, report: LibraryScanReport, music_path: str, auto_triggered: bool
    ) -> None:
        meta = self._settings.get_dict(self.META_KEY, {})
        timestamp = datetime.utcnow().isoformat()
        meta.update(
            {
                "last_scan_at": timestamp,
                "last_scan_path": music_path,
                "last_scan_total": report.total_files,
                "last_scan_inserted": report.inserted,
                "last_scan_updated": report.updated,
                "last_scan_skipped": report.skipped,
                "last_scan_error_count": len(report.errors),
            }
        )
        if auto_triggered:
            meta["last_auto_attempt_at"] = timestamp
        self._settings.set(self.META_KEY, meta)

    def _default_settings(self) -> Dict[str, str]:
        return {
            "music_path": str(self._config.paths.music_root),
            "database_dsn": self._config.database.dsn,
        }

    @staticmethod
    def _normalize_path(path: Path) -> str:
        try:
            return str(path.expanduser().resolve())
        except Exception:  # pragma: no cover - defensive normalization
            return str(path)

    def _extract_metadata(self, path: Path) -> TrackMetadata:
        audio = self._load_audio_metadata(path)

        artist = self._first_tag(audio, ["artist", "ARTIST", "TPE1", "TPE2", "albumartist"])
        title = self._first_tag(audio, ["title", "TITLE", "TIT2"])
        genre = self._first_tag(audio, ["genre", "GENRE", "TCON"])
        bpm_raw = self._first_tag(audio, ["bpm", "TBPM"])
        key_raw = self._first_tag(audio, ["initialkey", "TKEY"])

        if not artist or not title:
            fallback_artist, fallback_title = self._guess_from_filename(path)
            artist = artist or fallback_artist
            title = title or fallback_title

        duration_ms = 0
        if audio is not None:
            info = getattr(audio, "info", None)
            length = getattr(info, "length", None)
            if isinstance(length, (int, float)) and length > 0:
                duration_ms = int(length * 1000)

        bpm = self._coerce_float(bpm_raw, default=120.0)
        key_camelot = self._normalize_key(key_raw)
        genre_value = genre or "unknown"
        energy = self._estimate_energy(bpm)

        return TrackMetadata(
            artist=artist,
            title=title,
            duration_ms=duration_ms,
            lufs_i=-12.0,
            true_peak_db=-1.0,
            bpm=bpm,
            key_camelot=key_camelot,
            genre=genre_value,
            energy_avg=energy,
        )

    def _load_audio_metadata(self, path: Path):
        if MutagenFile is None:
            return None
        try:
            return MutagenFile(path, easy=True)  # type: ignore[arg-type]
        except Exception:  # pragma: no cover - fallback to strict parser
            try:
                return MutagenFile(path)  # type: ignore[call-arg]
            except Exception:
                return None

    @staticmethod
    def _first_tag(audio, keys: Iterable[str]) -> Optional[str]:
        if audio is None:
            return None
        tags = getattr(audio, "tags", None)
        if not tags:
            return None
        for key in keys:
            try:
                value = tags.get(key)
            except Exception:  # pragma: no cover - mutagen edge case
                continue
            if not value:
                continue
            if isinstance(value, list):
                candidate = value[0]
            else:
                candidate = value
            if candidate is None:
                continue
            return str(candidate).strip()
        return None

    @staticmethod
    def _guess_from_filename(path: Path) -> tuple[str, str]:
        stem = path.stem
        if " - " in stem:
            artist, title = stem.split(" - ", 1)
            return artist.strip() or "Unknown Artist", title.strip() or stem
        return "Unknown Artist", stem.strip() or path.name

    @staticmethod
    def _coerce_float(value: Optional[str], default: float) -> float:
        if not value:
            return default
        try:
            return float(str(value).strip())
        except ValueError:
            return default

    @staticmethod
    def _normalize_key(value: Optional[str]) -> str:
        if not value:
            return "8A"
        cleaned = str(value).strip().upper()
        if not cleaned:
            return "8A"
        if len(cleaned) <= 3:
            return cleaned
        return cleaned[:3]

    @staticmethod
    def _estimate_energy(bpm: float) -> float:
        normalized = max(0.0, min(bpm / 160.0, 1.0))
        return round(max(0.2, normalized), 3)


__all__ = ["LibraryService", "LibraryScanReport", "LibraryState"]

