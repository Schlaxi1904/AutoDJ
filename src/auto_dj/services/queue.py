"""Queue management primitives."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable, List, Optional

from sqlalchemy import select

from ..config import QueuePolicy
from ..database.models import QueueEntry, Request, Track
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
