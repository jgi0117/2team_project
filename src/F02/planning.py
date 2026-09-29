"""Public F02 service."""

from src.maintenance_planning.service import build_maintenance_plan, dashboard_overview


def build_plan(as_of=None):
    return build_maintenance_plan(as_of)


def build_procurement(as_of=None) -> dict:
    overview = dashboard_overview(as_of)
    return {
        "feature": "F02", "as_of": overview["as_of"], "plan": overview["plan"],
        "top5": overview["top5"], "priority_equipment": overview["priority_equipment"],
        "replacement_due_rows": overview["replacement_due_rows"],
        "order_due_rows": overview["order_due_rows"],
        "part_risk": overview["part_risk"], "kpis": overview["kpis"],
        "order_schedule": overview["order_schedule"],
        "action_schedule": overview["action_schedule"],
        "schedule_start": overview["schedule_start"],
        "schedule_end": overview["schedule_end"],
    }
