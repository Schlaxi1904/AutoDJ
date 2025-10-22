"""OSC communication scaffolding."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict

from pythonosc.udp_client import SimpleUDPClient

from ..config import OscConfig

logger = logging.getLogger(__name__)


@dataclass
class OscState:
    beat_phase: float = 0.0
    bar_index: int = 0
    energy: float = 0.0
    drop_active: bool = False
    break_active: bool = False


class OscService:
    def __init__(self, config: OscConfig) -> None:
        self._client = SimpleUDPClient(config.target_host, config.target_port)
        self._config = config

    def send_state(self, state: OscState) -> None:
        logger.debug("Sending OSC state", extra={"beat": state.beat_phase, "bar": state.bar_index})
        self._client.send_message("/beat", state.beat_phase)
        self._client.send_message("/bar", state.bar_index)
        self._client.send_message("/energy", state.energy)
        self._client.send_message("/mood/drop", int(state.drop_active))
        self._client.send_message("/mood/break", int(state.break_active))

    def trigger_genre_scene(self, genre_bank: int, slot: int, start: bool) -> None:
        if genre_bank not in {1, 2, 3, 4}:
            raise ValueError("Invalid genre bank")
        path = f"/cue/{genre_bank}/{slot}"
        logger.info("Triggering scene", extra={"path": path, "start": start})
        self._client.send_message(path, 1 if start else 0)

    def trigger_superscene(self, scene: int, start: bool) -> None:
        path = f"/cue/99/{scene}"
        logger.info("Triggering superscene", extra={"path": path, "start": start})
        self._client.send_message(path, 1 if start else 0)
