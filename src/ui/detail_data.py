"""설비 상세 화면의 발주 검토·협력사·교체 이력 데이터 (UI 확인용 예시 계산).

비용·조달기간·협력사는 data/operations의 가상 운영 데이터를 읽고, 계산 방식은 화면 확인용
단순 모델이다. 기능 담당자가 실제 로직으로 바꿀 때는 각 함수의 반환 형식만 맞추면 된다.
교체 이력은 원본 Azure PdM 정비·고장 기록(실제 데이터)을 사용한다.
"""

from datetime import date, timedelta
from functools import lru_cache
from math import exp

import pandas as pd

from src.common.paths import OPS, RAW_PDM
from src.database.readers import read_operation, read_table
from src.ui.sample_data import F02_STOCK

WON = 10_000  # 화면 단위: 만원


@lru_cache(maxsize=1)
def _costs():
    table = read_operation("costs.csv")
    if table is None:
        table = pd.read_csv(OPS / "costs.csv")
    return {comp: dict(zip(rows.cost_type, rows.amount)) for comp, rows in table.groupby("component")}


@lru_cache(maxsize=1)
def _parts():
    table = read_operation("part_master.csv")
    return (table if table is not None else pd.read_csv(OPS / "part_master.csv")).set_index("component")


@lru_cache(maxsize=1)
def _suppliers():
    table = read_operation("suppliers.csv")
    return (table if table is not None else pd.read_csv(OPS / "suppliers.csv")).set_index("supplier_id")


def part_info(comp):
    part = _parts().loc[comp]
    return {"lead": int(part.lead_time_days), "prep": int(part.preparation_days),
            "shelf_life": int(part.shelf_life_days), "supplier_id": part.supplier_id,
            "costs": _costs()[comp]}


def stock(comp):
    return next((row["stock"] for row in F02_STOCK if row["component"] == comp), 0)


def planned_cost(comp, hold_days=0):
    """계획 대응 비용 = 부품가 + 발주 행정비 + 예방 정비 인건비 + 보관비 × 보관일수."""
    c = part_info(comp)["costs"]
    return c["purchase"] + c["order_admin"] + c["preventive_labor"] + c["holding"] * max(hold_days, 0)


def emergency_cost(comp):
    """고장 후 대응 비용 = 부품가 + 긴급 할증 + 긴급 정비 인건비 + 설비 정지 손실 × 긴급 조달일수."""
    info = part_info(comp)
    c = info["costs"]
    stop_days = max(info["lead"] // 2, 1)   # 긴급 조달로 줄여도 절반은 멈춘다고 가정
    return c["purchase"] + c["expedite_surcharge"] + c["emergency_labor"] + c["downtime"] * stop_days


def saving(comp):
    """제때 발주했을 때 아끼는 금액(만원) = 고장 후 대응 비용 − 계획 대응 비용."""
    return round((emergency_cost(comp) - planned_cost(comp, 7)) / WON)


def cost_curve(comp, rise_days, as_of):
    """오늘부터 d일 뒤에 발주할 때의 예상 총비용(만원).

    부품이 필요한 시점(위험 상승 + 결정 시한의 절반으로 가정)보다 일찍 오면 보관비가 쌓이고,
    늦게 오면 고장 후 대응 비용이 날 확률이 커진다.
    """
    info = part_info(comp)
    lead = info["lead"] + info["prep"]                         # = 발주 결정 시한
    rise = rise_days if rise_days is not None else lead + 14
    need = rise + lead / 2                                     # 부품이 실제로 필요한 시점 (가정)
    scale = max(3.0, lead / 4)
    horizon = int(max(need + 7, lead + 7, 21))
    days, totals = [], []
    for day in range(0, horizon + 1):
        arrival = day + lead
        late = 1 / (1 + exp(-(arrival - need) / scale))         # 늦게 도착할 확률 (가정)
        total = (1 - late) * planned_cost(comp, need - arrival) + late * emergency_cost(comp)
        days.append(day)
        totals.append(round(total / WON, 1))
    best = min(range(len(totals)), key=lambda i: (totals[i], -i))
    deadline = max(int(need - lead), 0)
    start = date.fromisoformat(as_of)
    return {
        "days": days, "dates": [(start + timedelta(days=d)).isoformat() for d in days],
        "totals": totals, "best_day": days[best], "deadline_day": deadline,
        "deadline": (start + timedelta(days=deadline)).isoformat(),
        "scenario": {d: totals[min(d, len(totals) - 1)] for d in (0, 7, 14)},
        "lead": lead, "rise": rise, "stock": stock(comp), "too_late": lead > need,
        "quantity": 1 if stock(comp) else 2, "slack": deadline,
    }


def suppliers_for(comp):
    """주 거래처(가상 운영 데이터) + 대체 업체(예시). 행마다 발주 요청 버튼이 붙는다."""
    info = part_info(comp)
    c = info["costs"]
    main = _suppliers().loc[info["supplier_id"]]
    return [
        {"id": info["supplier_id"], "name": main.supplier_name, "tag": "주 거래처",
         "lead": info["lead"], "price": round(c["purchase"] / WON), "surcharge": 0,
         "contact": f"{main.contact_department} {main.contact_phone}"},
        {"id": "SUP-ALT", "name": "가상협력사 C", "tag": "긴급 대체",
         "lead": max(info["lead"] // 2, 2), "price": round((c["purchase"] + c["expedite_surcharge"]) / WON),
         "surcharge": round(c["expedite_surcharge"] / WON), "contact": "영업지원팀 02-XXXX-0003"},
    ]


@lru_cache(maxsize=1)
def _maint():
    maint = read_table("machine_maintenance_events")
    fails = read_table("machine_failures")
    if maint is None:
        maint = pd.read_csv(RAW_PDM / "PdM_maint.csv", parse_dates=["datetime"])
    if fails is None:
        fails = pd.read_csv(RAW_PDM / "PdM_failures.csv", parse_dates=["datetime"])
    fails = fails.rename(columns={"failure": "comp"}).assign(failure=True)
    data = maint.merge(fails, on=["datetime", "machineID", "comp"], how="left")
    return data.assign(failure=data.failure.fillna(False).astype(bool))


_WORKERS = ["김정비", "이보전", "박설비", "최점검"]


def replacement_history(machine_id, as_of, months=12):
    """기준일 이전 N개월의 교체 기록. 고장과 같은 날의 교체는 '고장 후 교체'."""
    end = pd.Timestamp(as_of) + pd.Timedelta(days=1)
    start = end - pd.DateOffset(months=months)
    data = _maint()
    rows = data.loc[data.machineID.eq(machine_id) & data.datetime.ge(start) & data.datetime.lt(end)]
    rows = rows.sort_values("datetime", ascending=False)
    result = []
    for i, row in enumerate(rows.itertuples()):
        cost = emergency_cost(row.comp) if row.failure else planned_cost(row.comp)
        result.append({"date": row.datetime.strftime("%Y-%m-%d"), "comp": row.comp,
                       "failure": bool(row.failure), "worker": _WORKERS[(i + machine_id) % len(_WORKERS)],
                       "cost": round(cost / WON)})
    return {"start": start.strftime("%Y-%m-%d"), "end": as_of, "rows": result}
