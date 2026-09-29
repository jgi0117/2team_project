"""Transactional writes produced by dashboard interactions."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select

from .connection import SessionLocal, database_enabled
from .models import (
    ActionTask,
    ProcurementRequest,
    ProcurementRequestItem,
    ProcurementStatusHistory,
    TaskActionHistory,
)
from .readers import table_available


def ready() -> bool:
    return database_enabled() and table_available("procurement_requests")


def create_procurement_request(lines: list[dict], business_as_of: str, actor_user_id: int | None = None) -> int:
    if not lines:
        raise ValueError("At least one order line is required")
    if not ready():
        raise RuntimeError("MySQL schema has not been initialized")

    as_of = date.fromisoformat(business_as_of)
    total = sum(Decimal(str(line["price"])) * 10_000 * int(line["qty"]) for line in lines)
    now = datetime.now()
    with SessionLocal.begin() as session:
        request = ProcurementRequest(
            requested_at=now,
            business_as_of=as_of,
            status="requested",
            total_amount_krw=total,
            request_source="dashboard",
            created_by_user_id=actor_user_id,
        )
        session.add(request)
        session.flush()
        tasks: dict[str, ActionTask] = {}
        for line in lines:
            session.add(ProcurementRequestItem(
                request_id=request.request_id,
                machine_id=int(line["machine"]),
                component=line["comp"],
                supplier_id=line["supplier"],
                supplier_name_snapshot=line["supplier_name"],
                quantity=int(line["qty"]),
                unit_price_krw=Decimal(str(line["price"])) * 10_000,
                lead_time_days=int(line.get("lead") or 0),
                order_deadline=(date.fromisoformat(line["order_deadline"])
                                if line.get("order_deadline") else None),
                target_maintenance_at=(date.fromisoformat(line["target_maintenance_at"])
                                       if line.get("target_maintenance_at") else None),
                reason=line.get("reason"),
            ))
            task_key = f"{int(line['machine'])}-{line['comp']}"
            if task_key not in tasks:
                task = session.scalar(select(ActionTask).where(
                    ActionTask.task_key == task_key,
                    ActionTask.business_as_of == as_of,
                ))
                if task is None:
                    task = ActionTask(
                        task_key=task_key,
                        machine_id=int(line["machine"]),
                        component=line["comp"],
                        task_type="procurement_due",
                        business_as_of=as_of,
                        status="order_requested",
                        reason=line.get("reason") or "Dashboard procurement request",
                    )
                    session.add(task)
                    session.flush()
                else:
                    task.status = "order_requested"
                tasks[task_key] = task
        for task in tasks.values():
            session.add(TaskActionHistory(
                task_id=task.task_id,
                action_type="order_requested",
                action_at=now,
                related_request_id=request.request_id,
                actor_user_id=actor_user_id,
            ))
        session.add(ProcurementStatusHistory(
            request_id=request.request_id,
            previous_status=None,
            new_status="requested",
            changed_at=now,
            note="Created from dashboard",
            changed_by_user_id=actor_user_id,
        ))
        return request.request_id


def list_procurement_request_items(limit: int = 500) -> list[dict]:
    if not ready():
        return []
    with SessionLocal() as session:
        rows = session.execute(
            select(ProcurementRequest, ProcurementRequestItem)
            .join(ProcurementRequestItem, ProcurementRequestItem.request_id == ProcurementRequest.request_id)
            .order_by(ProcurementRequest.requested_at.desc(), ProcurementRequestItem.request_item_id.desc())
            .limit(limit)
        ).all()
    return [{
        "request_id": request.request_id,
        "machine": item.machine_id,
        "component": item.component,
        "supplier": item.supplier_id,
        "supplier_name": item.supplier_name_snapshot,
        "qty": item.quantity,
        "price": float(item.unit_price_krw) / 10_000,
        "date": request.business_as_of.isoformat(),
        "requested_at": request.requested_at.isoformat(timespec="seconds"),
        "status": request.status,
    } for request, item in rows]


def list_dismissed_task_keys(business_as_of: str) -> list[str]:
    if not ready():
        return []
    as_of = date.fromisoformat(business_as_of)
    with SessionLocal() as session:
        return list(session.scalars(select(ActionTask.task_key).where(
            ActionTask.business_as_of == as_of,
            ActionTask.status == "dismissed",
        )).all())


def record_task_action(item: dict, business_as_of: str, action_type: str,
                       actor_user_id: int | None = None) -> None:
    if not ready():
        return
    as_of = date.fromisoformat(business_as_of)
    now = datetime.now()
    with SessionLocal.begin() as session:
        task = session.scalar(select(ActionTask).where(
            ActionTask.task_key == item["key"],
            ActionTask.business_as_of == as_of,
        ))
        if task is None:
            task = ActionTask(
                task_key=item["key"],
                machine_id=int(item["machine"]),
                component=item.get("component"),
                task_type=item.get("issue", "dashboard_todo"),
                business_as_of=as_of,
                priority=item.get("risk"),
                due_at=date.fromisoformat(item["date"]) if item.get("date") else None,
                reason=item.get("note"),
                status="open",
            )
            session.add(task)
            session.flush()
        task.status = "dismissed" if action_type == "dismissed" else "open"
        task.resolved_at = now if action_type == "dismissed" else None
        session.add(TaskActionHistory(task_id=task.task_id, action_type=action_type, action_at=now,
                                      actor_user_id=actor_user_id))


def restore_tasks(task_keys: list[str], business_as_of: str, actor_user_id: int | None = None) -> None:
    if not ready() or not task_keys:
        return
    as_of = date.fromisoformat(business_as_of)
    with SessionLocal.begin() as session:
        tasks = session.scalars(select(ActionTask).where(
            ActionTask.task_key.in_(task_keys),
            ActionTask.business_as_of == as_of,
        )).all()
        now = datetime.now()
        for task in tasks:
            task.status = "open"
            task.resolved_at = None
            session.add(TaskActionHistory(task_id=task.task_id, action_type="restored", action_at=now,
                                          actor_user_id=actor_user_id))
