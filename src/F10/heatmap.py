"""Use saved Isolation Forest observations without inventing process mappings."""

from pathlib import Path

import numpy as np
import pandas as pd

from src.common.machine_heatmap import ANOMALY_COLORS, machine_grid


DEFAULT_PREDICTIONS = Path(__file__).resolve().parents[2] / "outputs/model3/predictions.csv"


def load_predictions(path=DEFAULT_PREDICTIONS):
    data = pd.read_csv(path, usecols=["machineID", "as_of", "anomaly_score", "threshold", "is_anomaly"], parse_dates=["as_of"])
    if data.empty or data.isna().any().any():
        raise ValueError("Missing IF results")
    if data.as_of.dt.tz is not None or data.duplicated(["machineID", "as_of"]).any():
        raise ValueError("IF results require unique, timezone-naive observation keys")
    for column in ("anomaly_score", "threshold"):
        if not np.isfinite(data[column]).all() or not data[column].between(0, 1).all():
            raise ValueError(f"Invalid IF {column}")
    if not data.is_anomaly.eq(data.anomaly_score.gt(data.threshold).astype(int)).all():
        raise ValueError("IF flags disagree with their saved thresholds")
    return data


def build_heatmap(data, as_of, *, machines=None):
    at = pd.Timestamp(as_of)
    if pd.isna(at) or at.tzinfo is not None:
        raise ValueError("as_of must be a timezone-naive timestamp")
    machines = sorted(data.machineID.unique()) if machines is None else sorted(set(machines))
    eligible = data.loc[data.as_of.le(at)]
    observed_at = eligible.as_of.max()
    # One shared observation time; missing machines must not reuse older scores.
    rows = eligible.loc[eligible.as_of.eq(observed_at)].set_index("machineID").reindex(machines)
    details = {}
    for machine, row in rows.iterrows():
        if pd.isna(row.anomaly_score):
            details[machine] = "해당 시점의 이상탐지 결과 없음"
        else:
            state = "경고" if row.is_anomaly else "경고 없음"
            details[machine] = (f"IF 이상 점수: {row.anomaly_score:.4f}<br>{state} · 경고 기준 > {row.threshold:g}"
                                f"<br>관측: {row.as_of}<br>고장 확률이 아닌 센서 패턴 이상 점수입니다.")
    figure = machine_grid(machines, rows.anomaly_score.to_dict(), details,
                          colors=ANOMALY_COLORS, white_from=0.58)
    thresholds = sorted(rows.threshold.dropna().unique().tolist())
    return figure, dict(machines=len(machines), cells=int(rows.anomaly_score.notna().sum()),
                        as_of=at, observed_at=observed_at, thresholds=thresholds,
                        alerts=int(rows.is_anomaly.fillna(0).sum()))
