# 추가 구축할 운영 데이터

CSV는 입력 양식만 준비했으며 데이터 행은 없습니다. 부품 이름이나 조달기간을 임의로 확정하지 않습니다. `value_source`에는 `assumption:설명` 또는 `measured:근거`를 기록합니다.

| 파일 | 관리 내용 | 식별 키 |
| --- | --- | --- |
| part_master.csv | 부품별 조달기간, 준비시간, 목표재고, 입고 후 사용 가능 기간 | component |
| inventory_lots.csv | 입고 로트별 보유·예약 수량, 입고 시각, 사용 기한, 품질 상태 | lot_id |
| purchase_orders.csv | 발주 시점, 입고 예정·실제 시점, 주문 수량과 상태 | order_id |
| maintenance_records.csv | 계획·완료 정비, 사용 로트와 수량, 결과 | record_id |
| costs.csv | 구매·발주·정비·보유·폐기·정지 등 비용과 단위 | component, cost_type |

`component`는 Azure의 comp1~comp4와 대응합니다. 입고 시각은 교체 이력에서 가져오지 않습니다. 날짜는 ISO 8601을 사용하고 시간대가 알려지지 않은 값은 임의 변환하지 않습니다.

`shelf_life_policy`는 `days_after_receipt`, `no_limit`, `unknown` 중 하나입니다. `days_after_receipt`일 때만 `shelf_life_days`를 채웁니다. 예시의 산화 방지를 위한 입고 후 30일 사용 제한은 가정이며 현재 파일에는 넣지 않았습니다. 실제 입고 시각과 사용 가능 기간으로 기한을 계산하고, 누락된 정보를 무제한으로 해석하지 않습니다.

`quantity_reserved`는 `quantity_on_hand`에 포함된 수량입니다. 0 이상이며 보유량을 넘을 수 없습니다. 품질 상태 `available`, `quarantined`, `unknown`과 기한을 함께 확인해 가용재고를 결정합니다. 비용의 `unit`은 `per_order`, `per_unit`, `per_event`, `per_day`, `per_unit_day` 등으로 명시합니다.
