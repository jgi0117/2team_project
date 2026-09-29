"""GJ 기능(F01·F02·F04·F07·F08, maintenance_planning)을 UI 형식으로 바꾸는 연결부.

화면에 나오는 값은 모두 원본(Azure PdM)·모델 산출물·가상 운영 데이터를 기능 모듈이 계산한 결과다.
여기서는 단위 변환(원→만원, 점수→상대 위험도), 문구, 미채택 부품(comp2) 제외만 한다.
"""

from __future__ import annotations

import math
from datetime import date, timedelta
from functools import lru_cache

import pandas as pd

from src.common.labels import load_events
from src.common.paths import OPS, PROCESSED
from src.F01 import build_detection
from src.F02 import build_procurement
from src.F04 import build_tracking
from src.F07 import analyze_order
from src.F08 import get_history, get_supplier_options
from src.maintenance_planning.service import build_maintenance_plan, response_unit_costs

ISSUE_LABEL = {"part": "부품 교체", "anomaly": "이상 신호"}
STATUS_LABEL = {"now": "즉시", "watch": "주의", "ok": "관찰"}

# 우선순위 정렬 기준: (라벨, 정렬 키). 값이 없는 항목(이상 신호 등)은 뒤로.
_LAST = float("inf")
SORTS = {
    "risk": ("설비 위험도 높은 순", lambda item: -item["risk"]),
    "stock": ("재고 적은 순", lambda item: item.get("stock", _LAST)),
    "deadline": ("발주 마감 빠른 순", lambda item: item.get("deadline", "9999")),
    "loss": ("예상 손실 큰 순", lambda item: -item.get("loss", -_LAST)),
    "slack": ("대응 여유 적은 순", lambda item: item.get("slack", _LAST)),
}
DEFAULT_SORT = "risk"

WON = 10_000
ADOPTED = {"comp1": True, "comp2": False, "comp3": True, "comp4": True}   # comp2는 예측 미채택 → 우선순위 제외
TODO_LIMIT = 12
ACTION = {"late": "긴급 발주", "order_due": "발주", "watch": "발주 준비", "covered": "교체 준비"}


def _day(value):
    return pd.Timestamp(value).strftime("%Y-%m-%d")


def _manwon(value):
    return round(float(value) / WON)


@lru_cache(maxsize=32)
def procurement(as_of):
    return build_procurement(as_of)


@lru_cache(maxsize=32)
def detection(as_of):
    return build_detection(as_of)


def _risk_scale(as_of):
    plan = build_maintenance_plan(as_of)
    return float(plan.loc[plan.component.map(ADOPTED)].risk_score.max() or 1)


def relative_risk(score, as_of):
    """미보정 점수를 같은 기준일 채택 부품 최대값 대비 0~100 상대 위험도로."""
    return int(round(100 * float(score) / _risk_scale(as_of)))


def _candidates(as_of):
    """GJ와 같은 기준: 부품별 위험 상위 5%를 단기 확인 대상으로."""
    plan = build_maintenance_plan(as_of)
    groups = [rows.nlargest(max(1, math.ceil(len(rows) * .05)), "risk_score")
              for _, rows in plan.groupby("component", sort=True)]
    return pd.concat(groups, ignore_index=True)


# ---------------- 현재 상황 KPI ----------------
def _kpi_numbers(as_of):
    kpis = procurement(as_of)["kpis"]
    return {"warning": kpis["warning_machines"], "replace": kpis["replacement_due"],
            "overdue": kpis["late_items"], "order": kpis["order_due"],
            "loss": _manwon(kpis["unacted_loss"]), "saving": _manwon(kpis["action_savings"])}


KPI_META = [
    ("warning", "경고 설비", "🚨", "대", "danger"),
    ("replace", "교체기한 임박", "⏰", "건", "warn"),
    ("overdue", "기한 초과", "⛔", "건", "danger"),
    ("order", "이번 주 발주 필요", "📦", "건", "neutral"),
    ("loss", "미조치 시 예상 손실", "💸", "만원", "danger"),
    ("saving", "지금 조치 시 절감 효과", "💰", "만원", "good"),
]


def kpis(as_of):
    """(key, 제목, 아이콘, 값, 단위, 지난주 대비, 상태) — 비교 기준은 7일 전 예측."""
    now = _kpi_numbers(as_of)
    try:
        before = _kpi_numbers(_day(pd.Timestamp(as_of) - pd.Timedelta(days=7)))
    except ValueError:   # 첫 예측일 이전에는 비교 대상 없음
        before = None
    rows = []
    for key, title, icon, unit, state in KPI_META:
        value = now[key]
        change = ""
        if before is not None and unit != "만원":
            diff = value - before[key]
            change = f"+{diff}" if diff > 0 else (str(diff) if diff < 0 else "0")
        rows.append((key, title, icon, f"{value:,}", unit, change, state))
    return rows


def kpi_detail(key, as_of):
    data = procurement(as_of)
    if key == "warning":
        det = detection(as_of)
        plan = build_maintenance_plan(as_of)
        anomaly = det["anomaly_map"]
        flags = set() if anomaly.empty else set(
            anomaly.loc[anomaly.is_anomaly.astype(str).str.lower().isin(["1", "true"]), "machineID"].astype(int))
        rows = []
        for machine in det["warning_machine_ids"]:
            parts = plan.loc[plan.machineID.eq(machine) & plan.component.map(ADOPTED)]
            top = parts.nlargest(1, "risk_score").iloc[0] if not parts.empty else None
            reason = " · ".join(filter(None, ["고장 위험 상위 5%" if machine not in flags or top is not None else "",
                                              "센서 IF 경고" if machine in flags else ""]))
            rows.append([machine, top.component if top is not None else "—",
                         relative_risk(top.risk_score, as_of) if top is not None else "—",
                         "now" if machine in flags else "watch", reason or "고장 위험 상위 5%"])
        return {"desc": f"경고 기준: {det['warning_policy']}.",
                "columns": ["설비", "위험 부품", "위험도", "판정", "사유"], "rows": rows}
    frame = {"replace": data["replacement_due_rows"], "order": data["order_due_rows"]}.get(key)
    if key == "overdue":
        frame = _candidates(as_of).loc[lambda x: x.status.eq("late")]
    if frame is not None:
        desc = {"replace": "정비 목표일이 14일 안에 오는 위험 상위 설비·부품입니다.",
                "overdue": "부품 준비 완료 예정일이 계획 정비일보다 늦은 건입니다.",
                "order": "이번 주 안에 발주 마감이 오는 건입니다."}[key]
        return {"desc": desc, "columns": ["설비", "부품", "발주 마감", "정비 목표일", "대응 여유", "사유"],
                "rows": [[int(r.machineID), r.component, _day(r.order_by_at), _day(r.target_maintenance_at),
                          f"{int(r.response_margin_days)}일", r.reason] for r in frame.itertuples()]}
    # loss / saving: 우선 조치 대상(재고로 대응 불가) 오늘 발주 vs 14일 뒤 발주
    rows = []
    for r in _candidates(as_of).loc[lambda x: x.status.ne("covered")].nlargest(5, "risk_score").itertuples():
        cost = analyze_order(int(r.machineID), r.component, as_of)
        now, later = cost["scenarios"][0]["total_cost"], cost["scenarios"][14]["total_cost"]
        rows.append([int(r.machineID), r.component, f"{_manwon(now):,}만원", f"{_manwon(later):,}만원",
                     f"{_manwon(max(0, later - now)):,}만원"])
    return {"desc": ("우선 조치 대상(재고로 대응할 수 없는 위험 상위 건)을 오늘 발주할 때와 14일 뒤 발주할 때의 "
                     "예상 비용입니다. 손실 = 14일 뒤 발주 비용, 절감 = 그 차이."),
            "columns": ["설비", "부품", "오늘 발주", "14일 뒤 발주", "절감"], "rows": rows}


# ---------------- 할 일 · TOP5 ----------------
@lru_cache(maxsize=64)
def _todo_cached(as_of, if_threshold=None):
    items = []
    plan_rows = _candidates(as_of)
    plan_rows = plan_rows.loc[plan_rows.component.map(ADOPTED)]
    for r in plan_rows.sort_values("risk_score", ascending=False).head(TODO_LIMIT).itertuples():
        need_order = r.status != "covered"
        when = max(pd.Timestamp(r.order_by_at), pd.Timestamp(as_of)) if need_order else r.target_maintenance_at
        try:
            cost = analyze_order(int(r.machineID), r.component, as_of)
            loss = _manwon(max(0, cost["scenarios"][14]["total_cost"] - cost["scenarios"][0]["total_cost"]))
        except ValueError:
            loss = 0
        items.append({
            "key": f"{int(r.machineID)}-{r.component}", "machine": int(r.machineID), "issue": "part",
            "component": r.component, "action": ACTION.get(r.status, "확인"),
            "date": _day(when), "risk": relative_risk(r.risk_score, as_of),
            "deadline": _day(r.order_by_at), "loss": loss, "stock": int(r.available_stock),
            "slack": int(r.response_margin_days), "note": r.reason,
        })
    anomaly = detection(as_of)["anomaly_map"]
    if not anomaly.empty:
        # 설정의 '이상 신호 기준'이 있으면 그 값, 없으면 모델 기준(threshold)으로 판정
        cut = anomaly.threshold.astype(float) if if_threshold is None else float(if_threshold)
        flagged = anomaly.loc[anomaly.anomaly_score.astype(float) > cut]
        for r in flagged.sort_values("anomaly_score", ascending=False).head(5).itertuples():
            limit = float(r.threshold) if if_threshold is None else float(if_threshold)
            items.append({
                "key": f"{int(r.machineID)}-if", "machine": int(r.machineID), "issue": "anomaly",
                "action": "점검", "date": _day(as_of),
                "risk": min(100, int(round(100 * float(r.anomaly_score) / max(limit * 1.3, 1e-9)))),
                "note": f"센서 IF 이상 점수 {float(r.anomaly_score):.3f} (기준 {limit:.2f} 초과)",
            })
    return items


def todo_items(as_of, if_threshold=None):
    return [dict(item) for item in _todo_cached(as_of, if_threshold)]


def ranked_items(dismissed=(), sort=DEFAULT_SORT, as_of="2015-10-05", if_threshold=None):
    key = SORTS.get(sort, SORTS[DEFAULT_SORT])[1]
    items = [item for item in todo_items(as_of, if_threshold) if item["key"] not in set(dismissed or ())]
    return sorted(items, key=lambda item: (key(item), -item["risk"]))


def item_by_key(key, as_of="2015-10-05", if_threshold=None):
    return next((item for item in todo_items(as_of, if_threshold) if item["key"] == key), None)


# ---------------- F01 급상승 · F02 재고 × 위험 ----------------
def f01_rise(as_of):
    """전일 대비 7일 위험 점수 상승 (점 = 점수 × 100)."""
    return [{"machine": int(row["machineID"]), "component": None,
             "before": round(100 * (row["failure_probability"] - row["change"])),
             "after": round(100 * row["failure_probability"])}
            for row in detection(as_of)["surges"]]


def f02_stock(as_of):
    rows = []
    for r in procurement(as_of)["part_risk"].itertuples():
        status = "now" if r.urgent else "watch" if r.demand_shortage else "ok"
        rows.append({"component": r.component, "stock": int(r.available_stock),
                     "risky": int(r.risk_machines), "status": status, "adopted": ADOPTED[r.component]})
    return sorted(rows, key=lambda row: (not row["adopted"], {"now": 0, "watch": 1, "ok": 2}[row["status"]],
                                         row["stock"] - row["risky"]))


# ---------------- 과거 대응률 (F04) ----------------
def available_months(as_of):
    """F04는 기준일이 속한 해 1월부터 기준일까지 월별로 집계한다."""
    start = pd.Timestamp(as_of).replace(month=1, day=1)
    return [p.strftime("%Y-%m") for p in pd.period_range(start, pd.Timestamp(as_of), freq="M")]


def saving(comp):
    """예방 교체 1건의 절감액(만원) = 고장 후 대응 비용 − 계획 대응 비용 (response_unit_costs)."""
    return _manwon(response_unit_costs(comp)["saving"])


@lru_cache(maxsize=1)
def _events():
    return load_events()


@lru_cache(maxsize=32)
def _monthly_savings(as_of):
    """예방 교체(고장 전 교체) 1건마다 부품별 '고장 후 대응 비용 − 계획 대응 비용'(만원)을 월별 합산."""
    cutoff = pd.Timestamp(as_of).normalize()
    events = _events()
    events = events.loc[events.date.between(cutoff.replace(month=1, day=1), cutoff) & events.is_emergency.eq(0)]
    per_comp = {comp: saving(comp) for comp in ADOPTED}
    saved = events.assign(saved=events.component.map(per_comp), period=events.date.dt.strftime("%Y-%m"))
    return saved.groupby("period").saved.sum().to_dict()


def history(as_of, orders=(), start=None, end=None):
    months = available_months(as_of)
    end = end if end in months else months[-1]
    start = start if start in months else months[max(0, months.index(end) - 5)]
    if start > end:
        start, end = end, start
    tracking = build_tracking(as_of)["history"].set_index("period")
    savings = _monthly_savings(as_of)
    current = months[-1]
    rows = []
    for month in months[months.index(start):months.index(end) + 1]:
        due = int(tracking.requests.get(month, 0))
        on_time = int(tracking.responded.get(month, 0))
        rows.append({"month": f"{int(month[5:])}월", "key": month, "due": due, "on_time": on_time,
                     "saved": int(savings.get(month, 0)), "current": month == current})
    if rows and rows[-1]["current"]:
        for order in orders or ():
            # 화면에서 넣은 발주는 이번 달 예방 대응 1건으로 더한다.
            rows[-1]["due"] += 1
            rows[-1]["on_time"] += 1
            rows[-1]["saved"] += saving(order.get("component") or "comp1") * int(order.get("qty", 1))
    return rows


# ---------------- 설비 상세: 발주 검토 · 협력사 · 조치 이력 ----------------
def cost_review(machine_id, comp, as_of, rise=None, late_tolerance=20):
    """F07 발주일별 기대 총비용을 detail 화면 형식(만원, 날짜)으로."""
    result = analyze_order(int(machine_id), comp, as_of, late_tolerance=float(late_tolerance) / 100)
    plan = result["plan"]
    start = pd.Timestamp(plan["as_of"]).normalize()
    curve = result["curve"]
    order_by = pd.Timestamp(result["order_by_at"]).normalize()
    deadline_day = int((order_by - start).days)
    low, mode, high = result["need_window"]
    need_from, need_to = _day(start + timedelta(days=round(low))), _day(start + timedelta(days=round(high)))
    too_late = bool(result["too_late"])
    if too_late:
        reason = (f"부품이 필요한 시점({need_from}~{need_to})까지 조달 {result['lead_days']}일을 맞출 수 없습니다. "
                  "오늘 발주하거나 긴급 대체 업체(납기 단축)를 검토하세요.")
    elif deadline_day <= 7:
        reason = f"발주 마감까지 {deadline_day}일 남았습니다 · 필요 시점 {need_from}~{need_to}"
    else:
        reason = f"발주 마감까지 여유가 있습니다 ({deadline_day}일) · 필요 시점 {need_from}~{need_to}"

    def breakdown(item):
        return {"base": round(item["base"] / WON, 1), "early": round((item["holding"] + item["expiry"]) / WON, 2),
                "late": round(item["late"] / WON, 1), "late_p": round(100 * item["late_probability"])}

    return {
        "days": [item["delay_days"] for item in curve],
        "dates": [_day(start + timedelta(days=item["delay_days"])) for item in curve],
        "totals": [round(item["total_cost"] / WON, 1) for item in curve],
        "early": [round((item["holding"] + item["expiry"]) / WON, 2) for item in curve],
        "late": [round(item["late"] / WON, 1) for item in curve],
        "late_p": [round(100 * item["late_probability"]) for item in curve],
        "best_day": int(result["optimum"]["delay_days"]),
        "deadline": _day(order_by), "deadline_day": deadline_day,
        "scenario": {d: round(result["scenarios"][d]["total_cost"] / WON, 1) for d in (0, 7, 14)},
        "scenario_parts": {d: breakdown(result["scenarios"][d]) for d in (0, 7, 14)},
        "best_parts": breakdown(result["optimum"]),
        "lead": int(result["lead_days"]), "shelf": int(result["shelf_life_days"]), "rise": rise,
        "stock": int(plan["available_stock"]), "too_late": too_late, "quantity": 1,
        "slack": max(deadline_day, 0), "reason": reason,
        "status": "late" if too_late else ("order_due" if deadline_day <= 7 else "watch"),
        "target": _day(result["target_at"]), "need_from": need_from, "need_to": need_to,
        "tolerance": int(late_tolerance),
    }


def suppliers(comp, as_of):
    """주 거래처 + 긴급 대체 업체 (F08, data/operations/supplier_terms.csv)."""
    return [{"id": row["supplier_id"], "name": row["supplier_name"],
             "tag": "주 거래처" if row["role"] == "primary" else "긴급 대체",
             "lead": row["lead_time_days"], "price": _manwon(row["unit_price"]),
             "surcharge": _manwon(row["surcharge"]),
             "contact": f"{row['contact_department']} {row['contact_phone']}"}
            for row in get_supplier_options(comp, as_of)]


def replacement_history(machine_id, as_of, months=12):
    """타임라인: 원본 교체 이벤트(예방/고장 후, F04와 같은 정의). 표: F08 조치 기록."""
    cutoff = pd.Timestamp(as_of).normalize()
    start = cutoff - pd.DateOffset(months=months)
    events = _events()
    events = events.loc[events.machineID.eq(machine_id) & events.date.between(start, cutoff)]
    timeline = [{"date": _day(r.date), "comp": r.component, "failure": bool(r.is_emergency),
                 "cost": _manwon(response_unit_costs(r.component)["emergency" if r.is_emergency else "planned"])}
                for r in events.sort_values("date", ascending=False).itertuples()]
    records = get_history(int(machine_id), as_of, limit=None)
    table = [{"planned": _day(r.planned_at),
              "completed": "" if pd.isna(r.completed_at) else _day(r.completed_at),
              "comp": r.component, "result": r.result, "qty": int(r.quantity_used or 0),
              "delay": None if pd.isna(r.delay_days) else float(r.delay_days)}
             for r in records.itertuples()]
    return {"start": _day(start), "end": _day(cutoff), "rows": timeline, "records": table}


# ---------------- comp2 안전재고 근거 ----------------
@lru_cache(maxsize=1)
def _metrics():
    return pd.read_csv(PROCESSED / "model_metrics.csv")


def safety_stock_info(comp, as_of):
    """예측을 채택하지 않은 부품이 왜 안전재고로 대응하는지: 모델 성능·조달 조건·현재 재고 (모두 데이터 값)."""
    meta = _parts().loc[comp]
    decision = int(meta.lead_time_days + meta.preparation_days)
    metrics = _metrics()
    row = metrics.loc[metrics.component.eq(comp) & metrics.horizon_days.eq(decision) & metrics.source.eq("ml")]
    values = row.set_index("metric").value.to_dict()
    plan = build_maintenance_plan(as_of)
    part = plan.loc[plan.component.eq(comp)].iloc[0]
    cutoff = pd.Timestamp(as_of).normalize()
    events = _events()
    recent = events.loc[events.component.eq(comp) & events.date.between(cutoff - pd.Timedelta(days=90), cutoff)]
    daily = len(recent) / 90
    stock = int(part.available_stock)
    receipt = part.expected_receipt_at
    return {
        "component": comp, "decision_days": decision, "lead": int(meta.lead_time_days),
        "prep": int(meta.preparation_days), "shelf_life": int(meta.shelf_life_days),
        "target_stock": int(meta.target_stock), "stock": stock,
        "recommended": int(part.recommended_quantity), "daily_demand": round(daily, 2),
        "coverage_days": int(stock / daily) if daily else None,
        "next_receipt": None if pd.isna(receipt) else _day(receipt),
        "auc": values.get("auc"), "lift": values.get("lift_top10"), "base_rate": values.get("base_rate"),
    }


@lru_cache(maxsize=1)
def _parts():
    return pd.read_csv(OPS / "part_master.csv").set_index("component")