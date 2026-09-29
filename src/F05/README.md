# F05 · 설비 종합 진단

## 목적

한 설비의 부품별 고장 위험 순위와 F06에서 계산한 센서 이상 판정을 함께 설명합니다.
F05는 센서 통계나 IF를 직접 재계산하지 않고, 기존 결과를 별도 근거로 받습니다.
Qwen은 보여줄 근거를 선택할 수 있지만 위험 점수와 상태 판정을 변경하지 않습니다.

## 위험 비교

예측 입력은 `machineID, component, as_of, horizon_days, failure_probability,
model_version`을 포함합니다. 조회 기준일 이하, 지정된 예측 기간 및 모델 버전을 만족하는
행 중 선택 설비의 가장 최근 예측일을 고릅니다. 모든 설비 비교도 그 동일한 예측일에
맞춥니다. 이 날짜에서 설비별 대표 점수는 부품별 점수의 최댓값입니다.

- `highest_component`: 선택 설비에서 점수가 가장 높은 부품. 동점은 부품 ID 오름차순.
- `risk_rank`: 비교 설비 중 대표 점수 내림차순 순위. 동점은 같은 순위로 처리합니다.
- `risk_percentile`: 비교 대상 대표 점수 중 선택 설비 점수 이하인 값의 비율.
- 상태: IF 경고 또는 상위 5백분위 이상이면 `priority`; 통계 이상 센서가 있거나
    상위 20백분위 이상이면 `watch`; 그 외는 `normal`.

IF 경고는 `anomaly["if"]["is_anomaly"]`, 센서 통계 경고는 각 센서의 `three_sigma`/
`iqr` 판정 중 하나라도 이상인 센서의 개수로 봅니다. 부품별 점수와 IF 점수는 단위와
의미가 다르므로 서로 산술 결합하지 않습니다.

## 사용 예

```python
from src.F05 import build_diagnosis
from src.ai_summary import QwenSelector

result = build_diagnosis(predictions, machine_id=1, as_of="2015-12-21",
                                                 horizon_days=28, model_version="fp_v1",
                                                 anomaly=f06_result, selector=QwenSelector())
print(result["condition_status"], result["text"])
```

`anomaly`는 선택 설비에 대한 F06 결과 딕셔너리이며 생략할 수 있습니다. 결과에는
대표 부품/점수, 보정 여부, 상대 순위와 비교 설비 수, IF 감지 여부, 통계 경고 센서 수,
상태, 요약문과 근거가 포함됩니다. 예측 행이 없으면 `status=no_data`를 반환합니다.

## 설명 문구와 제약

보정된 값만 고장 확률(%)로 표시하고 미보정 값은 위험 점수로 표시합니다. 부품 예측이
일부 빠진 경우 없는 부품을 0점으로 간주하지 않고 미제공 근거를 남깁니다. 결과는
기준일 시점의 상대적 위험 분류이며 정확한 고장 시각이나 잔여 수명이 아닙니다. IF/통계
이상과 특정 부품 고장 사이의 인과관계를 뜻하지 않습니다.

설비 상세 UI는 `src/ui/ai_data.py`에서 F03/F05가 같은 Qwen 인스턴스를 재사용할 수
있습니다. Qwen 없이도 템플릿 요약이 가능하고 F06은 LLM 호출 없이 수치 판정만 합니다.
