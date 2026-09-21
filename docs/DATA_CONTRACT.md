# 기능 간 데이터 계약

이 문서는 기능별 병렬 개발을 위한 예정 규약입니다. 구현 전 담당자 간 변경 내용을 합의하며, 아직 없는 예측 결과를 채워 넣지 않습니다.

## 공통 키와 시간

- `machineID`: Azure 원본 설비 ID. 화면 표시용 M-023 등과 내부 키를 구분합니다.
- `component`: comp1, comp2, comp3, comp4. 원본의 comp 및 failure를 이 이름으로 정규화합니다.
- `as_of`: 조회·예측 기준시점. 원본 시간대가 미확인이므로 임의로 한국 시간으로 변환하지 않습니다.
- 부품 기준정보는 component로, 로트·발주·정비 기록은 해당 고유 ID로 연결합니다.

## 가상 운영 데이터의 시점별 조회

`data/operations/`는 2015-04-01 06시~2016-01-01 06시의 재고 기준 정책을 재생한 합성 데이터입니다. 초기 조건은 이전 90일의 교체 수요로 설정했습니다. `inventory_lots.csv`의 수량·상태와 주문·정비 결과는 최종시점 기준이므로 과거 예측 입력에 그대로 조인하지 않습니다. `src.maintenance_planning.operations_snapshot.snapshot(as_of)`로 해당 시점까지의 상태를 조회합니다.

- `inventory_lots.csv`에 `order_id`, `quantity_received`, `ready_at`, `as_of`를 추가했습니다. 시점별 가용 수량은 조회 함수의 `quantity_available`을 사용합니다.
- `inventory_movements.csv`의 `occurred_at`, `quantity_delta`, `quality_status`로 과거 재고를 복원합니다. 이번 정책은 선예약 없이 필요 시 즉시 출고하므로 예약량은 0입니다.
- `maintenance_records.csv`에 `source_event_at`, `quantity_requested`를 추가했습니다. 원본 교체 시점은 수요 관측 시점이며 `completed_at`은 가상 공급 정책의 완료 결과입니다. 둘을 원본 학습 이력에서 혼용하지 않습니다.
- `planned_at`은 이번 기준 정책에서 수요 접수 시점입니다. 미리 아는 고장일이나 예측 기반 정비 계획일을 의미하지 않습니다.
- 미래 실제 입고·완료 결과는 조회 함수가 숨깁니다. 미래 입고 예정일은 당시 알려진 주문 정보이므로 유지합니다.
- `costs.csv`의 작업비는 부품 구매비를 포함하지 않습니다. 보유비는 개·일, 정지 손실은 일 단위입니다. 모든 단가와 기한은 시나리오 가정입니다.

구체적인 수치 근거와 재현 명령은 [운영 데이터 안내](../data/operations/README.md)를 따릅니다.

## 결과 파일 규약

| 결과 파일 | 한 행의 단위 | 필수 필드 |
| --- | --- | --- |
| features.csv | 설비·부품·예측시점 | machineID, component, as_of 및 합의한 특징 열 |
| labels.csv | 설비·부품·예측시점·예측기간 | machineID, component, as_of, horizon_days, failure_within_horizon, observation_complete |
| predictions.csv | 설비·부품·예측시점·예측기간 | machineID, component, as_of, horizon_days, failure_probability, model_version |
| model_metrics.csv | 모델·예측기간·평가구간·지표 | model_version, horizon_days, split, metric, value |
| maintenance_plan.csv | 설비·부품·판단시점 | machineID, component, as_of, priority, target_maintenance_at, available_stock, expected_receipt_at, order_by_at, response_margin_days, status, reason |
| statistics.csv | 평가기간·설비·부품·지표 | period_start, period_end, machineID, component, metric, value, denominator |

미확정 날짜는 빈 값으로 두고 status와 reason에 이유를 기록합니다. 미확정 값을 0이나 오늘 날짜로 채우지 않습니다. 총계의 machineID 또는 component는 `ALL`을 사용합니다. predictions의 확률은 0~1이며 화면에서만 백분율로 변환합니다.

## 예측과 대응 판단

1. 예측 시점 이전 센서·이력만 특징에 사용합니다. 미래 정보는 정답 생성용이며 학습·검증·테스트 시간 경계를 넘는 라벨은 제거합니다.
2. 기간 내 고장 확률을 정확한 고장 날짜로 바꾸지 않습니다. 별도 검증한 시점 추정 모델이 있으면 예상 구간·불확실성을 확장 필드로 추가합니다.
3. 목표 정비일은 계획값입니다. 신규 조달 시 `발주 마감일 = 목표 정비일 - 조달기간 - 정비 준비시간`으로 판단합니다. 재고·진행 중 주문이 있으면 해당 확보 시점을 반영합니다.
4. `대응 여유 = 목표 정비일 - 준비 완료 예정일`이며 음수는 지연 위험입니다. 목표 정비일이 없으면 대응 여유도 확정하지 않습니다.
5. 로트는 준비 완료 이후, 사용 기한 이전에 투입할 수 있어야 합니다. 기한 초과·격리·예약 수량을 가용 수량에 중복 포함하지 않습니다. 확인 가능한 로트 중 기한이 빠른 것을 우선 배정합니다.
6. 통계의 대응률은 평가기간과 분모를 함께 저장합니다. 고장 행 수, 경고 횟수, 설비 수를 혼용하지 않습니다.

기획서 화면의 예시 확률·건수·날짜는 실제 모델 결과가 아닙니다. 운영조건과 비용의 근거는 별도 운영 CSV에 기록합니다.
