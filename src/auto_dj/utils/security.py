"""Security helpers for password hashing and verification."""
from __future__ import annotations

from passlib.context import CryptContext


_pwd_context = CryptContext(
    schemes=["bcrypt_sha256", "bcrypt"],
    default="bcrypt_sha256",
    deprecated="auto",
)


def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt."""

    if not password:
        raise ValueError("Password must not be empty")
    return _pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against a stored hash."""

    if not password_hash:
        return False
    return _pwd_context.verify(password, password_hash)
