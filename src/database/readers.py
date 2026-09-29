"""DataFrame readers that prefer MySQL and let offline tests fall back to CSV."""

from __future__ import annotations

from functools import lru_cache

import pandas as pd
from sqlalchemy import inspect

from .connection import database_enabled, engine


OPS_TABLES = {
    "costs.csv": "cost_policies",
    "inventory_lots.csv": "inventory_lots",
    "inventory_movements.csv": "inventory_movements",
    "maintenance_records.csv": "maintenance_records",
    "part_master.csv": "parts",
    "purchase_orders.csv": "purchase_orders",
    "suppliers.csv": "suppliers",
}

TABLE_RENAMES = {
    "machines": {"machine_id": "machineID"},
    "telemetry": {"machine_id": "machineID", "measured_at": "datetime"},
    "machine_errors": {"machine_id": "machineID", "occurred_at": "datetime", "error_code": "errorID"},
    "machine_failures": {"machine_id": "machineID", "occurred_at": "datetime", "component": "failure"},
    "machine_maintenance_events": {"machine_id": "machineID", "occurred_at": "datetime", "component": "comp"},
    "maintenance_records": {"machine_id": "machineID"},
    "failure_predictions": {"machine_id": "machineID"},
    "risk_curves": {"machine_id": "machineID", "probability_at_horizon": "p_at_decision_horizon"},
    "anomaly_predictions": {"machine_id": "machineID"},
}

INTERNAL_IDS = {
    "telemetry": "telemetry_id",
    "machine_errors": "error_id",
    "machine_failures": "failure_id",
    "machine_maintenance_events": "event_id",
    "failure_predictions": "prediction_id",
    "risk_curves": "risk_curve_id",
    "anomaly_predictions": "anomaly_prediction_id",
}


@lru_cache(maxsize=32)
def table_available(table_name: str) -> bool:
    if not database_enabled():
        return False
    try:
        return inspect(engine).has_table(table_name)
    except Exception:
        return False


def read_table(table_name: str) -> pd.DataFrame | None:
    if not table_available(table_name):
        return None
    data = pd.read_sql_table(table_name, engine)
    internal = INTERNAL_IDS.get(table_name)
    if internal in data.columns:
        data = data.drop(columns=internal)
    return data.rename(columns=TABLE_RENAMES.get(table_name, {}))


def read_operation(filename: str) -> pd.DataFrame | None:
    table = OPS_TABLES.get(filename)
    return read_table(table) if table else None
