"""Create the MySQL database and import the project's source-of-truth data.

Run from the project root::

    python -m src.database.bootstrap
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, func, select, text

from .connection import Base, database_url, engine
from .models import (
    AnomalyPrediction,
    CostPolicy,
    FailurePrediction,
    InventoryLot,
    InventoryMovement,
    Machine,
    MachineError,
    MachineFailure,
    MachineMaintenanceEvent,
    MaintenanceRecord,
    Part,
    PurchaseOrder,
    RiskCurve,
    Supplier,
    Telemetry,
)


ROOT = Path(__file__).resolve().parents[2]
OPS = ROOT / "data" / "operations"
RAW = ROOT / "data" / "raw" / "azure_pdm"
PROCESSED = ROOT / "data" / "processed"
ANOMALY = ROOT / "outputs" / "model3" / "predictions.csv"


def create_database() -> None:
    name = database_url().database
    if not name or not re.fullmatch(r"[A-Za-z0-9_]+", name):
        raise ValueError("DB_NAME must contain only letters, numbers, and underscores")
    # Connect to the server without selecting the not-yet-created database.
    admin = create_engine(database_url(database=""), pool_pre_ping=True)
    with admin.begin() as connection:
        connection.execute(text(
            f"CREATE DATABASE IF NOT EXISTS `{name}` "
            "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        ))
    admin.dispose()


def _python_value(value):
    if value is None or pd.isna(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime()
    if hasattr(value, "item"):
        return value.item()
    return value


def _records(frame: pd.DataFrame):
    return [{key: _python_value(value) for key, value in row.items()}
            for row in frame.to_dict("records")]


def _load(model, frame: pd.DataFrame, *, chunk_size: int = 5000) -> int:
    table = model.__table__
    with engine.begin() as connection:
        existing = connection.scalar(select(func.count()).select_from(table))
        if existing:
            print(f"skip {table.name}: already has {existing:,} rows")
            return int(existing)
        total = len(frame)
        for start in range(0, total, chunk_size):
            connection.execute(table.insert(), _records(frame.iloc[start:start + chunk_size]))
        print(f"load {table.name}: {total:,} rows")
        return total


def _csv(path: Path, dates=()) -> pd.DataFrame:
    return pd.read_csv(path, parse_dates=list(dates))


def import_all(include_telemetry: bool = True) -> None:
    machines = _csv(RAW / "PdM_machines.csv").rename(columns={"machineID": "machine_id"})
    suppliers = _csv(OPS / "suppliers.csv")
    parts = _csv(OPS / "part_master.csv")
    costs = _csv(OPS / "costs.csv")
    _load(Machine, machines)
    _load(Supplier, suppliers)
    _load(Part, parts)
    _load(CostPolicy, costs)

    orders = _csv(
        OPS / "purchase_orders.csv",
        ("ordered_at", "expected_receipt_at", "actual_receipt_at"),
    )
    _load(PurchaseOrder, orders)

    lots = _csv(
        OPS / "inventory_lots.csv",
        ("received_at", "use_by_at", "ready_at", "as_of"),
    )
    _load(InventoryLot, lots)

    maintenance = _csv(
        OPS / "maintenance_records.csv",
        ("planned_at", "completed_at", "source_event_at"),
    ).rename(columns={"machineID": "machine_id"})
    _load(MaintenanceRecord, maintenance)

    movements = _csv(OPS / "inventory_movements.csv", ("occurred_at",))
    _load(InventoryMovement, movements)

    errors = _csv(RAW / "PdM_errors.csv", ("datetime",)).rename(
        columns={"machineID": "machine_id", "datetime": "occurred_at", "errorID": "error_code"}
    )
    _load(MachineError, errors)

    failures = _csv(RAW / "PdM_failures.csv", ("datetime",)).rename(
        columns={"machineID": "machine_id", "datetime": "occurred_at", "failure": "component"}
    )
    _load(MachineFailure, failures)

    events = _csv(RAW / "PdM_maint.csv", ("datetime",)).rename(
        columns={"machineID": "machine_id", "datetime": "occurred_at", "comp": "component"}
    )
    _load(MachineMaintenanceEvent, events)

    predictions = _csv(PROCESSED / "predictions.csv", ("as_of",)).rename(
        columns={"machineID": "machine_id"}
    )
    predictions["as_of"] = predictions["as_of"].dt.date
    _load(FailurePrediction, predictions)

    curves = _csv(PROCESSED / "risk_curve.csv", ("as_of",)).rename(columns={
        "machineID": "machine_id",
        "p_at_decision_horizon": "probability_at_horizon",
    })
    curves["as_of"] = curves["as_of"].dt.date
    _load(RiskCurve, curves)

    anomaly = _csv(ANOMALY, ("as_of",)).rename(columns={"machineID": "machine_id"})
    anomaly["is_anomaly"] = anomaly["is_anomaly"].astype(bool)
    _load(AnomalyPrediction, anomaly)

    if include_telemetry:
        telemetry = _csv(RAW / "PdM_telemetry.csv", ("datetime",)).rename(
            columns={"machineID": "machine_id", "datetime": "measured_at"}
        )
        _load(Telemetry, telemetry, chunk_size=10_000)


def main() -> None:
    parser = argparse.ArgumentParser(description="Create and seed the maintenance dashboard MySQL database")
    parser.add_argument("--skip-telemetry", action="store_true", help="Skip the 876,100 telemetry rows")
    args = parser.parse_args()
    create_database()
    Base.metadata.create_all(engine)
    import_all(include_telemetry=not args.skip_telemetry)
    print(f"database ready: {database_url().database}")


if __name__ == "__main__":
    main()
