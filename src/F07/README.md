# F07 · 최적 발주 시점 및 비용 분석

구매비, 발주 행정비, 보유비, 긴급 작업비, 긴급 운송비와 정지 손실을 사용해
발주 지연일별 시나리오 비용과 최소비용 발주 시점을 계산합니다.

```python
from src.F07 import analyze_order

result = analyze_order(1, "comp2", "2015-12-21")
```
