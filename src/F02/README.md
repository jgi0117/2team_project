# F02 · 부품 재고 및 조달 위험 계산

조회 시점의 재고 이동을 재생하고 진행 주문, 조달기간, 정비 준비기간을 반영해
설비·부품별 발주 마감일과 대응 여유를 계산합니다.

```python
from src.F02 import build_plan

plan = build_plan("2015-12-21")
```

대시보드 수치의 변화 과정을 설명할 때는 `data/processed/procurement_history.csv`와
`data/processed/inventory_daily_history.csv`를 사용합니다. 두 파일은 기존 운영 이벤트를
시점 순서로 재생해 생성하며 원본 CSV를 수정하지 않습니다.
