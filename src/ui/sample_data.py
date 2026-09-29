"""메인 화면 예시 데이터 (UI 확인용).

기능 담당자가 실제 계산 결과로 바꿀 때는 아래 필드 이름과 형식만 맞추면
화면 코드는 그대로 동작한다. 금액 단위는 만원, 날짜는 'YYYY-MM-DD'.
"""

# ---------------- 현재 상황 KPI ----------------
# (제목, 아이콘, 값, 단위, 지난주 대비 변화, 상태: danger / warn / good / neutral)
KPIS = [
    ("경고 설비", "🚨", "8", "대", "+2", "danger"),
    ("교체기한 임박", "⏰", "1", "대", "+1", "warn"),
    ("기한 초과", "⛔", "1", "대", "0", "danger"),
    ("이번 주 발주 필요", "📦", "3", "건", "", "neutral"),
    ("미조치 시 예상 손실", "💸", "2,400", "만원", "", "danger"),
    ("지금 조치 시 절감 효과", "💰", "1,850", "만원", "", "good"),
]

# ---------------- 할 일 / 우선 확인 항목 ----------------
# issue: "part"(부품 교체) 또는 "anomaly"(센서 이상 신호)
# date: 달력에 표시할 날짜 (부품 → 발주 마감일, 이상 신호 → 점검 권장일)
# risk: 설비 위험도 0~100 (상대 점수, 확률 아님)
# 부품 이슈만: component, deadline, loss(지연 시 손실, 만원), stock(재고, 개), slack(대응 여유, 일)
TODO_ITEMS = [
    {"key": "t01", "machine": 23, "issue": "part", "component": "comp4", "action": "발주",
     "date": "2015-10-07", "risk": 91, "deadline": "2015-10-07", "loss": 1200, "stock": 0, "slack": 2,
     "note": "comp4 고장 위험이 높고 재고가 없어 발주가 급합니다"},
    {"key": "t02", "machine": 71, "issue": "anomaly", "action": "점검",
     "date": "2015-10-05", "risk": 86,
     "note": "최근 72시간 진동 이상 신호 5회"},
    {"key": "t03", "machine": 55, "issue": "part", "component": "comp1", "action": "발주",
     "date": "2015-10-07", "risk": 78, "deadline": "2015-10-07", "loss": 640, "stock": 1, "slack": 2,
     "note": "comp1 조달 8일 — 마감이 가까움"},
    {"key": "t04", "machine": 13, "issue": "part", "component": "comp3", "action": "교체",
     "date": "2015-10-15", "risk": 74, "deadline": "2015-10-12", "loss": 900, "stock": 2, "slack": 7,
     "note": "comp3 교체 주기 도래"},
    {"key": "t05", "machine": 87, "issue": "anomaly", "action": "점검",
     "date": "2015-10-06", "risk": 69,
     "note": "압력 값이 평소 범위를 반복해서 벗어남"},
    {"key": "t06", "machine": 42, "issue": "part", "component": "comp4", "action": "발주",
     "date": "2015-10-18", "risk": 63, "deadline": "2015-10-18", "loss": 520, "stock": 0, "slack": 13,
     "note": "comp4 재고 없음"},
    {"key": "t07", "machine": 98, "issue": "part", "component": "comp1", "action": "정비",
     "date": "2015-10-10", "risk": 58, "deadline": "2015-10-09", "loss": 300, "stock": 3, "slack": 4,
     "note": "comp1 예방 정비 예정"},
    {"key": "t08", "machine": 16, "issue": "part", "component": "comp3", "action": "발주",
     "date": "2015-10-21", "risk": 52, "deadline": "2015-10-21", "loss": 410, "stock": 1, "slack": 16,
     "note": "comp3 조달 16일"},
    {"key": "t09", "machine": 64, "issue": "anomaly", "action": "점검",
     "date": "2015-10-21", "risk": 47,
     "note": "회전속도 변동 증가"},
    {"key": "t10", "machine": 30, "issue": "part", "component": "comp4", "action": "교체",
     "date": "2015-10-28", "risk": 41, "deadline": "2015-10-26", "loss": 260, "stock": 2, "slack": 21,
     "note": "comp4 사용 기한 임박"},
]

ISSUE_LABEL = {"part": "부품 교체", "anomaly": "이상 신호"}

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


def ranked_items(dismissed=(), sort=DEFAULT_SORT):
    """삭제하지 않은 항목을 정렬 기준대로 반환 (동점은 설비 위험도 순)."""
    key = SORTS.get(sort, SORTS[DEFAULT_SORT])[1]
    items = [item for item in TODO_ITEMS if item["key"] not in set(dismissed or ())]
    return sorted(items, key=lambda item: (key(item), -item["risk"]))


def item_by_key(key):
    return next((item for item in TODO_ITEMS if item["key"] == key), None)


# ---------------- 하단 차트 ----------------
# F01 확률 급상승 알림: 지난주 대비 설비 위험도 상승폭(점) 큰 순. 화면에는 상위 3개, '전체보기'에 전부.
F01_RISE = [
    {"machine": 23, "component": "comp4", "before": 64, "after": 91},
    {"machine": 71, "component": "comp1", "before": 68, "after": 86},
    {"machine": 55, "component": "comp1", "before": 66, "after": 78},
    {"machine": 13, "component": "comp3", "before": 65, "after": 74},
    {"machine": 42, "component": "comp4", "before": 57, "after": 63},
]
F01_IS_NEW = True  # 이번 주 새로 들어온 알림이 있으면 NEW 배지

# F02 재고 × 위험 교차: 재고가 적은데 위험 설비가 많은 부품 순.
# status: "now"(즉시) / "watch"(주의) / "ok"(관찰) — 판정 기준은 기능 담당이 확정
F02_STOCK = [
    {"component": "comp4", "stock": 0, "risky": 3, "status": "now", "adopted": True},
    {"component": "comp1", "stock": 2, "risky": 2, "status": "watch", "adopted": True},
    {"component": "comp3", "stock": 5, "risky": 1, "status": "ok", "adopted": True},
    {"component": "comp2", "stock": 6, "risky": 0, "status": "ok", "adopted": False},
]
F02_IS_NEW = True
STATUS_LABEL = {"now": "즉시", "watch": "주의", "ok": "관찰"}

# 과거 대응률: 월별 누적 (대). 발주를 넣을 때마다 '대응 완료'가 기준월(마지막 달)에 더해진다.
HISTORY = [
    {"month": "5월", "risky": 15, "handled": 14},
    {"month": "6월", "risky": 40, "handled": 28},
    {"month": "7월", "risky": 46, "handled": 30},
    {"month": "8월", "risky": 53, "handled": 35},
    {"month": "9월", "risky": 79, "handled": 57},
    {"month": "10월", "risky": 88, "handled": 65},
]
