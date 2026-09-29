"""Public F07 service."""

from functools import lru_cache

import pandas as pd

from src.common.paths import PROCESSED
from src.maintenance_planning.service import cost_analysis

NO_RISE_DAYS = 42   # 예측 기간(최대 42일) 안에 위험 상승이 없으면 그 끝을 필요 시점으로 본다


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


def analyze_order(machine_id: int, component: str, as_of=None) -> dict:
    """발주 지연일별 총비용. 목표일은 설비·부품별 위험 상승 시점(없으면 F02 계획 목표일)."""
    result = cost_analysis(machine_id, component, as_of, target_at=need_date(machine_id, component, as_of))
    return {"feature": "F07", **result}
