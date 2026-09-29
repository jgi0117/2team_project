"""Public F07 service."""

from src.maintenance_planning.service import cost_analysis


def analyze_order(machine_id: int, component: str, as_of=None) -> dict:
    result = cost_analysis(machine_id, component, as_of)
    return {"feature": "F07", **result}
