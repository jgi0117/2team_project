"""IF 결과와 과거 센서 기준선의 3-Sigma/IQR 이탈을 시간별로 계산한다."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.ai_summary.validation import boolean_values, frame_with_keys, numeric, timestamp


SENSORS = ("volt", "rotate", "pressure", "vibration")


def _sensor_status(history: pd.DataFrame, observation: pd.Series | None,
                   window_hours: int, complete: bool) -> list[dict]:
    """시점별 네 센서 판정. 현재값과 미래 관측은 기준선에 포함하지 않는다."""
    results = []
    for sensor in SENSORS:
        value = None if observation is None or pd.isna(observation[sensor]) else float(observation[sensor])
        values = history[sensor].dropna()
        entry = {"sensor": sensor, "value": value, "baseline_count": len(values),
                 "three_sigma": None, "iqr": None, "status": "insufficient_history"}
        if value is None:
            entry["status"] = "missing_current"
        elif complete and len(values) == window_hours:
            mean, std = float(values.mean()), float(values.std(ddof=0))
            q1, q3 = float(values.quantile(.25)), float(values.quantile(.75))
            spread = q3 - q1
            entry.update(mean=mean, std=std, q1=q1, q3=q3, status="ok")
            for method, low, high in [("three_sigma", mean - 3 * std, mean + 3 * std),
                                      ("iqr", q1 - 1.5 * spread, q3 + 1.5 * spread)]:
                entry[method] = {"lower": low, "upper": high, "is_anomaly": value < low or value > high}
            entry["constant_baseline"] = std == 0
            entry["zero_iqr"] = spread == 0
        results.append(entry)
    return results


def analyze_equipment(telemetry: pd.DataFrame, machine_id: int, as_of, *,
                      if_predictions: pd.DataFrame | None = None,
                      window_hours: int = 72) -> dict:
    """마지막 window_hours+1개 시점의 IF·3-Sigma·IQR 추이를 반환한다.

    각 시점 t는 해당 시점 이전 [t-window, t)의 센서 관측만 기준선으로 쓴다.
    시간별 관측이나 센서값/IF 결과가 없으면 그 시점은 미확정으로 남긴다.
    IF는 설비 전체 센서 특징의 점수로서 특정 센서의 원인 판정이 아니다.
    """
    at = timestamp(as_of)
    if isinstance(machine_id, bool) or int(machine_id) != machine_id or machine_id <= 0:
        raise ValueError("machine_id must be a positive integer")
    if isinstance(window_hours, bool) or int(window_hours) != window_hours or window_hours < 2:
        raise ValueError("window_hours must be an integer >= 2")
    raw = telemetry.rename(columns={"datetime": "as_of"}) if "datetime" in telemetry else telemetry
    keys = ["machineID", "as_of"]
    data = frame_with_keys(raw, [*keys, *SENSORS], keys)
    for sensor in SENSORS:
        numeric(data, sensor, nullable=True)
    data = data.loc[data.machineID.eq(machine_id) & data.as_of.le(at)].sort_values("as_of")
    base = {"feature": "F06", "machineID": int(machine_id), "as_of": at.isoformat(),
            "window_hours": int(window_hours)}
    if data.empty:
        return {**base, "status": "no_data", "observed_at": None, "sensors": [], "if": None,
                "trend": [], "timeline": []}
    current = data.iloc[-1]
    observed = current.as_of
    start = observed - pd.Timedelta(hours=window_hours)
    scores_by_time = {}
    if if_predictions is not None:
        scores = frame_with_keys(if_predictions, [*keys, "anomaly_score", "threshold", "is_anomaly"], keys)
        numeric(scores, "anomaly_score")
        numeric(scores, "threshold")
        flags = boolean_values(scores.is_anomaly)
        if not flags.eq(scores.anomaly_score.gt(scores.threshold)).all():
            raise ValueError("IF flags disagree with saved thresholds")
        scores_by_time = {row.as_of: row for _, row in scores.loc[
            scores.machineID.eq(machine_id) & scores.as_of.ge(start) & scores.as_of.le(observed)
        ].iterrows()}

    indexed = data.set_index("as_of")
    timeline = []
    sensors, if_result = [], None
    for tick in pd.date_range(start, observed, freq="h"):
        observation = indexed.loc[tick] if tick in indexed.index else None
        baseline_start = tick - pd.Timedelta(hours=window_hours)
        history = data.loc[data.as_of.ge(baseline_start) & data.as_of.lt(tick)]
        expected = pd.date_range(baseline_start, tick, freq="h", inclusive="left")
        complete = pd.DatetimeIndex(history.as_of).equals(expected)
        entries = _sensor_status(history, observation, window_hours, complete)
        score = scores_by_time.get(tick)
        machine_if = None
        if observation is not None and score is not None:
            # 저장된 센서도 있다면 다른 원본으로 계산된 IF 결과 혼용을 차단한다.
            for sensor in SENSORS:
                if sensor in score and pd.notna(score[sensor]) and pd.notna(observation[sensor]):
                    if not np.isclose(float(score[sensor]), float(observation[sensor]), rtol=1e-5):
                        raise ValueError("IF sensors differ from the selected telemetry")
            machine_if = {"anomaly_score": float(score.anomaly_score),
                          "threshold": float(score.threshold),
                          "is_anomaly": bool(score.anomaly_score > score.threshold),
                          "observed_at": tick.isoformat()}
        timeline.append({"as_of": tick.isoformat(), "sensors": {item["sensor"]: item for item in entries},
                         "if": machine_if})
        if tick == observed:
            sensors, if_result = entries, machine_if

    ready = sum(s["status"] == "ok" for s in sensors)
    trend = data.loc[data.as_of.ge(start), ["as_of", *SENSORS]].copy()
    trend["as_of"] = trend.as_of.map(lambda t: t.isoformat())
    return {**base, "status": "ok" if ready == 4 and if_result is not None else "partial",
            "observed_at": observed.isoformat(), "observation_age_hours": (at - observed).total_seconds() / 3600,
            "baseline_start": start.isoformat(), "sensors": sensors, "if": if_result,
            "timeline": timeline,
            "trend": trend.astype(object).where(trend.notna(), None).to_dict("records"),
            "interpretation": "센서 패턴의 이상 신호이며 고장 확률·고장 원인을 뜻하지 않습니다"}
