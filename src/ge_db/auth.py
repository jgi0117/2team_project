from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func, select

from .connection import Base, SessionLocal, engine
from .models import LoginAudit, User
from .security import encrypt_text, hash_password, verify_password


def has_users() -> bool:
    Base.metadata.create_all(engine, tables=[User.__table__, LoginAudit.__table__])
    with SessionLocal() as session:
        return bool(session.scalar(select(func.count()).select_from(User)))


def create_admin(username: str, password: str) -> int:
    username = username.strip().lower()
    if not 3 <= len(username) <= 80 or not all(c.isalnum() or c in "._-" for c in username):
        raise ValueError("사용자명 형식이 올바르지 않습니다.")
    with SessionLocal.begin() as session:
        if session.scalar(select(User).where(User.username == username)):
            raise ValueError("이미 존재하는 사용자명입니다.")
        user = User(username=username, password_hash=hash_password(password), is_admin=True)
        session.add(user)
        session.flush()
        return user.user_id


def authenticate(username: str, password: str, client_ip: str) -> User | None:
    username = username.strip().lower()[:80]
    now = datetime.now()
    with SessionLocal.begin() as session:
        user = session.scalar(select(User).where(User.username == username))
        reason = "invalid_credentials"
        success = False
        if user and user.is_active and (not user.locked_until or user.locked_until <= now):
            success = verify_password(user.password_hash, password)
            if success:
                user.failed_logins = 0
                user.locked_until = None
                reason = "success"
            else:
                user.failed_logins += 1
                if user.failed_logins >= 5:
                    user.failed_logins = 0
                    user.locked_until = now + timedelta(minutes=15)
                    reason = "locked"
        elif user and user.locked_until and user.locked_until > now:
            reason = "locked"
        session.add(LoginAudit(username=username or "(empty)", success=success, reason=reason,
                               client_ip_encrypted=encrypt_text(client_ip or "unknown")))
        if success:
            session.flush()
            session.expunge(user)
            return user
    return None
