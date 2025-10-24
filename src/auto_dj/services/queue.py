"""Queue management primitives."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.orm import selectinload

from ..config import QueuePolicy
from ..database.models import QueueEntry, Track
from .playlists import PlaylistService
from ..database.session import Database

logger = logging.getLogger(__name__)


@dataclass
class QueueTrackSnapshot:
    id: int
    artist: str
    title: str
    duration_ms: int
    bpm: float
    genre: str
    key_camelot: str
    energy_avg: float


@dataclass
class QueueEntrySnapshot:
    id: int
    track_id: int
    track: QueueTrackSnapshot
    source: str
    guest_session: Optional[str]
    created_at: datetime
    status: str


@dataclass
class QueueStatus:
    entries: List[QueueEntrySnapshot]
    remaining_slots: int


class QueueManager:
    def __init__(
        self,
        database: Database,
        policy: QueuePolicy,
        playlist_service: PlaylistService | None = None,
    ) -> None:
        self._db = database
        self._policy = policy
        self._playlists = playlist_service

    def enqueue(
        self, track: Track | int, source: str, guest_session: Optional[str]
    ) -> QueueEntrySnapshot:
        """Enqueue a track either by instance or primary key."""

        track_id = track if isinstance(track, int) else track.id

        with self._db.session() as session:
            count = session.query(QueueEntry).count()
            if count >= self._policy.max_length:
                raise RuntimeError("Queue is full")
            track_obj = session.get(Track, track_id)
            if not track_obj:
                raise ValueError("Track not found")
            entry = QueueEntry(track=track_obj, source=source, guest_session=guest_session)
            session.add(entry)
            session.flush()
            session.refresh(entry)
            snapshot = _snapshot_entry(entry)
            logger.info(
                "Queued track",
                extra={"track": track_obj.title, "source": source, "track_id": track_obj.id},
            )
            return snapshot

    def next_track(self) -> Optional[QueueEntrySnapshot]:
        with self._db.session() as session:
            entry = (
                session.query(QueueEntry)
                .options(selectinload(QueueEntry.track))
                .filter(QueueEntry.status == "pending")
                .order_by(QueueEntry.created_at.asc())
                .first()
            )
            if entry:
                entry.status = "playing"
                session.flush()
                session.refresh(entry)
                return _snapshot_entry(entry)

        if not self._playlists:
            return None

        track_id = self._playlists.next_autoplay_track()
        if track_id is None:
            return None

        with self._db.session() as session:
            track = session.get(Track, track_id)
            if not track:
                return None
            entry = QueueEntry(track=track, source="autoplay", guest_session=None)
            entry.status = "playing"
            session.add(entry)
            session.flush()
            session.refresh(entry)
            return _snapshot_entry(entry)

    def status(self) -> QueueStatus:
        with self._db.session() as session:
            entries = (
                session.query(QueueEntry)
                .options(selectinload(QueueEntry.track))
                .order_by(QueueEntry.created_at.asc())
                .all()
            )
            remaining = self._policy.max_length - len(entries)
            snapshots = [_snapshot_entry(entry) for entry in entries]
            return QueueStatus(snapshots, remaining)

    def current_track(self) -> Optional[QueueEntrySnapshot]:
        """Return the queue entry that is currently playing, if any."""

        with self._db.session() as session:
            entry = (
                session.query(QueueEntry)
                .options(selectinload(QueueEntry.track))
                .filter(QueueEntry.status == "playing")
                .order_by(QueueEntry.created_at.desc())
                .first()
            )
            return _snapshot_entry(entry) if entry else None

    def remove(self, entry_id: int) -> None:
        """Remove an entry from the queue."""

        with self._db.session() as session:
            entry = session.get(QueueEntry, entry_id)
            if not entry:
                raise ValueError("Queue entry not found")
            session.delete(entry)

    def promote(self, entry_id: int) -> QueueEntrySnapshot:
        """Move an entry to the front of the queue by adjusting its creation time."""

        with self._db.session() as session:
            entry = session.get(QueueEntry, entry_id)
            if not entry:
                raise ValueError("Queue entry not found")

            earliest = (
                session.query(func.min(QueueEntry.created_at))
                .filter(QueueEntry.id != entry_id)
                .scalar()
            )

            new_created_at = earliest - timedelta(milliseconds=1) if earliest else datetime.utcnow()
            entry.created_at = new_created_at
            session.flush()
            session.refresh(entry)
            return _snapshot_entry(entry)

    def mark_playing(self, entry_id: int) -> QueueEntrySnapshot:
        """Mark a queue entry as the currently playing track."""

        with self._db.session() as session:
            entry = session.get(QueueEntry, entry_id)
            if not entry:
                raise ValueError("Queue entry not found")

            session.query(QueueEntry).filter(QueueEntry.status == "playing").update(
                {QueueEntry.status: "played"}, synchronize_session=False
            )
            entry.status = "playing"
            session.flush()
            session.refresh(entry)
            return _snapshot_entry(entry)


def _snapshot_entry(entry: QueueEntry) -> QueueEntrySnapshot:
    track = entry.track
    track_snapshot = QueueTrackSnapshot(
        id=track.id,
        artist=track.artist,
        title=track.title,
        duration_ms=track.duration_ms,
        bpm=track.bpm,
        genre=track.genre,
        key_camelot=track.key_camelot,
        energy_avg=track.energy_avg,
    )
    return QueueEntrySnapshot(
        id=entry.id,
        track_id=entry.track_id,
        track=track_snapshot,
        source=entry.source,
        guest_session=entry.guest_session,
        created_at=entry.created_at,
        status=entry.status,
    )
