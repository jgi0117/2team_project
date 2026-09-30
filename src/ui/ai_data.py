"""F03/F05는 Qwen을 공유하고 F06은 수치 분석만 수행한다."""

from __future__ import annotations

from functools import lru_cache
from threading import Lock

import pandas as pd
from src.common.data_source import read_csv

from src.F03 import build_summary
from src.F05 import build_diagnosis
from src.F06 import analyze_equipment
from src.ai_summary import QwenSelector
from src.common.paths import PROCESSED, RAW_PDM, ROOT
from src.F02 import build_plan
from src.ui.config import UI_AS_OF


_SELECTOR = QwenSelector()
_MODEL_LOCK = Lock()
_IF_RESULTS = ROOT / "outputs" / "model3" / "predictions.csv"


@lru_cache(maxsize=1)
def _failure_predictions():
    return read_csv(PROCESSED / "predictions.csv")


@lru_cache(maxsize=1)
def _telemetry():
    return read_csv(RAW_PDM / "PdM_telemetry.csv", parse_dates=["datetime"])


@lru_cache(maxsize=1)
def _if_predictions():
    return read_csv(_IF_RESULTS) if _IF_RESULTS.is_file() else None


@lru_cache(maxsize=16)
def f03_summary(as_of: str = UI_AS_OF):
    predictions = _failure_predictions()
    eligible = predictions.loc[predictions.as_of.le(as_of or UI_AS_OF)]
    if eligible.empty:
        raise ValueError("No failure predictions at or before the UI cutoff")
    latest = eligible.as_of.max()
    current = predictions.loc[predictions.as_of.eq(latest)]
    version = sorted(current.model_version.dropna().unique())[-1]
    horizons = sorted(current.loc[current.model_version.eq(version), "horizon_days"].unique())
    horizon = 7 if 7 in horizons else int(horizons[0])
    plan = build_plan(latest)
    with _MODEL_LOCK:
        return build_summary(
            predictions, latest, horizon_days=horizon, model_version=version,
            maintenance_plan=plan, selector=_SELECTOR,
        )


@lru_cache(maxsize=128)
def f06_analysis(machine_id: int, as_of: str):
    telemetry = _telemetry()
    machine_telemetry = telemetry.loc[telemetry.machineID.eq(machine_id)]
    scores = _if_predictions()
    machine_scores = None if scores is None else scores.loc[scores.machineID.eq(machine_id)]
    return analyze_equipment(
        machine_telemetry, machine_id, as_of, if_predictions=machine_scores,
    )


@lru_cache(maxsize=128)
def f05_diagnosis(machine_id: int, as_of: str):
    predictions = _failure_predictions()
    current = predictions.loc[predictions.machineID.eq(machine_id)
                              & predictions.as_of.le(as_of)]
    if current.empty:
        version, horizon = "fp_v1", 28
    else:
        latest = current.as_of.max()
        current = current.loc[current.as_of.eq(latest)]
        version = sorted(current.model_version.dropna().unique())[-1]
        horizons = sorted(current.loc[current.model_version.eq(version), "horizon_days"].unique())
        horizon = 28 if 28 in horizons else int(horizons[0])
    anomaly = f06_analysis(machine_id, as_of)
    with _MODEL_LOCK:
        return build_diagnosis(predictions, machine_id, as_of,
                               horizon_days=horizon, model_version=version,
                               anomaly=anomaly, selector=_SELECTOR)
