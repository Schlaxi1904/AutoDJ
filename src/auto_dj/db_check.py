"""Database readiness checks executed at service start."""
from __future__ import annotations

import logging
from pathlib import Path

from alembic import command
from alembic.config import Config as AlembicConfig
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from .config import AutoDjConfig, load_config
from .database.models import Base

LOGGER = logging.getLogger(__name__)

_REQUIRED_TABLES = tuple(Base.metadata.tables.keys())


def _redact_dsn(dsn: str) -> str:
    if "@" not in dsn:
        return dsn
    prefix, suffix = dsn.split("@", 1)
    if ":" in prefix:
        username = prefix.split(":", 1)[0]
    else:
        username = prefix
    return f"{username}:***@{suffix}"


def _build_engine(config: AutoDjConfig) -> Engine:
    return create_engine(config.database.dsn, future=True)


def _ensure_schema(connection, schema: str | None) -> None:
    if not schema:
        return
    try:
        connection.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
        connection.execute(text(f'SET search_path TO "{schema}"'))
    except SQLAlchemyError as exc:
        raise RuntimeError(
            f"Schema '{schema}' konnte nicht vorbereitet werden: {exc}") from exc


def _run_alembic_upgrade(config: AutoDjConfig) -> None:
    script_location = Path(__file__).resolve().parent / "migrations"
    alembic_cfg = AlembicConfig()
    alembic_cfg.set_main_option("script_location", str(script_location))
    alembic_cfg.set_main_option("sqlalchemy.url", config.database.dsn)
    if config.database.schema:
        alembic_cfg.set_main_option(
            "version_table_schema", config.database.schema
        )
    try:
        command.upgrade(alembic_cfg, "head")
    except Exception as exc:  # pragma: no cover - delegated to tests
        raise RuntimeError(
            "alembic upgrade head fehlgeschlagen. Bitte Logs prüfen."
        ) from exc


def _create_missing_tables(engine: Engine) -> list[str]:
    inspector = inspect(engine)
    missing = [table for table in _REQUIRED_TABLES if not inspector.has_table(table)]
    if not missing:
        return []
    Base.metadata.create_all(engine)
    inspector = inspect(engine)
    remaining = [table for table in missing if not inspector.has_table(table)]
    return remaining


def ensure_database_ready(config: AutoDjConfig) -> None:
    """Validate the database connection and ensure required tables exist."""

    dsn = config.database.dsn
    LOGGER.info("Prüfe Datenbankverbindung", extra={"dsn": _redact_dsn(dsn)})
    engine = _build_engine(config)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            _ensure_schema(connection, config.database.schema)
    except OperationalError as exc:
        raise RuntimeError(
            "Verbindung zur Datenbank fehlgeschlagen. Bitte Zugangsdaten prüfen."
        ) from exc

    LOGGER.info("Führe alembic upgrade head aus")
    _run_alembic_upgrade(config)

    remaining = _create_missing_tables(engine)
    if remaining:
        raise RuntimeError(
            "Nicht alle Tabellen konnten erstellt werden: " + ", ".join(remaining)
        )
    LOGGER.info("Datenbankstruktur vollständig initialisiert")


__all__ = ["ensure_database_ready"]


def main() -> int:
    """CLI entry point for database validation."""

    config = load_config()
    ensure_database_ready(config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
