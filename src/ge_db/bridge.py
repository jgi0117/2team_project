"""Observe completed GE callbacks and persist their results without adding Dash callbacks."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import datetime

from flask import has_request_context, request, session
from sqlalchemy import select, update

from .connection import Base, SessionLocal, enabled, engine
from .models import OrderRecord, UiEvent, UiState


TRACKED_STORES = {
    "store-todo-dismissed": "todo",
    "store-order-log": "orders",
    "store-settings": "settings",
}


def _owner() -> str:
    if has_request_context() and session.get("user_id"):
        return f"user:{session.get('user_id')}"
    return "anonymous"


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


def persist_updates(updates: dict[str, object], owner: str | None = None) -> int:
    if not updates:
        return 0
    Base.metadata.create_all(engine, tables=[UiState.__table__, UiEvent.__table__, OrderRecord.__table__])
    owner = owner or _owner()
    changed = 0
    with SessionLocal.begin() as db:
        for key, value in updates.items():
            changed += _sync_state(db, owner, key, value)
        if "orders" in updates:
            _sync_orders(db, owner, list(updates["orders"] or []))
    return changed


def persist(todo, orders, settings, owner: str | None = None) -> int:
    return persist_updates({"todo": todo or [], "orders": orders or [], "settings": settings or {}}, owner)


def install(server) -> None:
    """Attach a response observer; GE's layout and callback map remain untouched."""

    @server.after_request
    def observe_ge_callback(response):
        if not enabled() or request.path != "/_dash-update-component" or response.status_code != 200:
            return response
        try:
            body = response.get_json(silent=True) or {}
            callback_response = body.get("response", {})
            updates = {
                state_key: callback_response[store_id]["data"]
                for store_id, state_key in TRACKED_STORES.items()
                if isinstance(callback_response.get(store_id), dict)
                and "data" in callback_response[store_id]
            }
            persist_updates(updates)
        except Exception:
            pass
        return response
