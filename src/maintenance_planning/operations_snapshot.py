"""Reconstruct the synthetic operating state without future leakage."""

from __future__ import annotations

from functools import lru_cache

import pandas as pd

from src.common.paths import OPS


START = pd.Timestamp("2015-04-01 06:00:00")
END = pd.Timestamp("2016-01-01 06:00:00")


@lru_cache(maxsize=None)
def _csv(name: str) -> pd.DataFrame:
    return pd.read_csv(OPS / name)


def _at(value) -> pd.Timestamp:
    at = pd.Timestamp(value)
    if at.tz is not None or pd.isna(at):
        raise ValueError("as_of must be a timezone-naive valid timestamp")
    if not START <= at <= END:
        raise ValueError(f"as_of must be between {START} and {END}")
    return at


def snapshot(as_of) -> dict:
    """Return inventory, orders, and maintenance records known at ``as_of``."""
    at = _at(as_of)
    lots = _csv("inventory_lots.csv").copy()
    moves = _csv("inventory_movements.csv").copy()
    moves["occurred_at"] = pd.to_datetime(moves["occurred_at"])
    known_moves = moves.loc[moves.occurred_at.le(at)].sort_values("occurred_at")

    quantities = known_moves.groupby("lot_id").quantity_delta.sum()
    latest_quality = (known_moves.loc[known_moves.quality_status.notna()
                                      & known_moves.quality_status.ne("")]
                      .drop_duplicates("lot_id", keep="last")
                      .set_index("lot_id").quality_status)
    lots["ready_at"] = pd.to_datetime(lots["ready_at"])
    lots["use_by_at"] = pd.to_datetime(lots["use_by_at"])
    lots["quantity_on_hand"] = lots.lot_id.map(quantities).fillna(0).clip(lower=0).astype(int)
    lots["quality_status"] = lots.lot_id.map(latest_quality).fillna("unknown")
    ready = lots.ready_at.le(at)
    valid = lots.use_by_at.gt(at)
    quality = lots.quality_status.eq("available")
    lots["quantity_available"] = (lots.quantity_on_hand - lots.quantity_reserved.fillna(0))
    lots["quantity_available"] = lots.quantity_available.where(ready & valid & quality, 0).clip(lower=0).astype(int)

    orders = _csv("purchase_orders.csv").copy()
    for col in ("ordered_at", "expected_receipt_at", "actual_receipt_at"):
        orders[col] = pd.to_datetime(orders[col])
    orders = orders.loc[orders.ordered_at.le(at)].copy()
    received = orders.actual_receipt_at.notna() & orders.actual_receipt_at.le(at)
    orders.loc[~received, "actual_receipt_at"] = pd.NaT
    orders["status_as_of"] = received.map({True: "received", False: "open"})

    records = _csv("maintenance_records.csv").copy()
    for col in ("planned_at", "completed_at", "source_event_at"):
        records[col] = pd.to_datetime(records[col])
    records = records.loc[records.planned_at.le(at)].copy()
    completed = records.completed_at.notna() & records.completed_at.le(at)
    records.loc[~completed, ["completed_at", "used_lot_id", "quantity_used"]] = [pd.NaT, None, None]
    records["result_as_of"] = completed.map({True: "completed", False: "pending"})

    def rows(frame):
        return frame.astype(object).where(pd.notna(frame), None).to_dict("records")

    return {
        "as_of": at.isoformat(),
        "inventory_lots": rows(lots),
        "purchase_orders": rows(orders),
        "maintenance_records": rows(records),
    }
