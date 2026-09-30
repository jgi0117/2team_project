"""Write-only persistence for GE browser stores; never a GE rendering dependency."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import datetime

from dash import Input, Output
from flask import has_request_context, session
from sqlalchemy import select, update

from .connection import Base, SessionLocal, enabled, engine
from .models import OrderRecord, UiEvent, UiState


def _owner() -> str:
    return f"user:{session.get('user_id')}" if has_request_context() and session.get("user_id") else "anonymous"


def _json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _sync_state(db, owner: str, key: str, value) -> bool:
    payload = _json(value)
    row = db.scalar(select(UiState).where(UiState.owner_key == owner, UiState.state_key == key))
    if row and row.value_json == payload:
        return False
    if row is None:
        db.add(UiState(owner_key=owner, state_key=key, value_json=payload))
    else:
        row.value_json = payload
        row.updated_at = datetime.now()
    db.add(UiEvent(owner_key=owner, event_type=f"{key}_changed", payload_json=payload))
    return True


def _sync_orders(db, owner: str, orders: list[dict]) -> None:
    db.execute(update(OrderRecord).where(OrderRecord.owner_key == owner).values(status="cancelled"))
    occurrences: dict[str, int] = defaultdict(int)
    for order in orders:
        payload = _json(order)
        occurrences[payload] += 1
        key = hashlib.sha256(f"{payload}#{occurrences[payload]}".encode()).hexdigest()
        row = db.scalar(select(OrderRecord).where(
            OrderRecord.owner_key == owner, OrderRecord.order_key == key
        ))
        values = dict(
            business_date=str(order.get("date", ""))[:10], machine_id=int(order.get("machine", 0)),
            component=str(order.get("component", "")), supplier_id=str(order.get("supplier", "")),
            supplier_name=str(order.get("supplier_name", order.get("supplier", ""))),
            quantity=int(order.get("qty", 1)), unit_price=order.get("price", 0),
            status="requested", payload_json=payload, updated_at=datetime.now(),
        )
        if row is None:
            db.add(OrderRecord(owner_key=owner, order_key=key, **values))
        else:
            for name, value in values.items():
                setattr(row, name, value)


def persist(todo, orders, settings) -> int:
    Base.metadata.create_all(engine, tables=[UiState.__table__, UiEvent.__table__, OrderRecord.__table__])
    owner = _owner()
    changed = 0
    with SessionLocal.begin() as db:
        changed += _sync_state(db, owner, "todo", todo or [])
        changed += _sync_state(db, owner, "orders", orders or [])
        changed += _sync_state(db, owner, "settings", settings or {})
        _sync_orders(db, owner, orders or [])
    return changed


def register(app) -> None:
    @app.callback(
        Output("ge-db-sync", "data"),
        Input("store-todo-dismissed", "data"),
        Input("store-order-log", "data"),
        Input("store-settings", "data"),
    )
    def mirror(todo, orders, settings):
        if not enabled():
            return {"enabled": False}
        try:
            return {"enabled": True, "ok": True, "changed": persist(todo, orders, settings)}
        except Exception as error:
            return {"enabled": True, "ok": False, "error": type(error).__name__}
