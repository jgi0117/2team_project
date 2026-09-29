"""F03는 예측 점수를 계산하지 않고 기존 예측·계획 결과를 요약한다."""

from __future__ import annotations

import pandas as pd

from src.ai_summary import summarize
from src.ai_summary.validation import boolean_values, frame_with_keys, numeric, timestamp


def build_summary(predictions: pd.DataFrame, as_of, *, horizon_days: int,
                  model_version: str, maintenance_plan: pd.DataFrame | None = None,
                  selector=None) -> dict:
    """같은 기간·모델·예측시점의 후보를 비교한다.

    우선순위: 대응 여유 음수 -> 발주 마감 경과 -> 고장 위험 점수 내림차순.
    동률은 machineID/component 순서로 고정한다. 과거 계획은 마지막 알려진
    행을 사용하고 그 시점을 결과에 보존한다. 미래 예측/계획은 제외한다.
    """
    at = timestamp(as_of)
    if isinstance(horizon_days, bool) or int(horizon_days) != horizon_days or horizon_days <= 0:
        raise ValueError("horizon_days must be a positive integer")
    keys = ["machineID", "component", "as_of", "horizon_days", "model_version"]
    data = frame_with_keys(predictions, keys + ["failure_probability"], keys)
    if not data.component.isin(["comp1", "comp2", "comp3", "comp4"]).all():
        raise ValueError("Unknown component")
    numeric(data, "failure_probability", minimum=0, maximum=1, nullable=True)
    numeric(data, "horizon_days", minimum=1)
    if data.horizon_days.mod(1).ne(0).any():
        raise ValueError("horizon_days must be integral")
    data["calibrated"] = boolean_values(data.calibrated) if "calibrated" in data else False
    eligible = data.loc[data.as_of.le(at) & data.horizon_days.eq(horizon_days)
                        & data.model_version.eq(model_version)].copy()
    observed_at = eligible.as_of.max()
    # 결측인 최신 결과를 오래된 점수로 대체하지 않는다.
    data = eligible.loc[eligible.as_of.eq(observed_at)].copy()
    missing_scores = int(data.failure_probability.isna().sum())
    data = data.dropna(subset=["failure_probability"])
    base = {"feature": "F03", "as_of": at.isoformat(), "horizon_days": int(horizon_days),
            "model_version": model_version, "missing_scores": missing_scores,
            "prediction_as_of": None if pd.isna(observed_at) else observed_at.isoformat()}
    if data.empty:
        return {**base, "status": "no_data", "selected": None,
                **summarize("해당 조건의 고장 예측 결과가 없어 대응 우선순위를 정할 수 없습니다",
                            {}, task="F03")}
    if data.calibrated.nunique() > 1:
        raise ValueError("Cannot rank calibrated probabilities with uncalibrated scores")

    plan_columns = [
        "status", "reason", "available_stock", "recommended_quantity",
        "supply_source", "expected_receipt_at", "target_maintenance_at",
        "ready_at", "order_by_at", "response_margin_days",
    ]
    for col in [*plan_columns, "plan_horizon_days", "plan_as_of"]:
        data[col] = None
    if maintenance_plan is not None:
        pkeys = ["machineID", "component", "as_of"]
        plan = frame_with_keys(maintenance_plan, pkeys, pkeys)
        if not plan.component.isin(["comp1", "comp2", "comp3", "comp4"]).all():
            raise ValueError("Unknown planning component")
        for col in [*plan_columns, "horizon_days"]:
            if col not in plan:
                plan[col] = None
        numeric(plan, "available_stock", minimum=0, nullable=True)
        numeric(plan, "recommended_quantity", minimum=0, nullable=True)
        numeric(plan, "response_margin_days", nullable=True)
        numeric(plan, "horizon_days", minimum=1, nullable=True)
        for col in ["expected_receipt_at", "target_maintenance_at", "ready_at", "order_by_at"]:
            plan[col] = pd.to_datetime(plan[col], errors="raise")
            if plan[col].dt.tz is not None:
                raise ValueError(f"{col} must be timezone-naive")
        plan = (plan.loc[plan.as_of.le(at)].sort_values("as_of")
                .drop_duplicates(["machineID", "component"], keep="last")
                .rename(columns={"as_of": "plan_as_of", "horizon_days": "plan_horizon_days"}))
        data = data.drop(columns=[*plan_columns, "plan_horizon_days", "plan_as_of"]).merge(
            plan[["machineID", "component", "plan_as_of", "plan_horizon_days", *plan_columns]],
            on=["machineID", "component"], how="left", validate="one_to_one",
        )

    # F02가 확정한 조달 상태를 우선 사용한다. order_by_at만으로 다시 판정하면
    # 재고로 대응 가능한 covered 행도 발주 대상으로 잘못 분류될 수 있다.
    inferred_status = pd.Series(None, index=data.index, dtype="object")
    inferred_status.loc[pd.to_numeric(data.response_margin_days).lt(0)] = "late"
    no_stock = pd.to_numeric(data.available_stock).fillna(0).le(0)
    order_due = pd.to_datetime(data.order_by_at).le(at)
    inferred_status.loc[inferred_status.isna() & no_stock & order_due] = "order_due"
    inferred_status.loc[inferred_status.isna() & no_stock & data.plan_as_of.notna()] = "watch"
    inferred_status.loc[inferred_status.isna() & data.available_stock.notna()] = "covered"
    data["plan_status"] = data.status.where(data.status.notna(), inferred_status)
    known_statuses = {"late", "order_due", "watch", "covered"}
    unknown = set(data.plan_status.dropna()) - known_statuses
    if unknown:
        raise ValueError(f"Unknown planning status: {sorted(unknown)}")
    data["action_priority"] = data.plan_status.map(
        {"late": 3, "order_due": 2, "watch": 1, "covered": 0}
    ).fillna(0)
    row = data.sort_values(
        ["action_priority", "failure_probability", "machineID", "component"],
        ascending=[False, False, True, True],
    ).iloc[0]
    plan_status = None if pd.isna(row.plan_status) else str(row.plan_status)
    action_by_status = {
        "late": ("schedule_recovery", "조달 일정과 정비 계획을 즉시 조정하세요"),
        "order_due": ("confirm_order", "부품 발주 진행 여부를 우선 확인하세요"),
        "watch": ("prepare_order", "발주 마감 전 재고와 발주 계획을 확인하세요"),
        "covered": ("inspect_equipment", "설비 상태 점검을 우선 검토하세요"),
        None: ("inspect_equipment", "설비 상태 점검을 우선 검토하세요"),
    }
    action_id, action = action_by_status[plan_status]
    target = f"설비 {int(row.machineID)}의 {row.component}"
    risk = (f"향후 {horizon_days}일 고장 확률 {row.failure_probability:.1%}"
            if row.calibrated else
            f"향후 {horizon_days}일 미보정 고장 위험 점수 {row.failure_probability:.3f}")
    previous = eligible.loc[
        eligible.machineID.eq(row.machineID)
        & eligible.component.eq(row.component)
        & eligible.as_of.eq(observed_at - pd.Timedelta(days=1))
    ]
    previous_score = (None if previous.empty or pd.isna(previous.iloc[0].failure_probability)
                      else float(previous.iloc[0].failure_probability))
    daily_change = (None if previous_score is None else
                    float(row.failure_probability) - previous_score)

    def date_text(value):
        return None if pd.isna(value) else pd.Timestamp(value).strftime("%Y-%m-%d")

    all_evidence = {"risk_score": risk}
    if plan_status == "late":
        margin = abs(float(row.response_margin_days))
        dates = [
            f"준비 예정 {date_text(row.ready_at)}" if pd.notna(row.ready_at) else None,
            f"계획 정비 {date_text(row.target_maintenance_at)}" if pd.notna(row.target_maintenance_at) else None,
        ]
        all_evidence["schedule_delay"] = (
            f"대응 여유 {float(row.response_margin_days):g}일, 계획보다 {margin:g}일 지연" +
            (f" ({' · '.join(part for part in dates if part)})" if any(dates) else "")
        )
    elif plan_status == "order_due":
        stock = float(row.available_stock) if pd.notna(row.available_stock) else 0
        deadline = date_text(row.order_by_at)
        receipt = date_text(row.expected_receipt_at)
        stock_state = (f"현재 재고 {stock:g}개는 상위 위험 설비 대응분으로 배정"
                       if stock > 0 else "가용재고 0개")
        if row.supply_source == "open_order":
            supply_state = (f"기존 발주 입고 예정 {receipt}" if receipt else
                            "기존 발주 진행 상태 확인 필요")
        else:
            supply_state = (f"신규 발주 마감 {deadline}" if deadline else "신규 발주 필요")
        all_evidence["procurement_due"] = f"{stock_state} · {supply_state}"
    elif plan_status == "watch":
        stock = float(row.available_stock) if pd.notna(row.available_stock) else 0
        deadline = date_text(row.order_by_at)
        stock_state = (f"현재 재고 {stock:g}개는 상위 위험 설비 대응분으로 배정"
                       if stock > 0 else "가용재고 0개")
        all_evidence["procurement_watch"] = (
            stock_state +
            (f" · 발주 마감 {deadline}" if deadline else " · 발주 계획 확인 필요")
        )
    elif plan_status == "covered":
        if pd.notna(row.available_stock):
            all_evidence["stock_covered"] = (
                f"현재 가용재고 {float(row.available_stock):g}개로 대응 가능"
            )
        if pd.notna(row.response_margin_days):
            all_evidence["response_margin"] = (
                f"계획 정비일까지 대응 여유 {float(row.response_margin_days):g}일"
            )
    else:
        all_evidence["planning_missing"] = "재고·조달 계획 정보 미제공"

    allowed_by_action = {
        "schedule_recovery": ["risk_score", "schedule_delay"],
        "confirm_order": ["risk_score", "procurement_due"],
        "prepare_order": ["risk_score", "procurement_watch"],
        "inspect_equipment": ["risk_score", "stock_covered", "response_margin", "planning_missing"],
    }
    allowed_ids = allowed_by_action[action_id]
    evidence = {key: all_evidence[key] for key in allowed_ids if key in all_evidence}
    decision_context = {
        "as_of": at.strftime("%Y-%m-%d"),
        "target": {"machine_id": int(row.machineID), "component": str(row.component)},
        "risk": {
            "horizon_days": int(horizon_days),
            "score": float(row.failure_probability),
            "previous_day_score": previous_score,
            "daily_change": daily_change,
            "calibrated": bool(row.calibrated),
        },
        "maintenance_plan": {
            "horizon_days": (None if pd.isna(row.plan_horizon_days)
                             else int(row.plan_horizon_days)),
            "status": plan_status,
            "reason": None if pd.isna(row.reason) else str(row.reason),
            "target_maintenance_at": date_text(row.target_maintenance_at),
            "ready_at": date_text(row.ready_at),
            "response_margin_days": (None if pd.isna(row.response_margin_days)
                                     else float(row.response_margin_days)),
        },
        "inventory": {
            "available_stock": (None if pd.isna(row.available_stock)
                                else float(row.available_stock)),
            "recommended_replenishment_quantity": (
                None if pd.isna(row.recommended_quantity) else float(row.recommended_quantity)
            ),
            "supply_source": None if pd.isna(row.supply_source) else str(row.supply_source),
            "expected_receipt_at": date_text(row.expected_receipt_at),
            "order_by_at": date_text(row.order_by_at),
        },
        "decision": {
            "action_id": action_id,
            "action_text": action,
            "allowed_evidence_ids": list(evidence),
        },
    }
    result = summarize(f"{target} {action}", evidence,
                       task=decision_context, selector=selector, limit=2)
    return {**base, "status": "ok", **result, "selected": {
        "machineID": int(row.machineID), "component": row.component,
        "failure_probability": float(row.failure_probability), "calibrated": bool(row.calibrated),
        "plan_as_of": None if pd.isna(row.plan_as_of) else pd.Timestamp(row.plan_as_of).isoformat(),
        "plan_status": plan_status,
        "action_id": action_id,
        "priority_reason": ("negative_margin" if plan_status == "late" else
                            "order_due" if plan_status == "order_due" else
                            "procurement_watch" if plan_status == "watch" else "risk_score"),
    }, "decision_context": decision_context}
