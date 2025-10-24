"""Helpers for enumerating and testing available audio output devices."""
from __future__ import annotations

import math
import re
import shutil
import subprocess
import tempfile
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional


@dataclass
class AudioDevice:
    identifier: str
    label: str
    kind: str


@dataclass
class AudioTestResult:
    success: bool
    message: str
    command: Optional[List[str]] = None
    returncode: Optional[int] = None


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
class AudioDeviceTester:
    """Play a short test tone on a given output device."""

    def __init__(self, scanner: AudioDeviceScanner | None = None) -> None:
        self._scanner = scanner or AudioDeviceScanner()

    def test(self, device_id: str) -> AudioTestResult:
        available = {device.identifier for device in self._scanner.scan()}
        if available and device_id not in available:
            return AudioTestResult(False, f"Unbekanntes Gerät: {device_id}")

        if shutil.which("speaker-test"):
            return self._run_command(
                [
                    "speaker-test",
                    "-D",
                    device_id,
                    "-c",
                    "2",
                    "-l",
                    "1",
                    "-t",
                    "sine",
                    "-f",
                    "440",
                ]
            )

        if shutil.which("aplay"):
            return self._run_aplay(device_id)

        return AudioTestResult(
            False,
            "Kein Testwerkzeug gefunden. Installiere 'speaker-test' oder 'aplay'.",
        )

    def _run_command(self, command: List[str]) -> AudioTestResult:
        try:
            completed = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=6,
                text=True,
            )
        except subprocess.TimeoutExpired:
            return AudioTestResult(False, "Audiotest überschritt das Zeitlimit", command=command)
        except FileNotFoundError:
            return AudioTestResult(False, "Audiotest-Tool nicht gefunden", command=command)
        except subprocess.SubprocessError as exc:
            return AudioTestResult(False, f"Audiotest fehlgeschlagen: {exc}", command=command)

        if completed.returncode == 0:
            return AudioTestResult(True, "Audiotest erfolgreich gestartet", command=command)

        message = completed.stderr.strip() or completed.stdout.strip() or "Unbekannter Fehler"
        return AudioTestResult(
            False,
            f"Audiotest fehlgeschlagen: {message}",
            command=command,
            returncode=completed.returncode,
        )

    def _run_aplay(self, device_id: str) -> AudioTestResult:
        with tempfile.NamedTemporaryFile("wb", suffix=".wav", delete=False) as handle:
            tone_path = Path(handle.name)
        try:
            self._write_test_tone(tone_path)
            return self._run_command(["aplay", "-q", "-D", device_id, str(tone_path)])
        finally:
            try:
                tone_path.unlink(missing_ok=True)
            except OSError:
                pass

    @staticmethod
    def _write_test_tone(path: Path, duration: float = 0.5, frequency: float = 440.0) -> None:
        samplerate = 48_000
        amplitude = 0.4
        total_frames = int(duration * samplerate)

        with wave.open(str(path), "wb") as wav_file:
            wav_file.setnchannels(2)
            wav_file.setsampwidth(2)
            wav_file.setframerate(samplerate)

            for frame in range(total_frames):
                value = amplitude * math.sin(2 * math.pi * frequency * (frame / samplerate))
                sample = int(value * 32767)
                wav_file.writeframes(sample.to_bytes(2, "little", signed=True) * 2)


__all__ = ["AudioDevice", "AudioDeviceScanner", "AudioDeviceTester", "AudioTestResult"]

