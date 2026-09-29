"""사용자가 설정 창에서 바꿀 수 있는 기본값과 기준.

store-settings(브라우저 로컬 저장)에 저장되며, 값이 바뀌면 현재 화면이 그 값으로 다시 그려진다.
로그인 기능이 생기면 사용자별로 DB에 저장하도록 바꾸면 된다.
"""

DEFAULTS = {
    "main_sort": "risk",
    "main_if_threshold": 0.50,
    "main_chips_per_day": 2,
    "main_hist_range": "6",
    "detail_sensor": "vibration",
    "detail_late_tolerance": 20,
    "detail_history_months": 12,
    "stats_horizon": 7,
}

# (카테고리, 키, 이름, 설명, 컨트롤 종류, 옵션)
SPEC = [
    ("메인화면", "main_sort", "우선 확인 TOP5 기본 정렬 기준", "메인을 열 때 TOP5가 이 기준으로 정렬됩니다.",
     "dropdown", [("risk", "설비 위험도 높은 순"), ("stock", "재고 적은 순"), ("deadline", "발주 마감 빠른 순"),
                  ("loss", "예상 손실 큰 순"), ("slack", "대응 여유 적은 순")]),
    ("메인화면", "main_if_threshold", "To-Do 이상 신호 기준 (IF 점수)",
     "설비 IF 이상 점수가 이 값을 넘으면 To-Do에 '점검' 항목으로 올라갑니다. 모델 기본값은 0.50입니다.",
     "number", {"min": 0.40, "max": 0.80, "step": 0.01}),
    ("메인화면", "main_chips_per_day", "달력 하루에 보이는 할 일 수",
     "넘치는 할 일은 '+N건 더 보기'로 묶입니다.", "dropdown", [(1, "1건"), (2, "2건"), (3, "3건")]),
    ("메인화면", "main_hist_range", "과거 대응률 기본 기간", "메인을 열 때 선택되어 있는 기간입니다.",
     "dropdown", [("3", "최근 3개월"), ("6", "최근 6개월"), ("all", "전체")]),
    ("설비화면", "detail_sensor", "센서 이상 근거 기본 센서", "설비 화면을 열 때 먼저 보이는 센서입니다.",
     "dropdown", [("vibration", "진동"), ("volt", "전압"), ("rotate", "회전속도"), ("pressure", "압력")]),
    ("설비화면", "detail_late_tolerance", "발주 마감 기준 (늦을 확률 허용치, %)",
     "부품이 필요한 시점보다 늦게 도착할 확률이 이 값 이하인 마지막 날을 '발주 마감'으로 봅니다.",
     "number", {"min": 5, "max": 50, "step": 5}),
    ("설비화면", "detail_history_months", "교체 이력 타임라인 기간 (개월)", "교체 이력에서 보여주는 기간입니다.",
     "dropdown", [(6, "6개월"), (12, "12개월")]),
    ("통계", "stats_horizon", "고장 위험 히트맵 기본 예측기간", "통계 화면을 열 때 선택되어 있는 예측기간입니다.",
     "dropdown", [(7, "7일"), (14, "14일"), (42, "42일")]),
]


def merged(stored):
    """저장된 값 위에 기본값을 채운다 (새 항목이 추가돼도 안전)."""
    values = dict(DEFAULTS)
    values.update({key: value for key, value in (stored or {}).items() if key in DEFAULTS and value is not None})
    return values
