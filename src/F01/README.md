# F01 · 설비 이상 및 고장 위험 탐지

전일 대비 설비 단위 위험 점수 상승 폭을 계산하고, 당일 위험도 상위 5% 설비 중
상승 폭이 큰 TOP3를 제공합니다. 설비 점수는 4개 부품의 동일한 7일 예측 중
가장 높은 값이며 Isolation Forest 이상치 결과는 섞지 않습니다. 미보정 점수는
백분율로 표시하지 않습니다.

```python
from src.F01 import build_detection

result = build_detection("2015-12-21")
```
