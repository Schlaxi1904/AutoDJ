"""DJ planning logic scaffolding."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable, List, Optional

from ..config import AutoDjConfig
from ..database.models import QueueEntry, Track

logger = logging.getLogger(__name__)


@dataclass
class TransitionScore:
    from_track: Track
    to_track: Track
    score: float


class DjBrain:
    def __init__(self, config: AutoDjConfig) -> None:
        self._config = config

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
        score += weights.request if candidate.flags.get("requested") else 0.0
        return score
