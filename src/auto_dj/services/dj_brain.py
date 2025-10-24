"""DJ planning logic scaffolding."""
from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass
from time import sleep
from typing import Deque, Iterable, Optional, Sequence, Set, TYPE_CHECKING

from ..config import AutoDjConfig
from ..database.models import Track

if TYPE_CHECKING:  # pragma: no cover - typing only
    from ..database.session import Database
    from .queue import QueueManager


logger = logging.getLogger(__name__)


@dataclass
class TransitionScore:
    from_track: Track
    to_track: Track
    score: float


class DjBrain:
    def __init__(self, config: AutoDjConfig) -> None:
        self._config = config
        self._recent_track_ids: Deque[int] = deque(maxlen=16)

    def run_service(
        self,
        database: "Database",
        queue: "QueueManager",
        *,
        poll_interval: float = 5.0,
    ) -> None:
        """Continuously plan the next track when the queue runs low."""

        logger.info(
            "DJ brain service started",
            extra={"poll_interval_s": poll_interval},
        )
        try:
            while True:
                try:
                    planned = self.plan_next(database, queue)
                    if planned:
                        logger.debug("DJ brain enqueued a track to keep the flow running")
                except Exception as exc:  # pragma: no cover - defensive guard
                    logger.exception("DJ brain tick failed", extra={"error": str(exc)})
                sleep(poll_interval)
        except KeyboardInterrupt:  # pragma: no cover - service shutdown
            logger.info("DJ brain interrupted, shutting down")

    def plan_next(self, database: "Database", queue: "QueueManager") -> bool:
        """Plan the next track once and enqueue it when needed.

        Returns ``True`` when a track was enqueued, otherwise ``False``.
        """

        status = queue.status()
        pending_entries = [entry for entry in status.entries if entry.status == "pending"]
        if status.remaining_slots <= 0:
            logger.debug("Queue is full; skipping planning step")
            return False
        if pending_entries:
            logger.debug("Queue already has pending tracks; no action taken")
            return False

        playing_entry = next((entry for entry in status.entries if entry.status == "playing"), None)
        playing_track_id = playing_entry.track_id if playing_entry else None

        exclude_ids: Set[int] = {entry.track_id for entry in status.entries}
        exclude_ids.update(self._recent_track_ids)

        candidates, current_track = self._load_candidates(database, exclude_ids, playing_track_id)
        if not candidates:
            logger.debug("No candidate tracks available for planning")
            return False

        decision = self.choose_next_track(current_track, candidates)
        if not decision:
            logger.debug("No suitable transition candidate found")
            return False

        entry = queue.enqueue(decision.to_track.id, "auto", None)
        self._recent_track_ids.append(decision.to_track.id)
        logger.info(
            "DJ brain queued track",
            extra={"track": decision.to_track.title, "entry_id": entry.id},
        )
        return True

    def choose_next_track(self, current: Optional[Track], candidates: Iterable[Track]) -> Optional[TransitionScore]:
        best_score = float("-inf")
        best: Optional[TransitionScore] = None
        for candidate in candidates:
            score = self._score_track(current, candidate)
            if score > best_score:
                best_score = score
                best = TransitionScore(current, candidate, score)
        if best:
            logger.info("Selected track", extra={"track": best.to_track.title, "score": best.score})
        return best

    def _score_track(self, current: Optional[Track], candidate: Track) -> float:
        weights = self._config.brain_weights
        score = 0.0
        if current:
            bpm_diff = abs(current.bpm - candidate.bpm)
            score -= bpm_diff * weights.bpm
            score -= abs(current.energy_avg - candidate.energy_avg) * weights.energy
            if current.genre == candidate.genre:
                score += weights.genre
            else:
                score -= weights.genre
        score += weights.request if candidate.flags.get("requested") else 0.0
        return score

    def _load_candidates(
        self,
        database: "Database",
        exclude_ids: Set[int],
        playing_track_id: Optional[int],
        limit: int = 25,
    ) -> tuple[Sequence[Track], Optional[Track]]:
        """Fetch candidate tracks and the current playing track from the database."""

        with database.session() as session:
            current_track = session.get(Track, playing_track_id) if playing_track_id else None
            query = session.query(Track)
            if exclude_ids:
                query = query.filter(~Track.id.in_(exclude_ids))
            candidates = list(query.order_by(Track.energy_avg.desc()).limit(limit).all())
        return candidates, current_track
