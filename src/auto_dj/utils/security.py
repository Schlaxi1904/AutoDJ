"""Security helpers for password hashing and verification."""
from __future__ import annotations

import hashlib
import logging
from typing import Final, Optional

import bcrypt


LOGGER = logging.getLogger(__name__)

_BCRYPT_PREFIX: Final[str] = "$bcrypt-sha256$"


def _digest_password(password: str) -> bytes:
    """Return the SHA-256 digest used by the bcrypt_sha256 scheme."""

    return hashlib.sha256(password.encode("utf-8")).digest()


def _normalise_bcrypt_hash(password_hash: str) -> Optional[bytes]:
    """Convert stored bcrypt_sha256 strings into a raw bcrypt hash.

    passlib stores bcrypt_sha256 hashes using the format

    ``$bcrypt-sha256$IDENT,ROUNDS$<salt+hash>``

    while our own hashes are saved as ``$bcrypt-sha256$$IDENT$ROUNDS$...``.
    This helper accepts both encodings and returns a byte string that can be
    directly passed to :func:`bcrypt.checkpw`.
    """

    if not password_hash or not password_hash.startswith(_BCRYPT_PREFIX):
        return None

    remainder = password_hash[len(_BCRYPT_PREFIX) :]
    if remainder.startswith("$"):
        normalised = remainder
    else:
        try:
            ident_rounds, payload = remainder.split("$", 1)
            ident, rounds = ident_rounds.split(",", 1)
        except ValueError:
            LOGGER.warning("Malformed bcrypt_sha256 hash encountered")
            return None
        normalised = f"${ident}${rounds}${payload}"
    return normalised.encode("utf-8")


def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt_sha256 semantics."""

    if not password:
        raise ValueError("Password must not be empty")

    digest = _digest_password(password)
    hashed = bcrypt.hashpw(digest, bcrypt.gensalt())
    return f"{_BCRYPT_PREFIX}{hashed.decode('utf-8')}"


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against a stored hash without passlib dependencies."""

    normalised = _normalise_bcrypt_hash(password_hash)
    if not normalised:
        return False

    digest = _digest_password(password)
    try:
        return bcrypt.checkpw(digest, normalised)
    except (ValueError, RuntimeError) as exc:  # pragma: no cover - defensive
        LOGGER.warning("bcrypt verification raised", exc_info=exc)
        return False
