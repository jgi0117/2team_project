"""Public F07 service."""

from functools import lru_cache

import pandas as pd

from src.common.paths import PROCESSED
from src.maintenance_planning.service import cost_analysis, order_timing

NO_RISE_DAYS = 42   # 예측 기간(최대 42일) 안에 위험 상승이 없으면 그 끝을 필요 시점으로 본다
DECISION_DAYS = {"comp1": 8, "comp2": 42, "comp3": 16, "comp4": 24}


@lru_cache(maxsize=1)
def _risk_curve():
    data = pd.read_csv(PROCESSED / "risk_curve.csv")
    data["as_of"] = pd.to_datetime(data["as_of"])
    return data


def need_date(machine_id: int, component: str, as_of=None):
    """부품이 필요한 시점 = 예측 기준일 + 고장 위험 상승 시작일(risk_curve.risk_rise_from_days)."""
    data = _risk_curve()
    cutoff = data.as_of.max() if as_of is None else pd.Timestamp(as_of)
    rows = data.loc[data.machineID.eq(int(machine_id)) & data.component.eq(component) & data.as_of.le(cutoff)]
    if rows.empty:
        return None
    row = rows.loc[rows.as_of.idxmax()]
    days = row.risk_rise_from_days if pd.notna(row.risk_rise_from_days) else NO_RISE_DAYS
    return row.as_of + pd.Timedelta(days=int(round(days)))


def need_window(machine_id: int, component: str, as_of=None):
    """필요 시점 구간(일): 모델의 위험 상승 시작·중간·끝 (risk_rise_from/mid/to_days).

    끝이 없으면 시작 + 결정 시한/2, 중간이 없으면 시작과 끝의 가운데.
    예측 기간 안에 상승이 없으면 42일 이후로 본다.
    """
    data = _risk_curve()
    cutoff = data.as_of.max() if as_of is None else pd.Timestamp(as_of)
    rows = data.loc[data.machineID.eq(int(machine_id)) & data.component.eq(component) & data.as_of.le(cutoff)]
    spread = max(DECISION_DAYS.get(component, 14) / 2, 4)
    if rows.empty or pd.isna(rows.loc[rows.as_of.idxmax()].risk_rise_from_days):
        return (NO_RISE_DAYS, NO_RISE_DAYS + spread / 2, NO_RISE_DAYS + spread)
    row = rows.loc[rows.as_of.idxmax()]
    low = float(row.risk_rise_from_days)
    high = float(row.risk_rise_to_days) if pd.notna(row.risk_rise_to_days) else low + spread
    mode = float(row.risk_rise_mid_days) if pd.notna(row.risk_rise_mid_days) else (low + high) / 2
    return (low, mode, high)


def analyze_order(machine_id: int, component: str, as_of=None, late_tolerance: float = 0.2) -> dict:
    """이 설비 부품 1개의 발주일별 기대 총비용 (보유·폐기 vs 지연 긴급 비용, 필요 시점 불확실성 반영).

    late_tolerance: 늦게 도착할 확률이 이 값 이하인 마지막 날을 발주 마감으로 본다.
    """
    result = order_timing(machine_id, component, as_of, need_window(machine_id, component, as_of),
                          late_tolerance=late_tolerance)
    return {"feature": "F07", **result}
