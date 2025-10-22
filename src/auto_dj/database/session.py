"""Database session helpers."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from ..config import DatabaseConfig
from .models import Base


class Database:
    """Connection manager for the Auto-DJ database."""

    def __init__(self, config: DatabaseConfig) -> None:
        self._engine = create_engine(config.dsn, echo=config.echo, future=True)
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
