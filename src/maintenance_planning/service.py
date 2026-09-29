"""Feature services for F01, F02, F04, F07, and F08."""

from __future__ import annotations

from functools import lru_cache
import math

import pandas as pd

from src.common.paths import OPS, PROCESSED, ROOT, WORK
from src.common.labels import load_events
from src.database.readers import read_operation, read_table
from .operations_snapshot import snapshot


@lru_cache(maxsize=None)
def _csv(path: str) -> pd.DataFrame:
    return pd.read_csv(path)


@lru_cache(maxsize=None)
def _parquet(path: str) -> pd.DataFrame:
    return pd.read_parquet(path)


def _predictions() -> pd.DataFrame:
    stored = read_table("failure_predictions")
    data = (stored if stored is not None else _csv(str(PROCESSED / "predictions.csv"))).copy()
    data["as_of"] = pd.to_datetime(data["as_of"])
    data["calibrated"] = data.get("calibrated", False).astype(str).str.lower().eq("true")
    return data


def _ops(name: str) -> pd.DataFrame:
    stored = read_operation(name)
    return (stored if stored is not None else _csv(str(OPS / name))).copy()


def _latest_predictions(as_of=None) -> tuple[pd.DataFrame, pd.Timestamp, str]:
    data = _predictions()
    cutoff = data.as_of.max() if as_of is None else pd.Timestamp(as_of)
    eligible = data.loc[data.as_of.le(cutoff)]
    if eligible.empty:
        raise ValueError("No predictions at or before as_of")
    observed = eligible.as_of.max()
    current = eligible.loc[eligible.as_of.eq(observed)]
    version = sorted(current.model_version.dropna().unique())[-1]
    return current.loc[current.model_version.eq(version)].copy(), observed, version


def _inventory(as_of) -> tuple[dict[str, int], dict[str, pd.Timestamp]]:
    state = snapshot(as_of)
    lots = pd.DataFrame(state["inventory_lots"])
    stock = lots.groupby("component").quantity_available.sum().astype(int).to_dict()
    orders = pd.DataFrame(state["purchase_orders"])
    open_orders = orders.loc[orders.status_as_of.eq("open")]
    receipt = (open_orders.groupby("component").expected_receipt_at.min().apply(pd.Timestamp).to_dict()
               if not open_orders.empty else {})
    return stock, receipt


@lru_cache(maxsize=16)
def build_maintenance_plan(as_of=None) -> pd.DataFrame:
    """Create F02 decisions using only predictions and operating state known then."""
    predictions, observed, _ = _latest_predictions(as_of)
    parts = _ops("part_master.csv").set_index("component")
    stock, receipts = _inventory(observed)
    selected = []
    for component, meta in parts.iterrows():
        horizon = int(meta.lead_time_days + meta.preparation_days)
        candidates = predictions.loc[predictions.component.eq(component)]
        exact = candidates.loc[candidates.horizon_days.eq(horizon)]
        if exact.empty:
            nearest = (candidates.horizon_days.astype(int) - horizon).abs().min()
            exact = candidates.loc[(candidates.horizon_days.astype(int) - horizon).abs().eq(nearest)]
        selected.append(exact)
    rows = pd.concat(selected, ignore_index=True)
    rows = rows.sort_values(["component", "failure_probability"], ascending=[True, False])

    allocated = {component: int(stock.get(component, 0)) for component in parts.index}
    result = []
    for row in rows.itertuples(index=False):
        meta = parts.loc[row.component]
        target = observed + pd.Timedelta(days=int(row.horizon_days))
        has_stock = allocated[row.component] > 0
        if has_stock:
            allocated[row.component] -= 1
            ready_at = observed
            source = "available_stock"
        elif row.component in receipts:
            receipt_at = max(observed, pd.Timestamp(receipts[row.component]))
            ready_at = receipt_at + pd.Timedelta(days=int(meta.preparation_days))
            source = "open_order"
        else:
            ready_at = observed + pd.Timedelta(days=int(meta.lead_time_days + meta.preparation_days))
            source = "new_order"
        margin = int((target.normalize() - ready_at.normalize()).days)
        order_by = target - pd.Timedelta(days=int(meta.lead_time_days + meta.preparation_days))
        status = "late" if margin < 0 else "order_due" if not has_stock and order_by <= observed else "watch" if not has_stock else "covered"
        reason = {
            "late": "준비 완료 예정일이 계획 정비일보다 늦음",
            "order_due": "가용재고가 없어 발주 마감 도래",
            "watch": "가용재고 부족, 발주 마감 전",
            "covered": "현재 가용재고로 대응 가능",
        }[status]
        result.append({
            "machineID": int(row.machineID), "component": row.component,
            "as_of": observed, "horizon_days": int(row.horizon_days),
            "risk_score": float(row.failure_probability), "calibrated": bool(row.calibrated),
            "priority": status, "target_maintenance_at": target,
            "available_stock": int(stock.get(row.component, 0)),
            "expected_receipt_at": receipts.get(row.component), "order_by_at": order_by,
            "ready_at": ready_at, "response_margin_days": margin, "supply_source": source,
            "recommended_quantity": max(0, int(meta.target_stock) - int(stock.get(row.component, 0))),
            "status": status, "reason": reason,
        })
    return pd.DataFrame(result).sort_values(
        ["response_margin_days", "risk_score"], ascending=[True, False]
    ).reset_index(drop=True)


@lru_cache(maxsize=16)
def dashboard_overview(as_of=None) -> dict:
    """Build the F01/F02/F04 main dashboard payload."""
    current, observed, version = _latest_predictions(as_of)
    data = _predictions()
    previous_at = observed - pd.Timedelta(days=1)
    plan = build_maintenance_plan(observed)
    # 모든 설비를 교체 수요로 세면 부품마다 100대가 위험 설비가 된다. 부품별
    # 위험 상위 5%만 단기 확인 대상으로 삼아 현재 재고와 비교한다.
    risk_groups = []
    for _, rows in plan.groupby("component", sort=True):
        count = max(1, math.ceil(len(rows) * .05))
        risk_groups.append(rows.nlargest(count, "risk_score"))
    risk_candidates = pd.concat(risk_groups, ignore_index=True)
    status_rank = {"late": 3, "order_due": 2, "watch": 1, "covered": 0}
    risk_candidates["action_rank"] = risk_candidates.status.map(status_rank).fillna(0)
    priority_equipment = (risk_candidates
                          .sort_values(["action_rank", "risk_score"], ascending=[False, False])
                          .head(10).drop(columns="action_rank"))
    top = priority_equipment.head(5)
    cost_rows = (risk_candidates.loc[risk_candidates.status.ne("covered")]
                 .sort_values(["action_rank", "risk_score"], ascending=[False, False])
                 .head(5).drop(columns="action_rank"))
    scenario_costs = _priority_cost_summary(cost_rows)
    part_rows = []
    for component, rows in plan.groupby("component", sort=True):
        candidates = risk_candidates.loc[risk_candidates.component.eq(component)]
        stock = int(rows.available_stock.iloc[0])
        risk_count = int(candidates.machineID.nunique())
        part_rows.append({
            "component": component,
            "available_stock": stock,
            "risk_machines": risk_count,
            "demand_shortage": max(0, risk_count - stock),
            "replenishment_qty": int(rows.recommended_quantity.iloc[0]),
            "covered_machines": int(candidates.status.eq("covered").sum()),
            "urgent": int(candidates.status.isin(["late", "order_due"]).sum()),
            "max_risk": float(candidates.risk_score.max()),
        })
    part_risk = pd.DataFrame(part_rows).sort_values(
        ["urgent", "demand_shortage", "max_risk"], ascending=False
    ).reset_index(drop=True)
    history = _response_metrics(observed)
    action_rows = _ops("maintenance_records.csv")
    action_rows["planned_at"] = pd.to_datetime(action_rows["planned_at"])
    action_rows["completed_at"] = pd.to_datetime(action_rows["completed_at"])
    recent_actions = (action_rows.loc[action_rows.planned_at.le(observed)]
                      .sort_values("planned_at", ascending=False).head(5))
    anomaly_path = ROOT / "outputs" / "model3" / "predictions.csv"
    anomaly_map = pd.DataFrame()
    if anomaly_path.is_file():
        anomalies = _csv(str(anomaly_path)).copy()
        anomalies["as_of"] = pd.to_datetime(anomalies["as_of"])
        known = anomalies.loc[anomalies.as_of.le(observed)]
        if not known.empty:
            anomaly_at = known.as_of.max()
            anomaly_map = known.loc[known.as_of.eq(anomaly_at)].sort_values("machineID")
    calibrated = bool(current.calibrated.all())
    machine_risk = current.groupby("machineID").failure_probability.max()
    if calibrated:
        predicted_warning = set(machine_risk.loc[machine_risk.ge(.5)].index.astype(int))
        warning_policy = "고장 확률 50% 이상 또는 IF 경고"
    else:
        risk_cutoff = float(machine_risk.quantile(.95))
        predicted_warning = set(machine_risk.loc[machine_risk.ge(risk_cutoff)].index.astype(int))
        warning_policy = "미보정 위험 점수 상위 5% 또는 IF 경고"
    if anomaly_map.empty:
        anomaly_warning = set()
    else:
        flags = anomaly_map.is_anomaly.astype(str).str.lower().isin(["1", "true"])
        anomaly_warning = set(anomaly_map.loc[flags, "machineID"].astype(int))
    warning_machines = predicted_warning | anomaly_warning

    # 기준일이 속한 한 달에 실제로 확인할 항목을 달력에 싣는다.
    schedule_start = observed.normalize().replace(day=1)
    schedule_end = schedule_start + pd.offsets.MonthEnd(0)
    week_end = observed.normalize() - pd.Timedelta(days=observed.weekday()) + pd.Timedelta(days=6)
    schedule: dict[pd.Timestamp, list[str]] = {}

    def add_schedule(date, label):
        day = pd.Timestamp(date).normalize()
        if schedule_start <= day <= schedule_end:
            schedule.setdefault(day, []).append(label)

    if warning_machines:
        add_schedule(observed, f"위험 설비 확인 {len(warning_machines)}대")
    procurement = risk_candidates.loc[
        risk_candidates.status.isin(["late", "order_due"])
    ]
    if not procurement.empty:
        add_schedule(observed, f"발주 확인 {len(procurement)}건")
    receipts = (plan.loc[plan.expected_receipt_at.notna(), ["component", "expected_receipt_at"]]
                .drop_duplicates())
    for receipt_at, rows in receipts.groupby("expected_receipt_at"):
        add_schedule(receipt_at, f"입고 확인 {rows.component.nunique()}종")
    maintenance = risk_candidates.loc[
        risk_candidates.target_maintenance_at.between(
            schedule_start, schedule_end, inclusive="both"
        )
    ]
    for maintenance_at, rows in maintenance.groupby("target_maintenance_at"):
        add_schedule(maintenance_at, f"정비 예정 {rows.machineID.nunique()}대")
    action_schedule = pd.DataFrame([
        {"date": date, "label": " · ".join(labels), "items": len(labels)}
        for date, labels in sorted(schedule.items())
    ], columns=["date", "label", "items"])
    replacement_due_rows = (risk_candidates.loc[
        risk_candidates.target_maintenance_at.le(observed + pd.Timedelta(days=14))
    ].sort_values(["target_maintenance_at", "risk_score"], ascending=[True, False]))
    order_due_rows = (risk_candidates.loc[
        risk_candidates.status.isin(["late", "order_due"])
        & risk_candidates.order_by_at.le(week_end)
    ].sort_values(["order_by_at", "risk_score"], ascending=[True, False]))
    daily_path = WORK / "pred_ml.parquet"
    surges = []
    if daily_path.is_file():
        daily = _parquet(str(daily_path)).copy()
        daily["as_of"] = pd.to_datetime(daily["as_of"])
        daily = daily.loc[daily.horizon_days.eq(7)]
        daily_current = daily.loc[daily.as_of.eq(observed)].copy()
        daily_previous = daily.loc[daily.as_of.eq(previous_at)].copy()
        if not daily_current.empty and not daily_previous.empty:
            current_machine = (daily_current.groupby("machineID").failure_probability.max()
                               .rename("failure_probability"))
            previous_machine = (daily_previous.groupby("machineID").failure_probability.max()
                                .rename("failure_probability_previous"))
            daily_cutoff = float(current_machine.quantile(.95))
            dangerous = set(current_machine.loc[current_machine.ge(daily_cutoff)].index.astype(int))
            changes = pd.concat([current_machine, previous_machine], axis=1).dropna().reset_index()
            changes["change"] = changes.failure_probability - changes.failure_probability_previous
            changes["horizon_days"] = 7
            changes["calibrated"] = False
            surge_frame = (changes.loc[changes.machineID.isin(dangerous) & changes.change.gt(0)]
                           .sort_values("change", ascending=False)
                           .drop_duplicates("machineID").head(3))
            surges = surge_frame[
                ["machineID", "horizon_days", "failure_probability", "change", "calibrated"]
            ].to_dict("records")
    return {
        "as_of": observed, "previous_as_of": previous_at, "model_version": version,
        "calibrated": calibrated, "surges": surges, "plan": plan, "top5": top,
        "priority_equipment": priority_equipment,
        "replacement_due_rows": replacement_due_rows,
        "order_due_rows": order_due_rows,
        "part_risk": part_risk, "history": history, "recent_actions": recent_actions,
        "order_schedule": action_schedule, "action_schedule": action_schedule,
        "schedule_start": schedule_start, "schedule_end": schedule_end,
        "anomaly_map": anomaly_map, "warning_policy": warning_policy,
        "warning_machine_ids": sorted(warning_machines),
        "kpis": {
            "warning_machines": int(len(warning_machines)),
            "replacement_due": int(len(replacement_due_rows)),
            "late_items": int(risk_candidates.status.eq("late").sum()),
            "order_due": int(len(order_due_rows)),
            "covered": int(risk_candidates.status.eq("covered").sum()),
            "prediction_rows": int(len(current)),
            **scenario_costs,
        },
    }


def _priority_cost_summary(rows: pd.DataFrame) -> dict:
    """Compare today versus a 14-day delay for the five highest-priority rows."""
    if rows.empty:
        return {"unacted_loss": 0, "action_savings": 0, "cost_scope": 0}
    parts = _ops("part_master.csv").set_index("component")
    costs = _ops("costs.csv")
    total_now = 0.0
    total_delayed = 0.0
    for row in rows.itertuples(index=False):
        meta = parts.loc[row.component]
        unit = (costs.loc[costs.component.eq(row.component)]
                .set_index("cost_type").amount.astype(float).to_dict())
        quantity = max(1, int(row.recommended_quantity))
        scenario = []
        for delay in (0, 14):
            ready = row.as_of + pd.Timedelta(
                days=delay + int(meta.lead_time_days + meta.preparation_days)
            )
            gap = int((row.target_maintenance_at.normalize() - ready.normalize()).days)
            holding = max(0, gap) * unit["holding"] * quantity
            late = max(0, -gap)
            disruption = 0 if not late else (
                unit["emergency_labor"] + unit["expedite_surcharge"] * quantity
                + unit["downtime"] * late
            )
            scenario.append(unit["purchase"] * quantity + unit["order_admin"] + holding + disruption)
        total_now += scenario[0]
        total_delayed += scenario[1]
    return {
        "unacted_loss": round(total_delayed),
        "action_savings": round(max(0, total_delayed - total_now)),
        "cost_scope": int(len(rows)),
    }


def _response_metrics(as_of) -> pd.DataFrame:
    events = load_events()
    cutoff = pd.Timestamp(as_of).normalize()
    year_start = pd.Timestamp(year=cutoff.year, month=1, day=1)
    events = events.loc[events.date.between(year_start, cutoff, inclusive="both")].copy()
    events["period"] = events.date.dt.to_period("M").astype(str)
    events["preventive_response"] = events.is_emergency.eq(0)
    return (events.groupby("period").agg(requests=("is_emergency", "size"),
                                          responded=("preventive_response", "sum"))
            .assign(response_rate=lambda x: x.responded / x.requests)
            .reset_index())


def cost_analysis(machine_id: int, component: str, as_of=None) -> dict:
    plan = build_maintenance_plan(as_of)
    selected = plan.loc[plan.machineID.eq(int(machine_id)) & plan.component.eq(component)]
    if selected.empty:
        raise ValueError("No plan for machine/component")
    row = selected.iloc[0]
    parts = _ops("part_master.csv").set_index("component")
    costs = _ops("costs.csv")
    unit = costs.loc[costs.component.eq(component)].set_index("cost_type").amount.astype(float).to_dict()
    meta = parts.loc[component]
    quantity = max(1, int(row.recommended_quantity))
    curve = []
    max_delay = max(42, int(row.horizon_days) + 14)
    for delay in range(max_delay + 1):
        ready = row.as_of + pd.Timedelta(days=delay + int(meta.lead_time_days + meta.preparation_days))
        gap = int((row.target_maintenance_at.normalize() - ready.normalize()).days)
        holding = max(0, gap) * unit["holding"] * quantity
        late = max(0, -gap)
        disruption = 0 if not late else unit["emergency_labor"] + unit["expedite_surcharge"] * quantity + unit["downtime"] * late
        total = unit["purchase"] * quantity + unit["order_admin"] + holding + disruption
        curve.append({"delay_days": delay, "total_cost": round(total), "ready_at": ready, "late_days": late})
    optimum = min(curve, key=lambda item: item["total_cost"])
    scenarios = {day: next(item for item in curve if item["delay_days"] == day) for day in (0, 7, 14)}
    return {"plan": row.to_dict(), "curve": curve, "optimum": optimum,
            "scenarios": scenarios, "currency": "KRW", "quantity": quantity}


def supplier_detail(component: str, as_of=None) -> dict:
    _, observed, _ = _latest_predictions(as_of)
    parts = _ops("part_master.csv").set_index("component")
    suppliers = _ops("suppliers.csv").set_index("supplier_id")
    stock, _ = _inventory(observed)
    meta = parts.loc[component]
    supplier = suppliers.loc[meta.supplier_id]
    return {"component": component, "part_name": meta.part_name,
            "supplier_name": supplier.supplier_name,
            "contact_department": supplier.contact_department,
            "contact_phone": supplier.contact_phone, "contact_email": supplier.contact_email,
            "available_stock": int(stock.get(component, 0)),
            "lead_time_days": int(meta.lead_time_days), "target_stock": int(meta.target_stock)}


def response_history(machine_id: int, as_of=None, limit: int | None = 20) -> pd.DataFrame:
    _, observed, _ = _latest_predictions(as_of)
    records = _ops("maintenance_records.csv")
    for col in ("planned_at", "completed_at", "source_event_at"):
        records[col] = pd.to_datetime(records[col])
    rows = records.loc[records.machineID.eq(int(machine_id)) & records.planned_at.le(observed)].copy()
    rows["delay_days"] = (rows.completed_at - rows.planned_at).dt.total_seconds().div(86400)
    rows = rows.sort_values("planned_at", ascending=False)
    if limit is not None:
        rows = rows.head(limit)
    return rows.reset_index(drop=True)
