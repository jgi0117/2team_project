# F04 · 대응 이력 및 성과 추적

원본 정비·고장 이력으로 1월부터 월별 예방 대응률을 제공합니다. 예방 대응률은
전체 정비 중 고장 발생 전에 수행한 정비의 비율입니다. 가상 운영 결과는
고장예측 모델 학습에 반영하지 않습니다.

```python
from src.F04 import build_tracking

tracking = build_tracking("2015-12-21")
```
