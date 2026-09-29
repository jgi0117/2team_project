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
    eligible = data.loc[data.as_of.le(at) & data.horizon_days.eq(horizon_days)
                        & data.model_version.eq(model_version)].copy()
    observed_at = eligible.loc[eligible.machineID.eq(machine_id), "as_of"].max()
    peers = eligible.loc[eligible.as_of.eq(observed_at)].dropna(subset=["failure_probability"])
    data = peers.loc[peers.machineID.eq(machine_id)].copy()
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
    peer_scores = peers.groupby("machineID").failure_probability.max()
    percentile = float(peer_scores.le(float(first.failure_probability)).mean())
    risk_rank = int(peer_scores.rank(method="min", ascending=False).loc[int(machine_id)])
    risk_population = int(len(peer_scores))
    sensor_alerts = 0
    if anomaly and anomaly.get("sensors"):
        sensor_alerts = sum(any(row[method] is not None and row[method]["is_anomaly"]
                                for method in ("three_sigma", "iqr"))
                            for row in anomaly["sensors"])
    anomaly_detected = bool(machine_if and machine_if["is_anomaly"])
    if anomaly_detected or percentile >= .95:
        condition_status = "priority"
        lead = f"설비 {machine_id}: 현재 우선 점검이 필요합니다"
    elif sensor_alerts or percentile >= .80:
        condition_status = "watch"
        lead = f"설비 {machine_id}: 현재 상태를 관찰해야 합니다"
    else:
        condition_status = "normal"
        lead = f"설비 {machine_id}: 현재 정상 범위입니다"
    evidence = {}
    evidence["risk_position"] = f"동일 조건 {risk_population}대 중 위험 순위 {risk_rank}위, 대표 {score}"
    if machine_if is not None:
        sensor_detail = if_state
        if anomaly and anomaly.get("sensors"):
            ready = sum(row["status"] == "ok" for row in anomaly["sensors"])
            sensor_detail += f", 센서 {ready}종 중 {sensor_alerts}종에서 통계 이상 신호"
        evidence["sensor_status"] = sensor_detail
    elif anomaly and anomaly.get("sensors"):
        ready = sum(row["status"] == "ok" for row in anomaly["sensors"])
        evidence["sensor_status"] = f"센서 IF 결과 미제공, 센서 {ready}종 중 {sensor_alerts}종에서 통계 이상 신호"
    if condition_status != "normal":
        evidence["risk_component"] = f"위험 상승을 우선 확인할 부품 {first.component}"
    missing = sorted(set(COMPONENTS) - set(data.component))
    if missing:
        evidence["missing_components"] = f"부품 예측 결과 미제공: {', '.join(missing)}"
    result = summarize(lead, evidence, task="설비 현재 상태 진단: 상대 위험과 센서 이상을 근거로 상태 요약",
                       selector=selector, limit=3)
    return {**base, "status": "ok", "highest_component": str(first.component),
            "highest_score": float(first.failure_probability), "calibrated": calibrated,
            "condition_status": condition_status, "risk_percentile": percentile,
            "risk_rank": risk_rank, "risk_population": risk_population,
            "anomaly_detected": anomaly_detected, "sensor_alert_count": int(sensor_alerts),
            "sensor_observed_at": anomaly.get("observed_at") if anomaly else None,
            **result}
