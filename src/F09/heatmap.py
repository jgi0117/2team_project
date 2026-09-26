"""Validated prediction reader and standalone F09 Plotly visualization."""

from pathlib import Path

import numpy as np
import pandas as pd
from src.common.machine_heatmap import machine_grid


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PREDICTIONS = ROOT / "data/processed/predictions.csv"
COMPONENTS = ["comp1", "comp2", "comp3", "comp4"]


def load_predictions(path=DEFAULT_PREDICTIONS):
    data = pd.read_csv(path)
    keys = ["machineID", "component", "as_of", "horizon_days", "model_version"]
    required = set(keys + ["failure_probability"])
    if required - set(data):
        raise ValueError(f"Missing prediction columns: {sorted(required - set(data))}")
    if data.empty or data[keys].isna().any().any():
        raise ValueError("Predictions are empty or contain missing keys")
    dates = pd.to_datetime(data.as_of, errors="raise")
    if dates.dt.tz is not None:
        raise ValueError("Prediction dates must be timezone-naive")
    data["as_of"] = dates.dt.strftime("%Y-%m-%d")
    for column in ("machineID", "horizon_days"):
        values = pd.to_numeric(data[column], errors="raise")
        if (~np.isfinite(values) | values.le(0) | values.mod(1).ne(0)).any():
            raise ValueError(f"{column} must contain positive integers")
        data[column] = values.astype(int)
    if not data.component.isin(COMPONENTS).all() or data.duplicated(keys).any():
        raise ValueError("Unknown components or duplicate prediction keys")
    scores = pd.to_numeric(data.failure_probability, errors="raise")
    if ((scores.notna()) & (~np.isfinite(scores) | ~scores.between(0, 1))).any():
        raise ValueError("Prediction scores must be between 0 and 1")
    data["failure_probability"] = scores
    if "calibrated" in data:
        flags = data.calibrated.astype(str).str.lower()
        if not flags.isin(["true", "false", "1", "0"]).all():
            raise ValueError("Invalid calibrated flag")
        data["calibrated"] = flags.isin(["true", "1"])
    else:
        data["calibrated"] = False
    if "source" not in data:
        data["source"] = "unknown"
    return data


def machine_ids():
    return sorted(pd.read_csv(ROOT / "data/raw/azure_pdm/PdM_machines.csv").machineID.astype(int).tolist())


def build_heatmap(data, as_of, horizon_days, model_version, *, machines=None):
    """One tile per machine: maximum component score, not machine probability."""
    machines = sorted(data.machineID.unique().tolist()) if machines is None else sorted(set(machines))
    rows = data.loc[data.as_of.eq(as_of) & data.horizon_days.eq(horizon_days)
                    & data.model_version.eq(model_version)
                    & data.machineID.isin(machines)]
    matrix = rows.pivot(index="machineID", columns="component", values="failure_probability").reindex(index=machines, columns=COMPONENTS)
    calibrated = not rows.empty and bool(rows.calibrated.all())
    complete = matrix.notna().all(axis=1)
    scores = matrix.max(axis=1).where(complete)
    metadata = dict(machines=len(matrix), cells=int(scores.notna().sum()),
                    possible_cells=len(matrix), calibrated=calibrated,
                    component_cells=int(matrix.notna().sum().sum()), aggregation="max_component_score",
                    sources=", ".join(sorted(rows.source.astype(str).unique())))
    details = {}
    for machine, values in matrix.iterrows():
        if not complete.loc[machine]:
            missing = ", ".join(values.index[values.isna()])
            details[machine] = f"부품 결과 미제공: {missing}<br>설비 점수 미확정"
            continue
        details[machine] = f"설비 위험 점수: {scores.loc[machine]:.4f}<br>최대 위험 부품: {values.idxmax()}"
        details[machine] += f"<br>{as_of} 기준 · 향후 {int(horizon_days)}일"
        details[machine] += "<br>" + " · ".join(f"{part}: {score:.3f}" for part, score in values.items())
        details[machine] += "<br>부품 점수의 최댓값이며 설비 전체의 고장 확률은 아닙니다."
    figure = machine_grid(machines, scores.to_dict(), details)
    return figure, metadata
