"""Build explainable procurement and daily inventory history tables."""

from __future__ import annotations

from functools import lru_cache

import pandas as pd

from src.common.paths import OPS, PROCESSED
from .operations_snapshot import END, START, snapshot


def _read(name: str) -> pd.DataFrame:
    return pd.read_csv(OPS / name)


def build_procurement_history() -> pd.DataFrame:
    orders = _read("purchase_orders.csv")
    parts = _read("part_master.csv")
    suppliers = _read("suppliers.csv")
    lots = _read("inventory_lots.csv")
    costs = _read("costs.csv")
    for column in ("ordered_at", "expected_receipt_at", "actual_receipt_at"):
        orders[column] = pd.to_datetime(orders[column])
    for column in ("received_at", "ready_at", "use_by_at"):
        lots[column] = pd.to_datetime(lots[column])

    lot_info = (lots.loc[lots.order_id.notna(), [
        "order_id", "lot_id", "received_at", "ready_at", "use_by_at",
        "quantity_received",
    ]].drop_duplicates("order_id"))
    purchase = (costs.loc[costs.cost_type.eq("purchase"), ["component", "amount"]]
                .rename(columns={"amount": "purchase_unit_cost"}))
    admin = (costs.loc[costs.cost_type.eq("order_admin"), ["component", "amount"]]
             .rename(columns={"amount": "order_admin_cost"}))
    result = (orders.merge(parts.drop(columns=["supplier_id"]), on="component", how="left",
                           validate="many_to_one")
              .merge(suppliers, on="supplier_id", how="left", validate="many_to_one",
                     suffixes=("", "_supplier"))
              .merge(lot_info, on="order_id", how="left", validate="one_to_one")
              .merge(purchase, on="component", how="left", validate="many_to_one")
              .merge(admin, on="component", how="left", validate="many_to_one"))

    stock_at_order, open_at_order = [], []
    for row in result.itertuples(index=False):
        ordered_at = pd.Timestamp(row.ordered_at)
        if ordered_at < START:
            stock_at_order.append(pd.NA)
            open_at_order.append(pd.NA)
            continue
        at = min(ordered_at, END)
        state = snapshot(at)
        stock_at_order.append(sum(
            int(lot["quantity_available"]) for lot in state["inventory_lots"]
            if lot["component"] == row.component
        ))
        open_at_order.append(sum(
            int(order["quantity"]) for order in state["purchase_orders"]
            if order["component"] == row.component
            and order["status_as_of"] == "open"
            and order["order_id"] != row.order_id
        ))
    result["available_stock_at_order"] = stock_at_order
    result["open_order_qty_before"] = open_at_order
    result["stock_position_at_order"] = result.available_stock_at_order + result.open_order_qty_before
    result["replenishment_gap_at_order"] = (
        result.target_stock - result.stock_position_at_order
    ).clip(lower=0).astype("Int64")
    result["planned_lead_days"] = result.lead_time_days.astype(int)
    result["actual_lead_days"] = (
        result.actual_receipt_at - result.ordered_at
    ).dt.total_seconds().div(86400)
    result["receipt_delay_days"] = (
        result.actual_receipt_at - result.expected_receipt_at
    ).dt.total_seconds().div(86400)
    result["quality_hold_days"] = (
        result.ready_at - result.received_at
    ).dt.total_seconds().div(86400)
    result["planned_order_cost"] = (
        result.quantity * result.purchase_unit_cost + result.order_admin_cost
    ).round().astype(int)
    result["delivery_status"] = "open"
    received = result.actual_receipt_at.notna()
    result.loc[received & result.receipt_delay_days.le(0), "delivery_status"] = "on_time"
    result.loc[received & result.receipt_delay_days.gt(0), "delivery_status"] = "delayed"
    result["delay_bucket"] = "not_received"
    result.loc[result.delivery_status.eq("on_time"), "delay_bucket"] = "on_time"
    result.loc[result.receipt_delay_days.between(1, 5, inclusive="both"), "delay_bucket"] = "delay_1_5d"
    result.loc[result.receipt_delay_days.gt(5), "delay_bucket"] = "delay_6d_plus"
    result["quality_check_required"] = result.quality_hold_days.gt(result.preparation_days)
    result["order_reason"] = "정기 재고점검에서 목표 재고 포지션 부족"
    result.loc[result.ordered_at.lt(START), "order_reason"] = "운영 시작 시점의 진행 주문 가정"
    result["history_source"] = "derived:synthetic_operations_v1"
    columns = [
        "order_id", "component", "part_name", "supplier_id", "supplier_name",
        "contact_department", "ordered_at", "expected_receipt_at", "actual_receipt_at",
        "ready_at", "use_by_at", "quantity", "quantity_received",
        "available_stock_at_order", "open_order_qty_before", "stock_position_at_order",
        "target_stock", "replenishment_gap_at_order", "planned_lead_days",
        "actual_lead_days", "receipt_delay_days", "quality_hold_days",
        "delivery_status", "delay_bucket", "quality_check_required",
        "purchase_unit_cost", "order_admin_cost", "planned_order_cost",
        "order_reason", "history_source",
    ]
    return result[columns].sort_values(["ordered_at", "order_id"]).reset_index(drop=True)


def build_inventory_daily_history() -> pd.DataFrame:
    movements = _read("inventory_movements.csv")
    movements["occurred_at"] = pd.to_datetime(movements["occurred_at"])
    movements["date"] = movements.occurred_at.dt.normalize()
    parts = _read("part_master.csv").set_index("component")
    dates = pd.date_range(START.normalize(), END.normalize(), freq="D")
    event_counts = (movements.groupby(["date", "component", "movement_type"])
                    .agg(event_count=("movement_id", "size"), quantity_delta=("quantity_delta", "sum"))
                    .reset_index())
    rows = []
    for date in dates:
        at = min(date + pd.Timedelta(hours=6), END)
        state = snapshot(at)
        lots = pd.DataFrame(state["inventory_lots"])
        orders = pd.DataFrame(state["purchase_orders"])
        records = pd.DataFrame(state["maintenance_records"])
        day_events = event_counts.loc[event_counts.date.eq(date)]
        for component, meta in parts.iterrows():
            component_lots = lots.loc[lots.component.eq(component)]
            component_orders = orders.loc[orders.component.eq(component)]
            component_records = records.loc[records.component.eq(component)]
            events = day_events.loc[day_events.component.eq(component)].set_index("movement_type")

            def qty(kind, *, positive=True):
                if kind not in events.index:
                    return 0
                value = int(events.loc[kind, "quantity_delta"])
                return max(0, value) if positive else max(0, -value)

            def count(kind):
                return 0 if kind not in events.index else int(events.loc[kind, "event_count"])

            on_hand = int(component_lots.quantity_on_hand.sum())
            available = int(component_lots.quantity_available.sum())
            open_orders = component_orders.loc[component_orders.status_as_of.eq("open")]
            pending = component_records.loc[component_records.result_as_of.eq("pending")]
            target = int(meta.target_stock)
            notes = []
            for label, value in (("입고", qty("receipt")), ("출고", qty("issue", positive=False)),
                                 ("기한초과", count("expiry")), ("폐기", qty("disposal", positive=False)),
                                 ("검사해제", count("quality_release"))):
                if value:
                    notes.append(f"{label} {value}")
            rows.append({
                "date": date, "component": component,
                "opening_qty": qty("opening"), "received_qty": qty("receipt"),
                "issued_qty": qty("issue", positive=False),
                "expired_lot_events": count("expiry"),
                "disposed_qty": qty("disposal", positive=False),
                "quality_release_events": count("quality_release"),
                "closing_on_hand": on_hand, "available_stock": available,
                "quarantined_stock": int(component_lots.loc[
                    component_lots.quality_status.eq("quarantined"), "quantity_on_hand"
                ].sum()),
                "expired_stock": int(component_lots.loc[
                    component_lots.use_by_at.le(at), "quantity_on_hand"
                ].sum()),
                "open_order_count": int(len(open_orders)),
                "open_order_qty": int(open_orders.quantity.sum()) if not open_orders.empty else 0,
                "pending_maintenance_count": int(len(pending)),
                "target_stock": target, "stock_gap": max(0, target - available),
                "stock_status": "shortage" if available < target else "at_target" if available == target else "above_target",
                "daily_event_summary": "; ".join(notes) if notes else "변동 없음",
                "history_source": "derived:synthetic_operations_v1",
            })
    return pd.DataFrame(rows)


def export_histories(output_dir=PROCESSED) -> tuple:
    output_dir.mkdir(parents=True, exist_ok=True)
    procurement = build_procurement_history()
    inventory = build_inventory_daily_history()
    procurement_path = output_dir / "procurement_history.csv"
    inventory_path = output_dir / "inventory_daily_history.csv"
    procurement.to_csv(procurement_path, index=False)
    inventory.to_csv(inventory_path, index=False)
    return procurement_path, inventory_path


if __name__ == "__main__":
    for path in export_histories():
        print(path)
