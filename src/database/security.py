"""Password hashing and authenticated encryption for authentication data."""

from __future__ import annotations

import base64
import os

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


_PASSWORD_HASHER = PasswordHasher()
_DUMMY_HASH = _PASSWORD_HASHER.hash("dummy-password-used-only-to-equalize-login-work")


def hash_password(password: str) -> str:
    if len(password) < 12:
        raise ValueError("Password must contain at least 12 characters")
    return _PASSWORD_HASHER.hash(password)


def verify_password(stored_hash: str | None, password: str) -> bool:
    candidate = stored_hash or _DUMMY_HASH
    try:
        valid = _PASSWORD_HASHER.verify(candidate, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False
    return bool(valid and stored_hash)


def needs_rehash(stored_hash: str) -> bool:
    return _PASSWORD_HASHER.check_needs_rehash(stored_hash)


def _encryption_key() -> bytes:
    encoded = os.getenv("DATA_ENCRYPTION_KEY", "")
    if not encoded:
        raise RuntimeError("DATA_ENCRYPTION_KEY is required when authentication is enabled")
    try:
        key = base64.urlsafe_b64decode(encoded.encode("ascii"))
    except Exception as exc:
        raise RuntimeError("DATA_ENCRYPTION_KEY must be URL-safe base64") from exc
    if len(key) != 32:
        raise RuntimeError("DATA_ENCRYPTION_KEY must decode to 32 bytes")
    return key


def encrypt_text(value: str, purpose: str) -> bytes:
    nonce = os.urandom(12)
    ciphertext = AESGCM(_encryption_key()).encrypt(
        nonce,
        value.encode("utf-8"),
        purpose.encode("utf-8"),
    )
    return nonce + ciphertext


def decrypt_text(value: bytes, purpose: str) -> str:
    nonce, ciphertext = value[:12], value[12:]
    plaintext = AESGCM(_encryption_key()).decrypt(
        nonce,
        ciphertext,
        purpose.encode("utf-8"),
    )
    return plaintext.decode("utf-8")
