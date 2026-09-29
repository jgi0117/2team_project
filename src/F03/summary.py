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
    data = data.loc[data.as_of.le(at) & data.horizon_days.eq(horizon_days)
                    & data.model_version.eq(model_version)]
    observed_at = data.as_of.max()
    # 결측인 최신 결과를 오래된 점수로 대체하지 않는다.
    data = data.loc[data.as_of.eq(observed_at)].copy()
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

    plan_columns = ["available_stock", "order_by_at", "response_margin_days"]
    for col in [*plan_columns, "plan_as_of"]:
        data[col] = None
    if maintenance_plan is not None:
        pkeys = ["machineID", "component", "as_of"]
        plan = frame_with_keys(maintenance_plan, pkeys, pkeys)
        if not plan.component.isin(["comp1", "comp2", "comp3", "comp4"]).all():
            raise ValueError("Unknown planning component")
        for col in plan_columns:
            if col not in plan:
                plan[col] = None
        numeric(plan, "available_stock", minimum=0, nullable=True)
        numeric(plan, "response_margin_days", nullable=True)
        plan["order_by_at"] = pd.to_datetime(plan.order_by_at, errors="raise")
        if plan.order_by_at.dt.tz is not None:
            raise ValueError("order_by_at must be timezone-naive")
        plan = (plan.loc[plan.as_of.le(at)].sort_values("as_of")
                .drop_duplicates(["machineID", "component"], keep="last")
                .rename(columns={"as_of": "plan_as_of"}))
        data = data.drop(columns=[*plan_columns, "plan_as_of"]).merge(
            plan[["machineID", "component", "plan_as_of", *plan_columns]],
            on=["machineID", "component"], how="left", validate="one_to_one",
        )

    data["late"] = pd.to_numeric(data.response_margin_days).lt(0)
    data["due"] = pd.to_datetime(data.order_by_at).le(at)
    row = data.sort_values(
        ["late", "due", "failure_probability", "machineID", "component"],
        ascending=[False, False, False, True, True],
    ).iloc[0]
    action = ("조달 일정과 정비 계획을 우선 확인하세요" if row.late else
              "발주 진행 여부를 우선 확인하세요" if row.due else "점검 우선순위를 검토하세요")
    target = f"설비 {int(row.machineID)}의 {row.component}"
    risk = (f"향후 {horizon_days}일 고장 확률 {row.failure_probability:.1%}"
            if row.calibrated else
            f"향후 {horizon_days}일 미보정 고장 위험 점수 {row.failure_probability:.3f}")
    evidence = {}
    for col, label in [("response_margin_days", "계획상 대응 여유"), ("available_stock", "가용재고")]:
        if pd.notna(row[col]):
            unit = "일" if col == "response_margin_days" else "개"
            evidence[col] = f"{label} {float(row[col]):g}{unit}"
    if pd.notna(row.order_by_at):
        evidence["order_by_at"] = f"계획상 발주 마감 {pd.Timestamp(row.order_by_at).isoformat(sep=' ')}"
    if pd.isna(row.plan_as_of):
        evidence["planning_missing"] = "재고·조달 계획 정보 미제공"
    result = summarize(f"{target} {action} ({risk})", evidence,
                       task="고장 위험에 대한 대응 요약: 조달 여유와 발주 마감을 우선 선택",
                       selector=selector, limit=2)
    return {**base, "status": "ok", **result, "selected": {
        "machineID": int(row.machineID), "component": row.component,
        "failure_probability": float(row.failure_probability), "calibrated": bool(row.calibrated),
        "plan_as_of": None if pd.isna(row.plan_as_of) else pd.Timestamp(row.plan_as_of).isoformat(),
        "priority_reason": "negative_margin" if row.late else "order_due" if row.due else "risk_score",
    }}
