"""SQLAlchemy models representing the Auto-DJ persistence layer."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    metadata = MetaData()


class Track(Base):
    __tablename__ = "tracks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    path: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    artist: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    lufs_i: Mapped[float] = mapped_column(Float, nullable=False)
    true_peak_db: Mapped[float] = mapped_column(Float, nullable=False)
    bpm: Mapped[float] = mapped_column(Float, nullable=False)
    key_camelot: Mapped[str] = mapped_column(String(4), nullable=False)
    genre: Mapped[str] = mapped_column(String(64), nullable=False)
    energy_avg: Mapped[float] = mapped_column(Float, nullable=False)
    cover_path: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    added_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    flags: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict)

    features: Mapped["TrackFeatures"] = relationship(back_populates="track", uselist=False)


class TrackFeatures(Base):
    __tablename__ = "track_features"

    track_id: Mapped[int] = mapped_column(ForeignKey("tracks.id"), primary_key=True)
    beatgrid_json: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    energy_curve_json: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    structure_json: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)

    track: Mapped[Track] = relationship(back_populates="features")


class QueueEntry(Base):
    __tablename__ = "queue"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    track_id: Mapped[int] = mapped_column(ForeignKey("tracks.id"), nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    guest_session: Mapped[Optional[str]] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)

    track: Mapped[Track] = relationship()


class Request(Base):
    __tablename__ = "requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    track_id: Mapped[int] = mapped_column(ForeignKey("tracks.id"), nullable=False)
    guest_session: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)

    track: Mapped[Track] = relationship()


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value_json: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)


class BlacklistEntry(Base):
    __tablename__ = "blacklist"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    pattern: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class AuditLog(Base):
    __tablename__ = "audit"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    svc: Mapped[str] = mapped_column(String(32), nullable=False)
    event: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_json: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)


__all__ = [
    "Base",
    "Track",
    "TrackFeatures",
    "QueueEntry",
    "Request",
    "Setting",
    "BlacklistEntry",
    "AuditLog",
]
