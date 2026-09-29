"""Public F01 service."""

from __future__ import annotations

from src.maintenance_planning.service import dashboard_overview


def build_detection(as_of=None) -> dict:
    overview = dashboard_overview(as_of)
    return {
        "feature": "F01",
        "as_of": overview["as_of"],
        "previous_as_of": overview["previous_as_of"],
        "model_version": overview["model_version"],
        "calibrated": overview["calibrated"],
        "surges": overview["surges"],
        "anomaly_map": overview["anomaly_map"],
        "warning_policy": overview["warning_policy"],
        "warning_machine_ids": overview["warning_machine_ids"],
        "warning_machines": overview["kpis"]["warning_machines"],
    }
