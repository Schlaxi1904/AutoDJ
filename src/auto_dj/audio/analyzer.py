"""Audio analysis pipeline stubs."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from ..database.models import Track

logger = logging.getLogger(__name__)


@dataclass
class AnalysisResult:
    track: Track
    beatgrid: dict
    energy_curve: dict
    structure: dict


class Analyzer:
    """Batch analyzer that enriches tracks on startup."""

    def __init__(self, music_root: Path) -> None:
        self._music_root = music_root

    def scan(self) -> Iterator[Path]:
        for path in sorted(self._music_root.glob("**/*")):
            if path.suffix.lower() in {".flac", ".mp3", ".wav"}:
                yield path

    def analyze(self, path: Path) -> AnalysisResult:
        logger.info("Analyzing track", extra={"path": str(path)})
        # Placeholder results until the DSP pipeline is implemented.
        track = Track(
            path=str(path),
            artist="Unknown",
            title=path.stem,
            duration_ms=0,
            lufs_i=-14.0,
            true_peak_db=-1.0,
            bpm=120.0,
            key_camelot="8A",
            genre="unknown",
            energy_avg=0.5,
        )
        return AnalysisResult(track, beatgrid={}, energy_curve={}, structure={})
