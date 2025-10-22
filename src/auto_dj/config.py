"""Configuration models and defaults for the Auto-DJ system."""
from __future__ import annotations

import os
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

    dsn: str = "postgresql+psycopg://auto-dj:auto-dj@localhost:5432/auto_dj"
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


def _env_path(name: str, default: Path) -> Path:
    value = os.environ.get(name)
    if value:
        return Path(value)
    return default


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def _prefer_writable_path(default: Path, fallback_suffix: str) -> Path:
    """Return a writable path, falling back to the user's home if required."""

    # If the caller explicitly overrides the directory through an environment
    # variable we assume they know what they are doing and do not attempt any
    # fallbacks.  The caller will pass the override through `_env_path` prior to
    # invoking this helper, so only keep the default-detection behaviour here.
    candidate = default
    # Determine the closest existing ancestor directory and test writability.
    probe = candidate
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent

    if probe.exists() and os.access(probe, os.W_OK):
        return candidate

    fallback_base = Path.home() / ".auto-dj" / "logs"
    if fallback_suffix:
        return fallback_base / fallback_suffix
    return fallback_base


def load_config() -> AutoDjConfig:
    """Load the Auto-DJ configuration, applying environment overrides."""

    default_paths = PathsConfig()
    runtime_log_root = _env_path(
        "AUTO_DJ_RUNTIME_LOG_ROOT", default_paths.runtime_log_root
    )
    if runtime_log_root == default_paths.runtime_log_root:
        runtime_log_root = _prefer_writable_path(runtime_log_root, "runtime")

    persistent_log_root = _env_path(
        "AUTO_DJ_PERSISTENT_LOG_ROOT", default_paths.persistent_log_root
    )
    if persistent_log_root == default_paths.persistent_log_root:
        persistent_log_root = _prefer_writable_path(persistent_log_root, "persistent")

    paths = PathsConfig(
        music_root=_env_path("AUTO_DJ_MUSIC_ROOT", default_paths.music_root),
        covers_root=_env_path("AUTO_DJ_COVERS_ROOT", default_paths.covers_root),
        cache_root=_env_path("AUTO_DJ_CACHE_ROOT", default_paths.cache_root),
        config_root=_env_path("AUTO_DJ_CONFIG_ROOT", default_paths.config_root),
        runtime_log_root=runtime_log_root,
        persistent_log_root=persistent_log_root,
    )

    database_dsn = os.environ.get("AUTO_DJ_DATABASE_DSN")
    if not database_dsn:
        user = os.environ.get("AUTO_DJ_DB_USER", "auto-dj")
        password = os.environ.get("AUTO_DJ_DB_PASSWORD", "auto-dj")
        host = os.environ.get("AUTO_DJ_DB_HOST", "localhost")
        port = os.environ.get("AUTO_DJ_DB_PORT", "5432")
        name = os.environ.get("AUTO_DJ_DB_NAME", "auto_dj")
        database_dsn = (
            f"postgresql+psycopg://{user}:{password}@{host}:{port}/{name}"
        )

    database = DatabaseConfig(
        dsn=database_dsn,
        echo=_env_bool("AUTO_DJ_DB_ECHO", False),
    )

    return AutoDjConfig(paths=paths, database=database)


DEFAULT_CONFIG = load_config()
"""Shared default configuration instance with environment overrides applied."""
