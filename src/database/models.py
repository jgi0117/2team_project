"""Relational schema for maintenance, inventory, prediction, and UI actions."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .connection import Base


class Machine(Base):
    __tablename__ = "machines"

    machine_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    model: Mapped[str] = mapped_column(String(30), nullable=False)
    age: Mapped[int] = mapped_column(Integer, nullable=False)


class Supplier(Base):
    __tablename__ = "suppliers"

    supplier_id: Mapped[str] = mapped_column(String(30), primary_key=True)
    supplier_name: Mapped[str] = mapped_column(String(100), nullable=False)
    contact_department: Mapped[str | None] = mapped_column(String(100))
    contact_phone: Mapped[str | None] = mapped_column(String(50))
    contact_email: Mapped[str | None] = mapped_column(String(255))
    value_source: Mapped[str | None] = mapped_column(String(255))


class Part(Base):
    __tablename__ = "parts"

    component: Mapped[str] = mapped_column(String(30), primary_key=True)
    part_name: Mapped[str] = mapped_column(String(150), nullable=False)
    lead_time_days: Mapped[int] = mapped_column(Integer, nullable=False)
    preparation_days: Mapped[int] = mapped_column(Integer, nullable=False)
    target_stock: Mapped[int] = mapped_column(Integer, nullable=False)
    shelf_life_days: Mapped[int] = mapped_column(Integer, nullable=False)
    shelf_life_policy: Mapped[str | None] = mapped_column(String(100))
    storage_constraint: Mapped[str | None] = mapped_column(String(255))
    value_source: Mapped[str | None] = mapped_column(String(255))
    supplier_id: Mapped[str] = mapped_column(ForeignKey("suppliers.supplier_id"), nullable=False)


class CostPolicy(Base):
    __tablename__ = "cost_policies"

    component: Mapped[str] = mapped_column(ForeignKey("parts.component"), primary_key=True)
    cost_type: Mapped[str] = mapped_column(String(50), primary_key=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False)
    unit: Mapped[str] = mapped_column(String(50), nullable=False)
    value_source: Mapped[str | None] = mapped_column(String(255))


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    order_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    component: Mapped[str] = mapped_column(ForeignKey("parts.component"), nullable=False, index=True)
    supplier_id: Mapped[str] = mapped_column(ForeignKey("suppliers.supplier_id"), nullable=False)
    ordered_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    expected_receipt_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    actual_receipt_at: Mapped[datetime | None] = mapped_column(DateTime)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    value_source: Mapped[str | None] = mapped_column(String(255))


class InventoryLot(Base):
    __tablename__ = "inventory_lots"

    lot_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    component: Mapped[str] = mapped_column(ForeignKey("parts.component"), nullable=False, index=True)
    received_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    quantity_on_hand: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity_reserved: Mapped[int] = mapped_column(Integer, nullable=False)
    use_by_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    quality_status: Mapped[str] = mapped_column(String(30), nullable=False)
    value_source: Mapped[str | None] = mapped_column(String(255))
    order_id: Mapped[str | None] = mapped_column(String(40), index=True)
    quantity_received: Mapped[int] = mapped_column(Integer, nullable=False)
    ready_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    as_of: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class MaintenanceRecord(Base):
    __tablename__ = "maintenance_records"

    record_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    machine_id: Mapped[int] = mapped_column(ForeignKey("machines.machine_id"), nullable=False, index=True)
    component: Mapped[str] = mapped_column(ForeignKey("parts.component"), nullable=False)
    planned_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    maintenance_type: Mapped[str] = mapped_column(String(80), nullable=False)
    used_lot_id: Mapped[str | None] = mapped_column(String(40))
    quantity_used: Mapped[int | None] = mapped_column(Integer)
    result: Mapped[str] = mapped_column(String(30), nullable=False)
    value_source: Mapped[str | None] = mapped_column(String(255))
    source_event_at: Mapped[datetime | None] = mapped_column(DateTime)
    quantity_requested: Mapped[int] = mapped_column(Integer, nullable=False)


class InventoryMovement(Base):
    __tablename__ = "inventory_movements"

    movement_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    lot_id: Mapped[str] = mapped_column(ForeignKey("inventory_lots.lot_id"), nullable=False, index=True)
    component: Mapped[str] = mapped_column(ForeignKey("parts.component"), nullable=False)
    movement_type: Mapped[str] = mapped_column(String(30), nullable=False)
    quantity_delta: Mapped[int] = mapped_column(Integer, nullable=False)
    quality_status: Mapped[str | None] = mapped_column(String(30))
    record_id: Mapped[str | None] = mapped_column(String(40), index=True)
    value_source: Mapped[str | None] = mapped_column(String(255))


class Telemetry(Base):
    __tablename__ = "telemetry"
    __table_args__ = (
        UniqueConstraint("machine_id", "measured_at", name="uq_telemetry_machine_time"),
        Index("ix_telemetry_time_machine", "measured_at", "machine_id"),
    )

    telemetry_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    machine_id: Mapped[int] = mapped_column(ForeignKey("machines.machine_id"), nullable=False)
    measured_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    volt: Mapped[float] = mapped_column(Float, nullable=False)
    rotate: Mapped[float] = mapped_column(Float, nullable=False)
    pressure: Mapped[float] = mapped_column(Float, nullable=False)
    vibration: Mapped[float] = mapped_column(Float, nullable=False)


class MachineError(Base):
    __tablename__ = "machine_errors"
    __table_args__ = (UniqueConstraint("machine_id", "occurred_at", "error_code", name="uq_machine_error"),)

    error_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    machine_id: Mapped[int] = mapped_column(ForeignKey("machines.machine_id"), nullable=False, index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    error_code: Mapped[str] = mapped_column(String(30), nullable=False)


class MachineFailure(Base):
    __tablename__ = "machine_failures"
    __table_args__ = (UniqueConstraint("machine_id", "occurred_at", "component", name="uq_machine_failure"),)

    failure_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    machine_id: Mapped[int] = mapped_column(ForeignKey("machines.machine_id"), nullable=False, index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    component: Mapped[str] = mapped_column(ForeignKey("parts.component"), nullable=False)


class MachineMaintenanceEvent(Base):
    __tablename__ = "machine_maintenance_events"
    __table_args__ = (UniqueConstraint("machine_id", "occurred_at", "component", name="uq_machine_maint_event"),)

    event_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    machine_id: Mapped[int] = mapped_column(ForeignKey("machines.machine_id"), nullable=False, index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    component: Mapped[str] = mapped_column(ForeignKey("parts.component"), nullable=False)


class FailurePrediction(Base):
    __tablename__ = "failure_predictions"
    __table_args__ = (
        UniqueConstraint("machine_id", "component", "as_of", "horizon_days", "model_version",
                         name="uq_failure_prediction"),
        Index("ix_failure_prediction_lookup", "as_of", "horizon_days", "component"),
    )

    prediction_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    machine_id: Mapped[int] = mapped_column(ForeignKey("machines.machine_id"), nullable=False)
    component: Mapped[str] = mapped_column(ForeignKey("parts.component"), nullable=False)
    as_of: Mapped[date] = mapped_column(Date, nullable=False)
    horizon_days: Mapped[int] = mapped_column(Integer, nullable=False)
    failure_probability: Mapped[float] = mapped_column(Float, nullable=False)
    model_version: Mapped[str] = mapped_column(String(80), nullable=False)
    calibrated: Mapped[bool] = mapped_column(Boolean, nullable=False)
    source: Mapped[str | None] = mapped_column(String(50))
    model_adopted: Mapped[bool] = mapped_column(Boolean, nullable=False)


class RiskCurve(Base):
    __tablename__ = "risk_curves"
    __table_args__ = (UniqueConstraint("machine_id", "component", "as_of", "model_version", name="uq_risk_curve"),)

    risk_curve_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    as_of: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    machine_id: Mapped[int] = mapped_column(ForeignKey("machines.machine_id"), nullable=False)
    component: Mapped[str] = mapped_column(ForeignKey("parts.component"), nullable=False)
    decision_horizon_days: Mapped[int] = mapped_column(Integer, nullable=False)
    risk_rise_from_days: Mapped[float | None] = mapped_column(Float)
    risk_rise_mid_days: Mapped[float | None] = mapped_column(Float)
    risk_rise_to_days: Mapped[float | None] = mapped_column(Float)
    risk_threshold: Mapped[float] = mapped_column(Float, nullable=False)
    risk_status: Mapped[str] = mapped_column(String(30), nullable=False)
    probability_at_horizon: Mapped[float] = mapped_column(Float, nullable=False)
    model_adopted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    model_version: Mapped[str] = mapped_column(String(80), nullable=False)
    calibrated: Mapped[bool] = mapped_column(Boolean, nullable=False)


class AnomalyPrediction(Base):
    __tablename__ = "anomaly_predictions"
    __table_args__ = (UniqueConstraint("machine_id", "as_of", name="uq_anomaly_prediction"),)

    anomaly_prediction_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    machine_id: Mapped[int] = mapped_column(ForeignKey("machines.machine_id"), nullable=False, index=True)
    as_of: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    split: Mapped[str | None] = mapped_column(String(20))
    volt: Mapped[float] = mapped_column(Float, nullable=False)
    rotate: Mapped[float] = mapped_column(Float, nullable=False)
    pressure: Mapped[float] = mapped_column(Float, nullable=False)
    vibration: Mapped[float] = mapped_column(Float, nullable=False)
    anomaly_score: Mapped[float] = mapped_column(Float, nullable=False)
    threshold: Mapped[float] = mapped_column(Float, nullable=False)
    is_anomaly: Mapped[bool] = mapped_column(Boolean, nullable=False)


class ProcurementRequest(Base):
    __tablename__ = "procurement_requests"

    request_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, index=True)
    business_as_of: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="requested")
    total_amount_krw: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    request_source: Mapped[str] = mapped_column(String(30), nullable=False, default="dashboard")
    created_by_user_id: Mapped[int | None] = mapped_column(BigInteger)


class ProcurementRequestItem(Base):
    __tablename__ = "procurement_request_items"

    request_item_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("procurement_requests.request_id"), nullable=False, index=True)
    machine_id: Mapped[int] = mapped_column(ForeignKey("machines.machine_id"), nullable=False, index=True)
    component: Mapped[str] = mapped_column(ForeignKey("parts.component"), nullable=False)
    supplier_id: Mapped[str] = mapped_column(String(30), nullable=False)
    supplier_name_snapshot: Mapped[str] = mapped_column(String(100), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price_krw: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    lead_time_days: Mapped[int | None] = mapped_column(Integer)
    order_deadline: Mapped[date | None] = mapped_column(Date)
    target_maintenance_at: Mapped[date | None] = mapped_column(Date)
    reason: Mapped[str | None] = mapped_column(Text)


class ProcurementStatusHistory(Base):
    __tablename__ = "procurement_status_history"

    history_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("procurement_requests.request_id"), nullable=False, index=True)
    previous_status: Mapped[str | None] = mapped_column(String(30))
    new_status: Mapped[str] = mapped_column(String(30), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)
    note: Mapped[str | None] = mapped_column(Text)
    changed_by_user_id: Mapped[int | None] = mapped_column(BigInteger)


class ActionTask(Base):
    __tablename__ = "action_tasks"
    __table_args__ = (UniqueConstraint("task_key", "business_as_of", name="uq_action_task"),)

    task_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    task_key: Mapped[str] = mapped_column(String(100), nullable=False)
    machine_id: Mapped[int] = mapped_column(ForeignKey("machines.machine_id"), nullable=False, index=True)
    component: Mapped[str | None] = mapped_column(String(30))
    task_type: Mapped[str] = mapped_column(String(40), nullable=False)
    business_as_of: Mapped[date] = mapped_column(Date, nullable=False)
    priority: Mapped[int | None] = mapped_column(Integer)
    due_at: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="open")
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime)


class TaskActionHistory(Base):
    __tablename__ = "task_action_history"

    action_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("action_tasks.task_id"), nullable=False, index=True)
    action_type: Mapped[str] = mapped_column(String(30), nullable=False)
    action_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)
    note: Mapped[str | None] = mapped_column(Text)
    related_request_id: Mapped[int | None] = mapped_column(BigInteger)
    related_maintenance_record_id: Mapped[str | None] = mapped_column(String(40))
    actor_user_id: Mapped[int | None] = mapped_column(BigInteger)


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    failed_login_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now,
                                                  onupdate=datetime.now)


class AuthenticationEvent(Base):
    __tablename__ = "authentication_events"

    event_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.user_id"), index=True)
    username_attempted: Mapped[str] = mapped_column(String(80), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, index=True)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    reason: Mapped[str] = mapped_column(String(50), nullable=False)
    client_ip_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary)
    user_agent: Mapped[str | None] = mapped_column(String(255))
