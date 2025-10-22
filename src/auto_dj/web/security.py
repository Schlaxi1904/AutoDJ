"""Session utilities for the admin dashboard."""
from __future__ import annotations

from datetime import timedelta
from typing import Optional

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from ..config import AutoDjConfig

_SESSION_COOKIE = "auto_dj_admin_session"
_SESSION_MAX_AGE = int(timedelta(hours=12).total_seconds())


class SessionManager:
    def __init__(self, config: AutoDjConfig) -> None:
        self._config = config
        self._serializer = URLSafeTimedSerializer(
            secret_key=config.web_security.session_secret,
            salt="auto-dj-admin",
        )

    @property
    def cookie_name(self) -> str:
        return _SESSION_COOKIE

    @property
    def max_age(self) -> int:
        return _SESSION_MAX_AGE

    def create(self, admin_id: int) -> str:
        return self._serializer.dumps({"admin_id": admin_id})

    def verify(self, token: str) -> Optional[int]:
        try:
            data = self._serializer.loads(token, max_age=_SESSION_MAX_AGE)
        except (BadSignature, SignatureExpired):
            return None
        admin_id = data.get("admin_id")
        if isinstance(admin_id, int):
            return admin_id
        return None


__all__ = ["SessionManager"]
