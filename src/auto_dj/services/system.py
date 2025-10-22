"""Runtime system monitoring helpers for the admin dashboard."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

try:  # pragma: no cover - optional dependency runtime check
    import psutil  # type: ignore
except Exception:  # pragma: no cover - psutil not available on all platforms
    psutil = None  # type: ignore

from ..config import AutoDjConfig
from ..services.settings import SettingsService


@dataclass
class SystemSnapshot:
    cpu_percent: Optional[float]
    memory_percent: Optional[float]
    temperature_c: Optional[float]
    xrun_count: int
    osc_connected: bool


class SystemMonitor:
    """Collects lightweight host metrics and persisted runtime flags."""

    XRUN_KEY = "audio.xruns"
    OSC_STATUS_KEY = "osc.status"

    def __init__(self, config: AutoDjConfig, settings: SettingsService) -> None:
        self._config = config
        self._settings = settings

    def snapshot(self) -> SystemSnapshot:
        """Return a snapshot of host metrics and stored statuses."""

        cpu_percent: Optional[float] = None
        memory_percent: Optional[float] = None
        temperature_c: Optional[float] = None

        if psutil is not None:
            try:
                cpu_percent = psutil.cpu_percent(interval=0.0)
            except Exception:  # pragma: no cover - psutil edge cases
                cpu_percent = None
            try:
                memory_percent = psutil.virtual_memory().percent
            except Exception:  # pragma: no cover - psutil edge cases
                memory_percent = None
            try:
                temps = psutil.sensors_temperatures()
            except Exception:  # pragma: no cover - psutil edge cases
                temps = {}
            if temps:
                # Prefer Raspberry Pi thermal sensor label if present.
                for key in ("cpu-thermal", "soc_thermal", "coretemp"):
                    readings = temps.get(key)
                    if readings:
                        temperature_c = readings[0].current
                        break
                if temperature_c is None:
                    first_sensor = next(iter(temps.values()))
                    if first_sensor:
                        temperature_c = first_sensor[0].current

        xrun_count = int(self._settings.get(self.XRUN_KEY, 0) or 0)
        osc_status = self._settings.get_dict(self.OSC_STATUS_KEY, {"connected": False})
        osc_connected = bool(osc_status.get("connected", False))

        return SystemSnapshot(
            cpu_percent=cpu_percent,
            memory_percent=memory_percent,
            temperature_c=temperature_c,
            xrun_count=xrun_count,
            osc_connected=osc_connected,
        )


__all__ = ["SystemMonitor", "SystemSnapshot"]

