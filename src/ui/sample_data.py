"""메인 화면 예시 데이터 (UI 확인용).

기능 담당자가 실제 계산 결과로 바꿀 때는 아래 필드 이름과 형식만 맞추면
화면 코드는 그대로 동작한다. 금액 단위는 만원, 날짜는 'YYYY-MM-DD'.
예시 날짜는 기준일(as_of)로부터 며칠 뒤인지(day)로 적어 두고, 기준일을 바꾸면 함께 움직인다.
"""

from datetime import date, timedelta


def shift(as_of, days):
    return (date.fromisoformat(as_of[:10]) + timedelta(days=days)).isoformat()


# ---------------- 현재 상황 KPI ----------------
# (key, 제목, 아이콘, 값, 단위, 지난주 대비 변화, 상태: danger / warn / good / neutral)
KPIS = [
    ("warning", "경고 설비", "🚨", "8", "대", "+2", "danger"),
    ("replace", "교체기한 임박", "⏰", "1", "대", "+1", "warn"),
    ("overdue", "기한 초과", "⛔", "1", "대", "0", "danger"),
    ("order", "이번 주 발주 필요", "📦", "3", "건", "", "neutral"),
    ("loss", "미조치 시 예상 손실", "💸", "2,400", "만원", "", "danger"),
    ("saving", "지금 조치 시 절감 효과", "💰", "1,850", "만원", "", "good"),
]

# KPI 카드를 눌렀을 때 보여줄 상세 목록. 행의 첫 칸은 설비 번호(누르면 설비 상세로 이동).
# 날짜 칸은 {"day": n} (기준일 + n일)로 적는다. 판정 칸은 now / watch / ok.
KPI_DETAILS = {
    "warning": {
        "desc": "고장 위험도가 경고 기준을 넘은 설비입니다.",
        "columns": ["설비", "위험 부품", "위험도", "판정", "사유"],
        "rows": [
            [23, "comp4", 91, "now", "위험도 급상승, 재고 없음"],
            [71, "comp1", 86, "now", "진동 이상 신호 반복"],
            [55, "comp1", 78, "watch", "조달 마감 임박"],
            [13, "comp3", 74, "watch", "교체 주기 도래"],
            [87, "comp3", 69, "watch", "압력 이상 신호"],
            [42, "comp4", 63, "watch", "재고 없음"],
            [98, "comp1", 58, "watch", "예방 정비 예정"],
            [16, "comp3", 52, "watch", "조달 16일 필요"],
        ],
    },
    "replace": {
        "desc": "부품 사용 기한이 14일 안에 끝나는 설비입니다.",
        "columns": ["설비", "부품", "사용 기한", "남은 기간"],
        "rows": [[30, "comp4", {"day": 11}, "11일"]],
    },
    "overdue": {
        "desc": "부품 사용 기한이 이미 지난 설비입니다.",
        "columns": ["설비", "부품", "사용 기한", "초과 기간"],
        "rows": [[64, "comp2", {"day": -3}, "3일 초과"]],
    },
    "order": {
        "desc": "이번 주 안에 발주해야 제때 부품을 받을 수 있는 건입니다.",
        "columns": ["설비", "부품", "발주 마감", "권장 수량", "재고"],
        "rows": [
            [23, "comp4", {"day": 2}, "2개", "0개"],
            [55, "comp1", {"day": 2}, "1개", "1개"],
            [98, "comp1", {"day": 4}, "1개", "3개"],
        ],
    },
    "loss": {
        "desc": "지금 조치하지 않아 고장이 나면 예상되는 손실(정지 손실 + 긴급 조달 비용)입니다.",
        "columns": ["설비", "부품", "예상 손실"],
        "rows": [
            [23, "comp4", "1,200만원"],
            [13, "comp3", "900만원"],
            [55, "comp1", "300만원"],
        ],
    },
    "saving": {
        "desc": "지금 계획 발주하면 긴급 대응보다 아낄 수 있는 비용입니다.",
        "columns": ["설비", "부품", "지금 조치 비용", "절감액"],
        "rows": [
            [23, "comp4", "180만원", "1,020만원"],
            [13, "comp3", "150만원", "750만원"],
            [55, "comp1", "220만원", "80만원"],
        ],
    },
}


def kpi_detail(key, as_of):
    detail = KPI_DETAILS[key]
    rows = [[shift(as_of, cell["day"]) if isinstance(cell, dict) else cell for cell in row]
            for row in detail["rows"]]
    return {**detail, "rows": rows}


# ---------------- 할 일 / 우선 확인 항목 ----------------
# issue: "part"(부품 교체) 또는 "anomaly"(센서 이상 신호)
# day: 달력에 표시할 날짜 = 기준일 + day (부품 → 발주 마감일, 이상 신호 → 점검 권장일)
# risk: 설비 위험도 0~100 (상대 점수, 확률 아님)
# 부품 이슈만: component, deadline_day, loss(지연 시 손실, 만원), stock(재고, 개), slack(대응 여유, 일)
_TODO = [
    {"key": "t01", "machine": 23, "issue": "part", "component": "comp4", "action": "발주",
     "day": 2, "risk": 91, "deadline_day": 2, "loss": 1200, "stock": 0, "slack": 2,
     "note": "comp4 고장 위험이 높고 재고가 없어 발주가 급합니다"},
    {"key": "t02", "machine": 71, "issue": "anomaly", "action": "점검",
     "day": 0, "risk": 86,
     "note": "최근 72시간 진동 이상 신호 5회"},
    {"key": "t03", "machine": 55, "issue": "part", "component": "comp1", "action": "발주",
     "day": 2, "risk": 78, "deadline_day": 2, "loss": 640, "stock": 1, "slack": 2,
     "note": "comp1 조달 8일 — 마감이 가까움"},
    {"key": "t04", "machine": 13, "issue": "part", "component": "comp3", "action": "교체",
     "day": 10, "risk": 74, "deadline_day": 7, "loss": 900, "stock": 2, "slack": 7,
     "note": "comp3 교체 주기 도래"},
    {"key": "t05", "machine": 87, "issue": "anomaly", "action": "점검",
     "day": 1, "risk": 69,
     "note": "압력 값이 평소 범위를 반복해서 벗어남"},
    {"key": "t06", "machine": 42, "issue": "part", "component": "comp4", "action": "발주",
     "day": 13, "risk": 63, "deadline_day": 13, "loss": 520, "stock": 0, "slack": 13,
     "note": "comp4 재고 없음"},
    {"key": "t07", "machine": 98, "issue": "part", "component": "comp1", "action": "정비",
     "day": 5, "risk": 58, "deadline_day": 4, "loss": 300, "stock": 3, "slack": 4,
     "note": "comp1 예방 정비 예정"},
    {"key": "t08", "machine": 16, "issue": "part", "component": "comp3", "action": "발주",
     "day": 16, "risk": 52, "deadline_day": 16, "loss": 410, "stock": 1, "slack": 16,
     "note": "comp3 조달 16일"},
    {"key": "t09", "machine": 64, "issue": "anomaly", "action": "점검",
     "day": 16, "risk": 47,
     "note": "회전속도 변동 증가"},
    {"key": "t10", "machine": 30, "issue": "part", "component": "comp4", "action": "교체",
     "day": 23, "risk": 41, "deadline_day": 21, "loss": 260, "stock": 2, "slack": 21,
     "note": "comp4 사용 기한 임박"},
]

ISSUE_LABEL = {"part": "부품 교체", "anomaly": "이상 신호"}


def todo_items(as_of):
    items = []
    for raw in _TODO:
        item = {key: value for key, value in raw.items() if key not in ("day", "deadline_day")}
        item["date"] = shift(as_of, raw["day"])
        if "deadline_day" in raw:
            item["deadline"] = shift(as_of, raw["deadline_day"])
        items.append(item)
    return items


# 정렬 기준: (라벨, 정렬 키). 해당 값이 없는 항목(이상 신호 등)은 뒤로 보낸다.
_LAST = float("inf")
SORTS = {
    "risk": ("설비 위험도 높은 순", lambda item: -item["risk"]),
    "stock": ("재고 적은 순", lambda item: item.get("stock", _LAST)),
    "deadline": ("발주 마감 빠른 순", lambda item: item.get("deadline", "9999")),
    "loss": ("예상 손실 큰 순", lambda item: -item.get("loss", -_LAST)),
    "slack": ("대응 여유 적은 순", lambda item: item.get("slack", _LAST)),
}
DEFAULT_SORT = "risk"


def ranked_items(dismissed=(), sort=DEFAULT_SORT, as_of="2015-10-05"):
    """삭제하지 않은 항목을 정렬 기준대로 반환 (동점은 설비 위험도 순)."""
    key = SORTS.get(sort, SORTS[DEFAULT_SORT])[1]
    items = [item for item in todo_items(as_of) if item["key"] not in set(dismissed or ())]
    return sorted(items, key=lambda item: (key(item), -item["risk"]))


def item_by_key(key, as_of="2015-10-05"):
    return next((item for item in todo_items(as_of) if item["key"] == key), None)


# ---------------- 하단 ----------------
# F01 확률 급상승 알림: 지난주 대비 설비 위험도 상승폭(점) 큰 순. 화면에는 상위 3개, '전체보기'에 전부.
F01_RISE = [
    {"machine": 23, "component": "comp4", "before": 64, "after": 91},
    {"machine": 71, "component": "comp1", "before": 68, "after": 86},
    {"machine": 55, "component": "comp1", "before": 66, "after": 78},
    {"machine": 13, "component": "comp3", "before": 65, "after": 74},
    {"machine": 42, "component": "comp4", "before": 57, "after": 63},
]
F01_IS_NEW = True  # 이번 주 새로 들어온 알림이 있으면 NEW 배지

# F02 재고 × 위험 교차: 부품 4종 전부. 재고가 적은데 위험 설비가 많은 순.
# status: "now"(즉시) / "watch"(주의) / "ok"(관찰) — 모델 risk_curve.csv의 판정 단어와 같다
F02_STOCK = [
    {"component": "comp4", "stock": 0, "risky": 3, "status": "now", "adopted": True},
    {"component": "comp1", "stock": 2, "risky": 2, "status": "watch", "adopted": True},
    {"component": "comp3", "stock": 5, "risky": 1, "status": "ok", "adopted": True},
    {"component": "comp2", "stock": 6, "risky": 0, "status": "ok", "adopted": False},
]
F02_IS_NEW = True
STATUS_LABEL = {"now": "즉시", "watch": "주의", "ok": "관찰"}

# 과거 대응률: 월별 (누적 아님). 위험 건은 '발주 마감일이 속한 달'로 묶는다.
#   due: 그 달에 발주 마감이 도래한 위험 건수
#   on_time: 그중 마감 전에 발주한 건수 → 적시 대응률 = on_time / due
#   saved: 제때 발주해서 아낀 비용(만원) = Σ(고장 후 대응 비용 − 계획 대응 비용), 계산식은 detail_data.saving
# 기준일이 속한 달은 진행 중(기준일 이후 마감 건은 아직 판정하지 않음).
HISTORY_MONTHS = {  # (연, 월): (due, on_time, saved)
    (2015, 1): (12, 6, 1650), (2015, 2): (14, 8, 1980), (2015, 3): (13, 8, 1890),
    (2015, 4): (16, 10, 2240), (2015, 5): (15, 9, 2100), (2015, 6): (18, 12, 2650),
    (2015, 7): (14, 11, 2400), (2015, 8): (20, 17, 3350), (2015, 9): (22, 19, 3900),
    (2015, 10): (21, 16, 3300), (2015, 11): (19, 16, 3150), (2015, 12): (17, 15, 2980),
}
HISTORY_FIRST = (2015, 1)
DEFAULT_ORDER_SAVING = 500  # 할 일 목록에 없는 발주 1건의 절감액 가정 (만원)


def month_key(value):
    return int(value[:4]), int(value[5:7])


def available_months(as_of):
    """선택 가능한 달: 데이터 첫 달 ~ 기준일이 속한 달 ('YYYY-MM')."""
    end = month_key(as_of)
    months, (y, m) = [], HISTORY_FIRST
    while (y, m) <= end:
        months.append(f"{y}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return months


def history(as_of, orders=(), start=None, end=None):
    """start~end 달('YYYY-MM')의 월별 기록. 기준일이 속한 달은 진행 중이며 세션 발주를 더한다."""
    months = available_months(as_of)
    end = end if end in months else months[-1]
    start = start if start in months else months[max(0, months.index(end) - 5)]
    if start > end:
        start, end = end, start
    current = months[-1]
    rows = []
    for month in months[months.index(start):months.index(end) + 1]:
        due, on_time, saved = HISTORY_MONTHS.get(month_key(month), (15, 10, 2000))
        if month == current:   # 진행 중인 달은 기준일까지 마감된 건만 (일수 비율로 축소)
            share = min(int(as_of[8:10]) / 30, 1)
            due, on_time, saved = max(round(due * share), 1), round(on_time * share), round(saved * share)
        rows.append({"month": f"{int(month[5:])}월", "key": month, "due": due, "on_time": on_time,
                     "saved": saved, "current": month == current})
    items = {(item["machine"], item.get("component")): item for item in todo_items(as_of)}
    if rows and rows[-1]["current"]:
        for order in orders or ():
            # 발주한 건은 이번 달 마감 도래 건 중 하나로 보고 '제때 대응'으로 옮긴다.
            item = items.get((order.get("machine"), order.get("component")))
            rows[-1]["due"] = max(rows[-1]["due"], rows[-1]["on_time"] + 1)
            rows[-1]["on_time"] += 1
            rows[-1]["saved"] += item["loss"] if item and "loss" in item else DEFAULT_ORDER_SAVING
    return rows
