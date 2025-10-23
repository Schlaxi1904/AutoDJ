"""Helpers for enumerating available audio output devices."""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from typing import Dict, Iterable, List


@dataclass
class AudioDevice:
    identifier: str
    label: str
    kind: str


class AudioDeviceScanner:
    """Enumerate ALSA, PulseAudio and Bluetooth outputs on the host."""

    _APLAY_PATTERN = re.compile(r"^(?P<id>[\w:-]+)\\s*(?P<label>.*)$")
    _APLAY_CARD_PATTERN = re.compile(
        r"^card\s+(?P<card>\d+):\s+(?P<card_name>[^\[]+)\[(?P<card_desc>[^\]]+)\],\s*"
        r"device\s+(?P<device>\d+):\s+(?P<device_name>[^\[]+)\[(?P<device_desc>[^\]]+)\]",
        re.IGNORECASE,
    )

    def _scan_aplay(self) -> Iterable[AudioDevice]:
        try:
            result = subprocess.run(
                ["aplay", "-L"],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=5,
            )
        except FileNotFoundError:
            return []
        except subprocess.SubprocessError:
            return []

        devices: List[AudioDevice] = []
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            match = self._APLAY_PATTERN.match(line)
            if not match:
                continue
            identifier = match.group("id")
            label = match.group("label") or identifier
            kind = "alsa"
            if "hdmi" in identifier.lower():
                kind = "hdmi"
            elif identifier.lower().startswith("bluealsa"):
                kind = "bluetooth"
            devices.append(AudioDevice(identifier=identifier, label=label.strip(), kind=kind))
        return devices

    def _scan_alsa_cards(self) -> Iterable[AudioDevice]:
        try:
            result = subprocess.run(
                ["aplay", "-l"],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=5,
            )
        except FileNotFoundError:
            return []
        except subprocess.SubprocessError:
            return []

        devices: List[AudioDevice] = []
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            match = self._APLAY_CARD_PATTERN.match(line)
            if not match:
                continue
            card = match.group("card")
            device = match.group("device")
            device_desc = match.group("device_desc").strip()
            card_desc = match.group("card_desc").strip()
            friendly_name = device_desc or card_desc or match.group("card_name").strip()
            identifier = f"hw:{card},{device}"
            label = f"{friendly_name} (hw:{card},{device})"
            devices.append(AudioDevice(identifier=identifier, label=label, kind="alsa"))
        return devices

    def _scan_pulseaudio(self) -> Iterable[AudioDevice]:
        try:
            result = subprocess.run(
                ["pactl", "list", "short", "sinks"],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=5,
            )
        except FileNotFoundError:
            return []
        except subprocess.SubprocessError:
            return []

        devices: List[AudioDevice] = []
        for line in result.stdout.splitlines():
            parts = line.strip().split("\t")
            if len(parts) < 2:
                continue
            identifier = parts[1]
            description = parts[1]
            if len(parts) >= 3:
                description = parts[1] if not parts[2] else parts[2]
            devices.append(
                AudioDevice(identifier=identifier, label=description.strip(), kind="pulse")
            )
        return devices

    def scan(self) -> List[AudioDevice]:
        """Return a deduplicated list of audio outputs."""

        devices: Dict[str, AudioDevice] = {}
        for provider in (
            self._scan_alsa_cards(),
            self._scan_aplay(),
            self._scan_pulseaudio(),
        ):
            for device in provider:
                devices[device.identifier] = device

        if not devices:
            fallback = [
                AudioDevice("hw:0", "Onboard Audio (hw:0)", "alsa"),
                AudioDevice("hw:1", "USB Audio Interface (hw:1)", "alsa"),
                AudioDevice("bluez_sink", "Bluetooth Speaker", "bluetooth"),
            ]
            return fallback

        return sorted(devices.values(), key=lambda dev: dev.label.lower())


__all__ = ["AudioDevice", "AudioDeviceScanner"]

