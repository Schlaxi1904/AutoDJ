"""Queue management primitives."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy import func

from ..config import QueuePolicy
from ..database.models import QueueEntry, Track
from ..database.session import Database

logger = logging.getLogger(__name__)


@dataclass
class QueueStatus:
    entries: List[QueueEntry]
    remaining_slots: int


class QueueManager:
    def __init__(self, database: Database, policy: QueuePolicy) -> None:
        self._db = database
        self._policy = policy

    def enqueue(self, track: Track, source: str, guest_session: Optional[str]) -> QueueEntry:
        with self._db.session() as session:
            count = session.query(QueueEntry).count()
            if count >= self._policy.max_length:
                raise RuntimeError("Queue is full")
            entry = QueueEntry(track=track, source=source, guest_session=guest_session)
            session.add(entry)
            session.flush()
            session.refresh(entry)
            logger.info("Queued track", extra={"track": track.title, "source": source})
            return entry

    def next_track(self) -> Optional[QueueEntry]:
        with self._db.session() as session:
            entry = (
                session.query(QueueEntry)
                .filter(QueueEntry.status == "pending")
                .order_by(QueueEntry.created_at.asc())
                .first()
            )
            if entry:
                entry.status = "playing"
            return entry

    def status(self) -> QueueStatus:
        with self._db.session() as session:
            entries = list(session.query(QueueEntry).order_by(QueueEntry.created_at.asc()).all())
            remaining = self._policy.max_length - len(entries)
            return QueueStatus(entries, remaining)

    def current_track(self) -> Optional[QueueEntry]:
        """Return the queue entry that is currently playing, if any."""

        with self._db.session() as session:
            return (
                session.query(QueueEntry)
                .filter(QueueEntry.status == "playing")
                .order_by(QueueEntry.created_at.desc())
                .first()
            )

    def remove(self, entry_id: int) -> None:
        """Remove an entry from the queue."""

        with self._db.session() as session:
            entry = session.get(QueueEntry, entry_id)
            if not entry:
                raise ValueError("Queue entry not found")
            session.delete(entry)

    def promote(self, entry_id: int) -> QueueEntry:
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
            return entry

    def mark_playing(self, entry_id: int) -> QueueEntry:
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
            return entry
