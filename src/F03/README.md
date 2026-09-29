# F03 · 고장 위험 기반 한 줄 대응 요약

기존 고장 예측과 재고·조달 계획을 받아 현재 우선 확인할 대응을 한 문장으로
제공합니다. Dash와 독립적인 Python API/CLI입니다.

## 실행

프로젝트 루트에서 기본 `requirements.txt`를 설치합니다. Qwen을 사용할 때는
추가로 `python -m pip install -r src/ai_summary/requirements.txt`를 실행합니다.

```powershell
python -m src.F03 --as-of 2015-12-28 --horizon-days 7 --model-version fp_v1 --backend template
python -m src.F03 --as-of 2015-12-28 --horizon-days 7 --model-version fp_v1 --backend qwen --model Qwen/Qwen3-1.7B
```

`--maintenance-plan path/to/maintenance_plan.csv`로 계획을 추가합니다.
`--device cuda:0`으로 GPU를 지정할 수 있습니다. 기본은 CPU이며 최초 Qwen
실행 시 Hugging Face에서 가중치를 다운로드합니다. `--local-files-only`는
이미 내려받은 모델만 사용합니다. 더 작은 비교 모델은 `Qwen/Qwen3-0.6B`입니다.

## 입력과 동작

- 예측: `machineID, component, as_of, horizon_days, failure_probability, model_version`.
  `calibrated`가 없거나 false이면 미보정 점수로 표시하며 백분율로 바꾸지 않습니다.
- 계획: `machineID, component, as_of`와 선택 열
  `available_stock, order_by_at, response_margin_days`.
- 지정 모델·예측기간에서 조회시점 이전의 가장 최근 예측 배치를 사용합니다.
  계획은 각 설비·부품의 마지막 알려진 행을 사용하며 원래 시점을 반환합니다.
- 대응 여유 음수, 발주 마감 경과, 고장 위험 점수 순으로 우선순위를 정합니다.
  이 정책은 최초 구현용 규칙이며 비용 최적화 결과를 대신하지 않습니다.
- 미보정 점수와 보정 확률을 함께 순위 매기지 않습니다. 미확정 재고/날짜를
  0이나 오늘 날짜로 채우지 않으며, 계획이 없으면 정보 미제공으로 표시합니다.
- 고장 확률로 고장 날짜를 계산하지 않습니다. 센서 이상 점수도 입력하지 않습니다.

## Python API와 결과

```python
from src.F03 import build_summary
from src.ai_summary import QwenSelector

selector = QwenSelector("Qwen/Qwen3-1.7B", device="cpu")  # 인스턴스 재사용
result = build_summary(predictions, "2015-12-28", horizon_days=7,
                       model_version="fp_v1", maintenance_plan=plan,
                       selector=selector)
print(result["text"])
```

`selector=None`은 모델 없이 실행합니다. 결과는 `text`, `selected`,
`prediction_as_of`, `backend`, `fallback_reason`, `evidence` 등을 포함합니다.
조회시점과 예측시점은 다를 수 있으므로 화면 연동 시 원래 시점도 표시해야 합니다.

Qwen은 확정된 핵심 대응에 덧붙일 근거 ID를 선택합니다. 문장은 선택된 원문을
조합합니다. 이 방식은 모델이 수치·날짜·조치를 임의로 추가하지 못하게 합니다.
모델 로딩 실패나 유효하지 않은 응답은 `backend=template` 및 실패 종류를
반환하고 결정론적 요약으로 대체합니다. Qwen 실행 성공과 대체 출력을 구분합니다.
