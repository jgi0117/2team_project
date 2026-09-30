from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, LargeBinary, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .connection import Base


class User(Base):
    __tablename__ = "users"
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    failed_logins: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)


class LoginAudit(Base):
    __tablename__ = "login_audits"
    audit_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    reason: Mapped[str] = mapped_column(String(50), nullable=False)
    client_ip_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False, index=True)


class UiState(Base):
    __tablename__ = "ui_states"
    __table_args__ = (UniqueConstraint("owner_key", "state_key", name="uq_ui_state_owner_key"),)
    state_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    owner_key: Mapped[str] = mapped_column(String(100), nullable=False)
    state_key: Mapped[str] = mapped_column(String(50), nullable=False)
    value_json: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)


class UiEvent(Base):
    __tablename__ = "ui_events"
    event_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    owner_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False, index=True)


class OrderRecord(Base):
    __tablename__ = "order_records"
    __table_args__ = (UniqueConstraint("owner_key", "order_key", name="uq_order_owner_key"),)
    order_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    owner_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    order_key: Mapped[str] = mapped_column(String(64), nullable=False)
    business_date: Mapped[str] = mapped_column(String(10), nullable=False)
    machine_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    component: Mapped[str] = mapped_column(String(30), nullable=False)
    supplier_id: Mapped[str] = mapped_column(String(50), nullable=False)
    supplier_name: Mapped[str] = mapped_column(String(100), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="requested", nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)


class ErrorLog(Base):
    __tablename__ = "error_logs"
    error_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    owner_key: Mapped[str] = mapped_column(String(100), nullable=False)
    path: Mapped[str] = mapped_column(String(255), nullable=False)
    error_type: Mapped[str] = mapped_column(String(120), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False, index=True)


class SourceManifest(Base):
    __tablename__ = "source_manifest"
    source_path: Mapped[str] = mapped_column(String(255), primary_key=True)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    row_count: Mapped[int | None] = mapped_column(BigInteger)
    scanned_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)


class Dataset(Base):
    __tablename__ = "datasets"
    source_path: Mapped[str] = mapped_column(String(255), primary_key=True)
    table_name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    row_count: Mapped[int] = mapped_column(BigInteger, nullable=False)
    dtypes_json: Mapped[str] = mapped_column(Text, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
