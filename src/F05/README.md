# F05 · 설비 종합 진단

선택 설비의 같은 기간·모델 버전에서 부품별 고장 위험을 비교하고, F06의 센서
IF·통계 판정을 별도 근거로 받아 한 문장으로 종합합니다. Qwen은 설명에 사용할
근거를 고르며, 점수와 판정은 기존 분석 결과를 그대로 사용합니다.

```python
from src.F05 import build_diagnosis
from src.ai_summary import QwenSelector

result = build_diagnosis(predictions, machine_id=1, as_of="2015-12-21",
                         horizon_days=28, model_version="fp_v1",
                         anomaly=f06_result, selector=QwenSelector())
print(result["text"])
```

미보정 모델 점수는 확률로 표시하지 않습니다. 기간 내 고장 위험으로 정확한
고장 날짜를 만들지 않습니다. 센서 IF 경고와 부품 고장 위험 사이의 인과관계도
단정하지 않습니다. 설비 상세 화면은 `src/ui/ai_data.py`를 통해 같은 Qwen
인스턴스를 F03과 F05에서 재사용합니다. F06은 LLM 없이 센서 판정만 계산합니다.
