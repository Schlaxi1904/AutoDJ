"""Configuration models and defaults for the Auto-DJ system."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass(frozen=True)
class PathsConfig:
    """Filesystem layout for runtime assets.

    The defaults mirror the deployment layout from the implementation specification.
    """

    music_root: Path = Path("/media/music")
    covers_root: Path = Path("/var/lib/auto-dj/covers")
    cache_root: Path = Path("/var/lib/auto-dj")
    config_root: Path = Path("/etc/auto-dj")
    runtime_log_root: Path = Path("/run/auto-dj/logs")
    persistent_log_root: Path = Path("/var/log/auto-dj")


@dataclass(frozen=True)
class DatabaseConfig:
    """Connection settings for PostgreSQL."""

    dsn: str = "postgresql+psycopg://auto_dj:change-me@localhost:5432/auto_dj"
    echo: bool = False


@dataclass(frozen=True)
class AudioConfig:
    """Realtime audio processing parameters."""

    samplerate: int = 48_000
    period_size: int = 256
    periods: int = 3
    fallback_period_size: int = 512
    limiter_ceiling_db: float = -1.0
    limiter_lookahead_ms: float = 6.0
    time_stretch_max_percent: float = 6.0


@dataclass(frozen=True)
class OscConfig:
    """Outgoing OSC target configuration."""

    target_host: str = "192.168.1.100"
    target_port: int = 4040
    inbound_port: int = 4041
    rate_limit_hz: float = 120.0


@dataclass(frozen=True)
class BrainWeights:
    """Weights for DJ planning decisions."""

    key: float = 1.0
    bpm: float = 1.0
    energy: float = 1.0
    genre: float = 0.7
    recency: float = 0.5
    request: float = 1.2


@dataclass(frozen=True)
class QueuePolicy:
    """Queue length and spacing constraints."""

    max_length: int = 20
    preferred_spacing: int = 1


@dataclass(frozen=True)
class WebSecurityConfig:
    """HTTP security toggles."""

    public_enabled: bool = False
    ssl_enabled: bool = False
    session_secret: str = "auto-dj-development-secret"


@dataclass(frozen=True)
class GuestRateLimit:
    requests_per_minute: int = 6
    captcha_threshold: int = 6


@dataclass(frozen=True)
class AdminAccount:
    username: str = "admin"
    password_hash: Optional[str] = None


@dataclass(frozen=True)
class AutoDjConfig:
    paths: PathsConfig = field(default_factory=PathsConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    audio: AudioConfig = field(default_factory=AudioConfig)
    osc: OscConfig = field(default_factory=OscConfig)
    brain_weights: BrainWeights = field(default_factory=BrainWeights)
    queue_policy: QueuePolicy = field(default_factory=QueuePolicy)
    web_security: WebSecurityConfig = field(default_factory=WebSecurityConfig)
    guest_rate_limit: GuestRateLimit = field(default_factory=GuestRateLimit)
    admin_accounts: List[AdminAccount] = field(default_factory=lambda: [AdminAccount()])
    allowed_inbound_osc: List[str] = field(
        default_factory=lambda: [
            "/genre/override",
            "/superscene/enable",
            "/superscene/stop",
            "/bar/reset",
            "/master/dimmer",
        ]
    )


DEFAULT_CONFIG = AutoDjConfig()
"""Shared default configuration instance."""
