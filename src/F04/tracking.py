"""Public F04 service."""

from src.maintenance_planning.service import dashboard_overview


def build_tracking(as_of=None) -> dict:
    overview = dashboard_overview(as_of)
    return {
        "feature": "F04",
        "as_of": overview["as_of"],
        "model_version": overview["model_version"],
        "prediction_rows": overview["kpis"]["prediction_rows"],
        "history": overview["history"],
        "recent_actions": overview["recent_actions"],
    }
