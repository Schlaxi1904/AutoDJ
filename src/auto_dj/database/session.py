"""Database session helpers."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from ..config import DatabaseConfig
from .models import Base


class Database:
    """Connection manager for the Auto-DJ database."""

    def __init__(self, config: DatabaseConfig) -> None:
        self._engine = create_engine(config.dsn, echo=config.echo, future=True)
        if config.schema and config.dsn.startswith("postgresql"):
            schema = config.schema

            @event.listens_for(self._engine, "connect")
            def _set_search_path(dbapi_connection, connection_record):  # pragma: no cover - driver level
                cursor = dbapi_connection.cursor()
                try:
                    cursor.execute(f'SET search_path TO "{schema}"')
                finally:
                    cursor.close()
        self._session_factory = sessionmaker(self._engine, class_=Session, expire_on_commit=False)

    def create_all(self) -> None:
        Base.metadata.create_all(self._engine)

    @contextmanager
    def session(self) -> Iterator[Session]:
        session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
