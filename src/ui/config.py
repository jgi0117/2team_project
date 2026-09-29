"""UI 전체가 공유하는 표시 기준.

기본 기준일은 UI_AS_OF. 사이드바에서 날짜를 바꾸면 store-as-of에 저장되고
모든 화면이 그 날짜로 다시 그려진다. 고장 예측은 2015-10-05부터 주 1회(월요일)
결과가 있으므로, 그 사이 날짜를 고르면 직전 예측일이 사용된다.
"""

UI_AS_OF = "2015-10-05"
AS_OF_MIN = "2015-10-05"   # 첫 예측일
AS_OF_MAX = "2015-12-31"   # 원본 데이터 마지막 달

# 사이드바 로그인 정보 (예시). 사진은 assets/profile.png가 있으면 사용하고, 없으면 이름 첫 글자.
CURRENT_USER = {
    "name": "홍길동",
    "title": "설비보전팀 · 과장",
    "role": "관리자",
}


def upto_as_of(data, as_of=UI_AS_OF):
    """기준일 이후 결과를 제외한다 (as_of 컬럼이 'YYYY-MM-DD' 문자열인 표)."""
    return data.loc[data.as_of.le(as_of or UI_AS_OF)]


def valid_as_of(value):
    """store/URL에서 받은 날짜를 허용 범위의 'YYYY-MM-DD'로 정리."""
    value = str(value or UI_AS_OF)[:10]
    return min(max(value, AS_OF_MIN), AS_OF_MAX)
