# F03 · 고장 위험 기반 한 줄 대응 요약

## 목적

이미 계산된 부품별 고장 예측과 선택적으로 F02 유지보수 계획을 받아, 지금 가장
우선할 설비·부품 및 대응을 한 문장으로 요약합니다. F03 자체는 예측 모델을 실행하지
않고 새로운 위험 점수나 비용을 계산하지 않습니다. Dash와 독립적인 Python API/CLI입니다.

## 입력과 시점 선택

예측 DataFrame에는 `machineID, component, as_of, horizon_days, failure_probability,
model_version`이 필요합니다. `calibrated`가 없으면 미보정으로 취급합니다. 계획 입력에는
`machineID, component, as_of`와 선택 열 `status, available_stock, order_by_at,
response_margin_days` 등을 사용할 수 있습니다.

지정한 기준일 이하에서 모델 버전과 예측기간이 일치하는 가장 최근 예측 시점을 고릅니다.
그 최신 배치의 점수가 결측이어도 과거 배치 점수로 대체하지 않습니다. 계획은 기준일
이하에서 설비·부품별 마지막 행을 고르고 `plan_as_of`로 원래 날짜를 보존합니다.

## 우선순위 계산

계획 상태는 F02가 준 `status`를 우선 사용합니다. 상태가 없을 때는 대응 여유 음수면
`late`, 재고가 없고 발주 마감일이 지났으면 `order_due`, 재고가 없고 계획 기록이 있으면
`watch`, 재고 정보가 있으면 `covered`로 추론합니다.

정렬 키는 다음 순서입니다.

1. `late` > `order_due` > `watch` > `covered` (계획 없음은 기본 점수 그룹).
2. 같은 상태 안에서는 고장 위험 점수 내림차순.
3. 동점은 `machineID`, `component` 오름차순으로 고정.

선택 상태에 따른 문구는 일정 회복, 발주 확인, 발주 준비 또는 설비 점검입니다.
같은 조건 내에서 보정 점수와 미보정 점수가 섞이면 비교를 거부합니다. 점수가 보정된
경우에만 확률로 표시하고, 미보정 값은 원래 점수 스케일로 표시합니다.

## 실행

기본 `requirements.txt` 설치 후 템플릿 방식은 외부 모델 없이 실행됩니다.

```powershell
python -m src.F03 --as-of 2015-12-28 --horizon-days 7 --model-version fp_v1 --backend template
python -m src.F03 --as-of 2015-12-28 --horizon-days 7 --model-version fp_v1 --backend qwen --model Qwen/Qwen3-1.7B
```

`--maintenance-plan path/to/maintenance_plan.csv`로 계획 파일을 추가할 수 있습니다.
Qwen 사용 시 `python -m pip install -r src/ai_summary/requirements.txt`가 필요합니다.
`--device cuda:0`은 GPU를 지정하고 `--local-files-only`는 로컬 가중치만 사용합니다.

## Python API

```python
from src.F03 import build_summary
from src.ai_summary import QwenSelector

selector = QwenSelector("Qwen/Qwen3-1.7B", device="cpu")
result = build_summary(predictions, "2015-12-28", horizon_days=7,
                       model_version="fp_v1", maintenance_plan=plan,
                       selector=selector)
print(result["text"])
```

`selector=None`이면 결정론적 템플릿만 씁니다. 결과에는 요약문, 선택 설비/부품,
선택된 예측 시점, 상태, 근거, backend와 대체 사유 등이 들어갑니다. Qwen은 허용된
근거 ID를 선택할 뿐이며, 실제 문장은 선택한 근거 원문을 조합해 만듭니다. 로딩 실패나
잘못된 응답은 템플릿으로 대체되고 `backend` 및 `fallback_reason`으로 구분됩니다.

## 해석 시 주의

우선순위는 실행 가능한 고정 규칙이지 비용 최적화나 임상/공학적 판정이 아닙니다.
고장 위험 기간을 정확한 고장 날짜로 바꾸지 않으며, 센서 이상 점수는 입력하지 않습니다.
조회 기준일과 실제 예측 생성일은 다를 수 있으므로 화면이나 보고서에 둘 다 표시하세요.
