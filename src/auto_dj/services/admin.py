"""Administrative account management services."""
from __future__ import annotations

from datetime import datetime
from typing import Iterable, Optional

from sqlalchemy import select

from ..config import AutoDjConfig
from ..database.models import AdminUser
from ..database.session import Database
from ..utils.security import hash_password, verify_password


class AdminService:
    """Business logic around admin accounts."""

    def __init__(self, db: Database, config: AutoDjConfig) -> None:
        self._db = db
        self._config = config

    def ensure_seed_accounts(self) -> None:
        """Ensure accounts from config exist with default passwords."""

        with self._db.session() as session:
            for account in self._config.admin_accounts:
                user = session.execute(
                    select(AdminUser).where(AdminUser.username == account.username)
                ).scalar_one_or_none()
                if user is None:
                    default_password = account.password_hash or "Admin123"
                    session.add(
                        AdminUser(
                            username=account.username,
                            password_hash=hash_password(default_password),
                        )
                    )

    def list_accounts(self) -> Iterable[AdminUser]:
        with self._db.session() as session:
            return list(session.execute(select(AdminUser).order_by(AdminUser.username)).scalars())

    def get_account(self, user_id: int) -> Optional[AdminUser]:
        with self._db.session() as session:
            return session.get(AdminUser, user_id)

    def authenticate(self, username: str, password: str) -> Optional[AdminUser]:
        with self._db.session() as session:
            user = session.execute(
                select(AdminUser).where(AdminUser.username == username)
            ).scalar_one_or_none()
            if user and verify_password(password, user.password_hash):
                user.last_login_at = datetime.utcnow()
                session.add(user)
                return user
            return None

    def change_password(self, user_id: int, new_password: str) -> None:
        if len(new_password) < 8:
            raise ValueError("Password must be at least 8 characters long")
        with self._db.session() as session:
            user = session.get(AdminUser, user_id)
            if not user:
                raise ValueError("Admin account not found")
            user.password_hash = hash_password(new_password)
            user.updated_at = datetime.utcnow()
            session.add(user)

    def reset_password(self, username: str, new_password: str) -> None:
        with self._db.session() as session:
            user = session.execute(
                select(AdminUser).where(AdminUser.username == username)
            ).scalar_one_or_none()
            if not user:
                raise ValueError("Admin account not found")
            if len(new_password) < 8:
                raise ValueError("Password must be at least 8 characters long")
            user.password_hash = hash_password(new_password)
            user.updated_at = datetime.utcnow()
            session.add(user)
