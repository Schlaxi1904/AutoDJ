"""Persistence helpers for dynamic runtime settings."""
from __future__ import annotations

from typing import Any, Dict, Optional

from ..database.models import Setting
from ..database.session import Database


class SettingsService:
    """Read and write structured settings stored in the database."""

    def __init__(self, database: Database) -> None:
        self._db = database

    def get(self, key: str, default: Optional[Any] = None) -> Any:
        """Return the stored value for *key* or ``default`` if unset."""

        with self._db.session() as session:
            record = session.get(Setting, key)
            if record is None:
                return default
            return record.value_json

    def get_dict(self, key: str, default: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Return a dictionary value, ensuring a copy is returned."""

        value = self.get(key, default or {})
        if not isinstance(value, dict):
            return dict(default or {})
        # Return a shallow copy so callers can mutate without side effects.
        return {**value}

    def set(self, key: str, value: Any) -> None:
        """Persist *value* for *key*, replacing any existing entry."""

        with self._db.session() as session:
            record = session.get(Setting, key)
            if record is None:
                session.add(Setting(key=key, value_json=value))
            else:
                record.value_json = value
                session.add(record)

    def update_dict(self, key: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Merge *updates* into an existing dictionary setting."""

        current = self.get_dict(key, {})
        current.update(updates)
        self.set(key, current)
        return current


__all__ = ["SettingsService"]

