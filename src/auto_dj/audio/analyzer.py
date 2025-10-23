"""Audio analysis pipeline stubs."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Iterator, List, Tuple

if TYPE_CHECKING:  # pragma: no cover - only needed for type checking
    from ..database.models import Track

logger = logging.getLogger(__name__)


SUPPORTED_MUSIC_EXTENSIONS = {".flac", ".mp3", ".wav"}


@dataclass
class AnalysisResult:
    track: "Track"
    beatgrid: dict
    energy_curve: dict
    structure: dict


class Analyzer:
    """Batch analyzer that enriches tracks on startup."""

    def __init__(self, music_root: Path) -> None:
        self._music_root = music_root

    def scan(self) -> Iterator[Path]:
        for path in sorted(self._music_root.glob("**/*")):
            if path.suffix.lower() in SUPPORTED_MUSIC_EXTENSIONS:
                yield path

    def analyze(self, path: Path) -> AnalysisResult:
        logger.info("Analyzing track", extra={"path": str(path)})
        # Placeholder results until the DSP pipeline is implemented.
        from ..database.models import Track  # local import avoids optional dependency at import time

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


def summarize_music_directory(
    music_root: Path, preview_limit: int = 5
) -> Tuple[int, List[str]]:
    """Return the number of supported audio files and a preview list.

    The helper is primarily used by the admin dashboard to provide quick
    feedback about the currently selected music root. Paths are reported
    relative to *music_root* whenever possible.
    """

    try:
        expanded = music_root.expanduser()
    except Exception:
        return 0, []

    if not expanded.exists() or not expanded.is_dir():
        return 0, []

    analyzer = Analyzer(expanded)
    files = list(analyzer.scan())
    count = len(files)

    preview: List[str] = []
    for path in files[:preview_limit]:
        try:
            preview.append(str(path.relative_to(expanded)))
        except ValueError:
            preview.append(str(path))

    return count, preview


__all__ = ["AnalysisResult", "Analyzer", "SUPPORTED_MUSIC_EXTENSIONS", "summarize_music_directory"]
