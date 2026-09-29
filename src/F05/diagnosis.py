"""같은 예측기간의 부품 위험과 별도 센서 이상 신호를 근거로 종합한다."""

from __future__ import annotations

import pandas as pd

from src.ai_summary import summarize
from src.ai_summary.validation import boolean_values, frame_with_keys, numeric, timestamp


COMPONENTS = ("comp1", "comp2", "comp3", "comp4")


def build_diagnosis(predictions: pd.DataFrame, machine_id: int, as_of, *,
                    horizon_days: int, model_version: str, anomaly: dict | None = None,
                    selector=None) -> dict:
    """고장 위험은 동일 기간·모델에서 비교하고 IF는 별도 판정으로 덧붙인다."""
    at = timestamp(as_of)
    if isinstance(machine_id, bool) or int(machine_id) != machine_id or machine_id <= 0:
        raise ValueError("machine_id must be a positive integer")
    if isinstance(horizon_days, bool) or int(horizon_days) != horizon_days or horizon_days <= 0:
        raise ValueError("horizon_days must be a positive integer")
    keys = ["machineID", "component", "as_of", "horizon_days", "model_version"]
    data = frame_with_keys(predictions, [*keys, "failure_probability"], keys)
    if not data.component.isin(COMPONENTS).all():
        raise ValueError("Unknown component")
    numeric(data, "failure_probability", minimum=0, maximum=1, nullable=True)
    numeric(data, "horizon_days", minimum=1)
    if data.horizon_days.mod(1).ne(0).any():
        raise ValueError("horizon_days must be integral")
    data["calibrated"] = boolean_values(data.calibrated) if "calibrated" in data else False
    data = data.loc[data.machineID.eq(machine_id) & data.as_of.le(at)
                    & data.horizon_days.eq(horizon_days) & data.model_version.eq(model_version)]
    observed_at = data.as_of.max()
    data = data.loc[data.as_of.eq(observed_at)].dropna(subset=["failure_probability"]).copy()
    base = {"feature": "F05", "machineID": int(machine_id), "as_of": at.isoformat(),
            "horizon_days": int(horizon_days), "model_version": model_version,
            "prediction_as_of": None if pd.isna(observed_at) else observed_at.isoformat()}
    if data.empty:
        return {**base, "status": "no_data", "highest_component": None,
                **summarize(f"설비 {machine_id}: 고장 예측 결과가 없어 종합진단을 제공할 수 없습니다",
                            {}, task="F05")}
    if data.calibrated.nunique() > 1:
        raise ValueError("Cannot compare calibrated probabilities with uncalibrated scores")

    data = data.sort_values(["failure_probability", "component"], ascending=[False, True])
    first = data.iloc[0]
    calibrated = bool(first.calibrated)
    score = (f"고장 확률 {first.failure_probability:.1%}" if calibrated else
             f"미보정 고장 위험 점수 {first.failure_probability:.3f}")
    machine_if = anomaly.get("if") if anomaly else None
    if_state = ("센서 IF 결과 미제공" if machine_if is None else
                "센서 IF 경고" if machine_if["is_anomaly"] else "센서 IF 경고 없음")
    lead = (f"설비 {machine_id}: 향후 {horizon_days}일 기준 최고 위험 부품은 "
            f"{first.component}({score}); {if_state}")
    evidence = {}
    if anomaly and anomaly.get("sensors"):
        alerts = sum(any(row[method] is not None and row[method]["is_anomaly"]
                         for method in ("three_sigma", "iqr")) for row in anomaly["sensors"])
        ready = sum(row["status"] == "ok" for row in anomaly["sensors"])
        evidence["sensor_status"] = f"센서 {ready}종 판정 가능, 그중 {alerts}종에서 통계 이상 신호"
    for _, row in data.iloc[1:].iterrows():
        other = (f"고장 확률 {row.failure_probability:.1%}" if calibrated else
                 f"미보정 위험 점수 {row.failure_probability:.3f}")
        evidence[str(row.component)] = f"{row.component} {other}"
    missing = sorted(set(COMPONENTS) - set(data.component))
    if missing:
        evidence["missing_components"] = f"부품 예측 결과 미제공: {', '.join(missing)}"
    result = summarize(lead, evidence, task="설비 종합진단: 고장 위험과 센서 이상을 별도 근거로 요약",
                       selector=selector, limit=3)
    return {**base, "status": "ok", "highest_component": str(first.component),
            "highest_score": float(first.failure_probability), "calibrated": calibrated,
            "sensor_observed_at": anomaly.get("observed_at") if anomaly else None,
            **result}
