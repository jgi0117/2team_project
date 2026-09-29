"""UI 전체가 공유하는 표시 기준.

기준일을 바꾸려면 UI_AS_OF만 수정한다. 고장 예측은 2015-10-05부터 주 1회
(월요일) 결과가 있으므로, 그 사이 날짜를 넣으면 직전 예측일이 사용된다.
"""

UI_AS_OF = "2015-10-05"


def upto_as_of(data, as_of=UI_AS_OF):
    """기준일 이후 결과를 제외한다 (as_of 컬럼이 'YYYY-MM-DD' 문자열인 표)."""
    return data.loc[data.as_of.le(as_of)]
