from __future__ import annotations

import base64
import os

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    if len(password) < 10:
        raise ValueError("비밀번호는 10자 이상이어야 합니다.")
    return _hasher.hash(password)


def verify_password(stored_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(stored_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def encrypt_text(value: str) -> bytes:
    encoded = os.getenv("DATA_ENCRYPTION_KEY", "")
    key = base64.urlsafe_b64decode(encoded.encode("ascii"))
    if len(key) != 32:
        raise RuntimeError("DATA_ENCRYPTION_KEY must decode to 32 bytes")
    nonce = os.urandom(12)
    return nonce + AESGCM(key).encrypt(nonce, value.encode("utf-8"), b"ge-dashboard")
