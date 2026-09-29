"""User administration and authentication service."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta
from getpass import getpass

from sqlalchemy import select

from .connection import Base, SessionLocal, engine
from .models import AuthenticationEvent, User
from .security import encrypt_text, hash_password, needs_rehash, verify_password


MAX_FAILURES = 5
LOCK_MINUTES = 15


def normalize_username(username: str) -> str:
    value = username.strip().lower()
    if not 3 <= len(value) <= 80 or not all(char.isalnum() or char in "._-" for char in value):
        raise ValueError("Username must be 3-80 characters using letters, numbers, '.', '_' or '-'")
    return value


def create_user(username: str, password: str, *, is_admin: bool = False) -> int:
    Base.metadata.create_all(engine, tables=[User.__table__, AuthenticationEvent.__table__])
    username = normalize_username(username)
    with SessionLocal.begin() as session:
        if session.scalar(select(User).where(User.username == username)) is not None:
            raise ValueError(f"User already exists: {username}")
        user = User(username=username, password_hash=hash_password(password), is_admin=is_admin)
        session.add(user)
        session.flush()
        return user.user_id


def change_password(username: str, password: str) -> None:
    username = normalize_username(username)
    with SessionLocal.begin() as session:
        user = session.scalar(select(User).where(User.username == username))
        if user is None:
            raise ValueError(f"Unknown user: {username}")
        user.password_hash = hash_password(password)
        user.failed_login_count = 0
        user.locked_until = None


@dataclass(frozen=True)
class AuthResult:
    success: bool
    reason: str
    user_id: int | None = None
    username: str | None = None
    is_admin: bool = False


def authenticate(username: str, password: str, client_ip: str, user_agent: str = "") -> AuthResult:
    try:
        username = normalize_username(username)
    except ValueError:
        username = username.strip().lower()[:80] or "(empty)"
    now = datetime.now()
    with SessionLocal.begin() as session:
        user = session.scalar(select(User).where(User.username == username))
        if user is not None and user.locked_until is not None and user.locked_until > now:
            result = AuthResult(False, "locked", user.user_id, user.username, user.is_admin)
        elif user is None or not user.is_active or not verify_password(user.password_hash if user else None, password):
            if user is not None and user.is_active:
                user.failed_login_count += 1
                if user.failed_login_count >= MAX_FAILURES:
                    user.locked_until = now + timedelta(minutes=LOCK_MINUTES)
                    user.failed_login_count = 0
            result = AuthResult(False, "invalid_credentials", user.user_id if user else None)
        else:
            user.failed_login_count = 0
            user.locked_until = None
            user.last_login_at = now
            if needs_rehash(user.password_hash):
                user.password_hash = hash_password(password)
            result = AuthResult(True, "success", user.user_id, user.username, user.is_admin)
        session.add(AuthenticationEvent(
            user_id=result.user_id,
            username_attempted=username,
            occurred_at=now,
            success=result.success,
            reason=result.reason,
            client_ip_encrypted=encrypt_text(client_ip or "unknown", "auth.client_ip"),
            user_agent=(user_agent or "")[:255],
        ))
        return result


def _prompt_password(confirm: bool = True) -> str:
    password = getpass("Password: ")
    if confirm and password != getpass("Confirm password: "):
        raise ValueError("Passwords do not match")
    return password


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage dashboard users")
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create-user")
    create.add_argument("--username", required=True)
    create.add_argument("--admin", action="store_true")
    password = sub.add_parser("change-password")
    password.add_argument("--username", required=True)
    args = parser.parse_args()
    if args.command == "create-user":
        user_id = create_user(args.username, _prompt_password(), is_admin=args.admin)
        print(f"Created user {normalize_username(args.username)} (id={user_id})")
    else:
        change_password(args.username, _prompt_password())
        print(f"Changed password for {normalize_username(args.username)}")


if __name__ == "__main__":
    main()
