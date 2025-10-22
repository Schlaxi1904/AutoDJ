"""Security helpers for password hashing and verification."""
from __future__ import annotations

import hashlib
import logging
from typing import Final

import bcrypt
from passlib.context import CryptContext


LOGGER = logging.getLogger(__name__)

_BCRYPT_PREFIX: Final[str] = "$bcrypt-sha256$"

_pwd_context = CryptContext(
    schemes=["bcrypt_sha256"],
    default="bcrypt_sha256",
    deprecated="auto",
)


def _verify_bcrypt_sha256(password: str, password_hash: str) -> bool:
    """Manually verify bcrypt_sha256 hashes without passlib bug checks."""

    if not password_hash.startswith(_BCRYPT_PREFIX):
        return False

    digest = hashlib.sha256(password.encode("utf-8")).digest()
    stored = password_hash[len(_BCRYPT_PREFIX) :].encode("utf-8")
    try:
        return bcrypt.checkpw(digest, stored)
    except ValueError:
        # bcrypt may still raise on malformed hashes – treat as mismatch.
        return False


def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt_sha256."""

    if not password:
        raise ValueError("Password must not be empty")
    return _pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against a stored hash.

    Passlib's bcrypt backend raises when probing for long-password bugs on
    certain builds (notably on Raspberry Pi distributions shipping bcrypt
    >=4). We optimistically use the context, but gracefully fall back to a
    manual bcrypt_sha256 verifier so the login flow never crashes.
    """

    if not password_hash:
        return False

    try:
        return _pwd_context.verify(password, password_hash)
    except ValueError as exc:
        LOGGER.warning("bcrypt verification failed – falling back", exc_info=exc)
        return _verify_bcrypt_sha256(password, password_hash)
