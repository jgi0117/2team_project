"""Public F08 service."""

from src.maintenance_planning.service import response_history, supplier_detail


def get_supplier(component: str, as_of=None) -> dict:
    return {"feature": "F08", **supplier_detail(component, as_of)}


def get_history(machine_id: int, as_of=None, limit: int | None = 20):
    return response_history(machine_id, as_of, limit)
