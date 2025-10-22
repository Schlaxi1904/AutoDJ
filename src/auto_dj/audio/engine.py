"""Realtime audio engine scaffolding."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from threading import Event, Thread
from time import sleep
from typing import Callable, Optional

from ..config import AudioConfig

logger = logging.getLogger(__name__)


@dataclass
class TrackPlayback:
    path: Path
    bpm: float
    key: str
    energy: float


class AudioEngine:
    """High-level audio engine façade.

    The actual DSP implementation will interface with a backend such as JACK or
    PipeWire. Here we provide the control-thread skeleton that coordinates
    playback, crossfades and limiter configuration.
    """

    def __init__(self, config: AudioConfig) -> None:
        self._config = config
        self._thread: Optional[Thread] = None
        self._stop_event = Event()
        self._on_track_end: Optional[Callable[[TrackPlayback], None]] = None

    def set_track_end_callback(self, callback: Callable[[TrackPlayback], None]) -> None:
        self._on_track_end = callback

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        logger.info(
            "Starting audio engine", extra={"samplerate": self._config.samplerate, "period": self._config.period_size}
        )
        self._stop_event.clear()
        self._thread = Thread(target=self._loop, name="audio-engine", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if not self._thread:
            return
        logger.info("Stopping audio engine")
        self._stop_event.set()
        self._thread.join(timeout=5)
        self._thread = None

    def play(self, track: TrackPlayback) -> None:
        logger.info("Scheduling track", extra={"path": str(track.path)})
        # Actual audio scheduling will be implemented in a future iteration.

    def _loop(self) -> None:
        logger.debug("Audio engine control loop started")
        while not self._stop_event.is_set():
            sleep(0.05)
        logger.debug("Audio engine control loop stopped")
