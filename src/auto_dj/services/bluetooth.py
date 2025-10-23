"""Utilities for managing Bluetooth audio devices via bluetoothctl."""
from __future__ import annotations

import re
import subprocess
import getpass
try:  # pragma: no cover - Windows fallback
    import grp  # type: ignore
except ImportError:  # pragma: no cover - Windows fallback
    grp = None
import logging
import os
from dataclasses import dataclass
from typing import Iterable, List


@dataclass
class BluetoothDevice:
    address: str
    name: str
    paired: bool
    trusted: bool
    connected: bool


class BluetoothError(RuntimeError):
    """Raised when a Bluetooth command fails."""


class BluetoothManager:
    """Wrapper around ``bluetoothctl`` for pairing and connecting devices."""

    def __init__(self, timeout: int = 12) -> None:
        self._timeout = timeout
        self._logger = logging.getLogger(__name__)

    def _ensure_prerequisites(self) -> None:
        required_groups = {"bluetooth", "audio", "netdev"}
        username = getpass.getuser()
        missing: List[str] = []
        if grp is not None:
            try:
                group_names = {grp.getgrgid(gid).gr_name for gid in os.getgroups()}
            except Exception:  # pragma: no cover - platform specific fallback
                group_names = set()
            missing = [group for group in required_groups if group not in group_names]
        if missing and os.geteuid() != 0:
            raise BluetoothError(
                "Fehlende Berechtigungen: Benutzer "
                f"{username} benötigt Zugriff auf {', '.join(sorted(missing))}."
            )

        os.environ.setdefault(
            "DBUS_SYSTEM_BUS_ADDRESS", "unix:path=/var/run/dbus/system_bus_socket"
        )

        try:
            subprocess.run(
                ["rfkill", "unblock", "bluetooth"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
        except FileNotFoundError:
            self._logger.debug("rfkill nicht verfügbar – überspringe Freigabe")

        try:
            result = subprocess.run(
                ["bluetoothctl", "power", "on"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=self._timeout,
                check=False,
            )
            if result.returncode != 0:
                self._logger.warning(
                    "bluetoothctl power on fehlgeschlagen: %s",
                    result.stderr.strip() or result.stdout.strip(),
                )
        except FileNotFoundError:
            raise BluetoothError("bluetoothctl nicht gefunden") from None

    def _execute(
        self, args: Iterable[str], *, input_data: str | None = None
    ) -> subprocess.CompletedProcess:
        self._ensure_prerequisites()
        command = ["bluetoothctl", *args]
        try:
            result = subprocess.run(
                command,
                input=input_data,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=self._timeout,
                check=False,
            )
        except FileNotFoundError as exc:  # pragma: no cover - runtime dependency
            raise BluetoothError("bluetoothctl nicht gefunden") from exc
        except subprocess.TimeoutExpired as exc:
            raise BluetoothError("Bluetooth-Befehl hat zu lange gedauert") from exc
        except subprocess.SubprocessError as exc:
            raise BluetoothError(f"Bluetooth-Befehl fehlgeschlagen: {exc}") from exc

        output = f"{result.stdout}\n{result.stderr}".lower()
        if "no default controller available" in output:
            raise BluetoothError("Kein Bluetooth-Adapter verfügbar")
        if "not available" in output and "device" in output:
            raise BluetoothError("Bluetooth-Gerät nicht verfügbar")

        return result

    def _execute_script(self, commands: Iterable[str]) -> subprocess.CompletedProcess:
        script = "\n".join(list(commands) + ["quit"])
        return self._execute([], input_data=script)

    @staticmethod
    def _has_error(result: subprocess.CompletedProcess) -> bool:
        text = f"{result.stdout}\n{result.stderr}".lower()
        return any(keyword in text for keyword in ("failed", "error", "not available"))

    @staticmethod
    def _parse_devices(output: str) -> List[tuple[str, str]]:
        devices: List[tuple[str, str]] = []
        for line in output.splitlines():
            line = line.strip()
            if not line or not line.startswith("Device "):
                continue
            parts = line.split(" ", 2)
            if len(parts) < 3:
                continue
            address = parts[1].strip()
            name = parts[2].strip()
            devices.append((address, name))
        return devices

    @staticmethod
    def _parse_info(output: str, address: str, fallback_name: str) -> BluetoothDevice:
        name = fallback_name
        paired = False
        trusted = False
        connected = False
        for line in output.splitlines():
            text = line.strip()
            if text.startswith("Name: "):
                name = text.split(":", 1)[1].strip() or name
            elif text.startswith("Alias: ") and not name:
                name = text.split(":", 1)[1].strip()
            elif text.startswith("Connected: "):
                connected = text.split(":", 1)[1].strip().lower() == "yes"
            elif text.startswith("Paired: "):
                paired = text.split(":", 1)[1].strip().lower() == "yes"
            elif text.startswith("Trusted: "):
                trusted = text.split(":", 1)[1].strip().lower() == "yes"
        if not name:
            name = fallback_name or "Unbenanntes Gerät"
        return BluetoothDevice(
            address=address,
            name=name,
            paired=paired,
            trusted=trusted,
            connected=connected,
        )

    def _device_info(self, address: str, fallback_name: str = "") -> BluetoothDevice:
        result = self._execute(["info", address])
        if result.returncode != 0:
            raise BluetoothError(
                result.stderr.strip() or f"Informationen für {address} nicht verfügbar"
            )
        return self._parse_info(result.stdout, address, fallback_name or address)

    def list_devices(self) -> List[BluetoothDevice]:
        result = self._execute(["devices"])
        if result.returncode != 0:
            raise BluetoothError(result.stderr.strip() or "Bluetooth-Geräte konnten nicht geladen werden")
        discovered = self._parse_devices(result.stdout)
        devices: List[BluetoothDevice] = []
        for address, name in discovered:
            try:
                devices.append(self._device_info(address, name))
            except BluetoothError:
                devices.append(
                    BluetoothDevice(
                        address=address,
                        name=name or address,
                        paired=False,
                        trusted=False,
                        connected=False,
                    )
                )
        return devices

    def scan(self, duration: int = 6) -> List[BluetoothDevice]:
        args = ["--timeout", str(max(3, duration)), "scan", "on"]
        result = self._execute(args)
        if result.returncode != 0:
            raise BluetoothError(
                result.stderr.strip() or result.stdout.strip() or "Scan fehlgeschlagen"
            )
        return self.list_devices()

    def pair_device(self, address: str) -> BluetoothDevice:
        cleaned = address.strip()
        if not re.fullmatch(r"([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}", cleaned):
            raise BluetoothError("Ungültige Bluetooth-Adresse")
        normalized = cleaned.upper()
        # Ensure the controller is powered and the device is visible.
        self.scan()
        result = self._execute_script(
            [
                "power on",
                "agent NoInputNoOutput",
                "default-agent",
                f"pair {normalized}",
                f"trust {normalized}",
                f"connect {normalized}",
            ]
        )
        if result.returncode != 0 or self._has_error(result):
            raise BluetoothError(
                result.stderr.strip() or result.stdout.strip() or "Koppeln fehlgeschlagen"
            )
        return self._device_info(normalized)

    def connect_device(self, address: str) -> BluetoothDevice:
        normalized = address.strip().upper()
        result = self._execute(["connect", normalized])
        if result.returncode != 0 or self._has_error(result):
            raise BluetoothError(
                result.stderr.strip() or result.stdout.strip() or "Verbindung fehlgeschlagen"
            )
        return self._device_info(normalized)

    def disconnect_device(self, address: str) -> BluetoothDevice:
        normalized = address.strip().upper()
        result = self._execute(["disconnect", normalized])
        if result.returncode != 0 or self._has_error(result):
            raise BluetoothError(
                result.stderr.strip() or result.stdout.strip() or "Trennen fehlgeschlagen"
            )
        try:
            return self._device_info(normalized)
        except BluetoothError:
            return BluetoothDevice(
                address=normalized,
                name=normalized,
                paired=False,
                trusted=False,
                connected=False,
            )


__all__ = ["BluetoothDevice", "BluetoothError", "BluetoothManager"]
