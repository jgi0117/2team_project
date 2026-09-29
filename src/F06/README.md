# F06 · 시간별 센서 이상 분석

## 목적과 입력

선택 설비의 최근 센서 시계열을 바탕으로 3-Sigma/IQR 통계 이탈과 저장된 Isolation
Forest(IF) 결과를 시간별로 나란히 보여줍니다. 고장 예측은 F05가 별도로 다루며 F06은
LLM을 호출하지 않고 수치와 판정만 반환합니다.

필수 센서 열은 `volt, rotate, pressure, vibration`입니다. 시간 열은 `datetime` 또는
`as_of`이며 `machineID`와 함께 필요합니다. IF 입력은 `machineID, as_of, anomaly_score,
threshold, is_anomaly`를 포함합니다.

## 통계 계산

조회 시점 이하에서 선택 설비의 마지막 관측을 `observed_at`으로 고릅니다. 기본
`window_hours=72`이며 마지막 기준선 시작부터 관측 시점까지의 시간별 추이를 반환합니다.
각 시간 t의 통계 기준선은 같은 설비에서 t보다 앞선 `[t - window_hours, t)` 관측만
사용합니다. 따라서 t의 현재 센서값 및 미래 데이터는 기준선에 들어가지 않습니다.

각 센서별로 기준선에 필요한 모든 시간 관측과 센서 값이 있을 때에만 계산합니다.

- 평균과 표준편차: `mean`, 모집단 표준편차 `std(ddof=0)`.
- 3-Sigma 범위: `[mean - 3 × std, mean + 3 × std]`.
- 사분위 범위: `IQR = Q3 - Q1`.
- IQR 탐지 범위: `[Q1 - 1.5 × IQR, Q3 + 1.5 × IQR]`.
- 현재 값이 범위보다 엄격히 작거나 크면 이상입니다. 경계와 같은 값은 이상이 아닙니다.

기준선이 불완전하거나 현재 센서값이 비면 상태를 미확정으로 둡니다. 표준편차 또는
IQR가 0인 경우도 0 폭의 범위와 직접 비교하고 `constant_baseline`/`zero_iqr`로
표시합니다. 임의 epsilon을 더해 점수를 만들지 않습니다.

## IF 결과와 결과 구조

IF CSV에서 같은 설비 및 정확히 같은 관측시각의 행만 연결합니다. `is_anomaly`가
`anomaly_score > threshold`와 일치하는지 검증합니다. 저장 결과에 센서 원값이 포함되어
있으면 선택한 telemetry와 값이 맞는지도 확인합니다. IF는 여러 센서 특징에 대한
설비 단위 탐지이므로 특정 센서의 원인을 말해주지 않습니다.

- `sensors`: 마지막 관측의 센서값, 기준선 크기/범위, 3-Sigma/IQR 판정 및 상태.
- `timeline`: 관측 구간 각 시각의 센서 통계와 해당 시각 IF 결과.
- `trend`: 실제로 관측된 원본 센서값. 결측을 보간하지 않습니다.
- `if`: 마지막 관측의 IF 점수, 저장 임계값 및 경고 여부. 생략 입력이면 `null`.
- `observation_age_hours`: 조회 기준시각과 마지막 관측의 시간 차.
- `status`: 모든 센서 통계가 준비되고 IF가 연결되면 `ok`, 일부 정보만 있으면
  `partial`, 관측 자체가 없으면 `no_data`.

## 실행 방법

```powershell
python -m src.F06 --machine-id 1 --as-of "2015-12-28 06:00:00" --if-predictions outputs/model3/predictions.csv
```

기본 telemetry는 `data/raw/azure_pdm/PdM_telemetry.csv`, 기본 창은 72시간입니다.
IF 파일을 생략하면 통계 분석만 수행합니다. Python에서는
`analyze_equipment(telemetry, machine_id, as_of, if_predictions=..., window_hours=72)`를
호출할 수 있습니다.

## 시각화와 한계

UI는 센서 원값과 IQR/3-Sigma 경계를 위 그래프에, 설비 IF 점수/저장 임계값을 아래
그래프에 표시합니다. IQR 상·하한은 UDL/LDL, 3-Sigma 한계는 UCL/LCL로 표시합니다.
이 범위는 해당 과거 구간의 통계 기준이지 검증된 정상 운전 한계가 아닙니다. 센서 이상은
고장 확률, 고장 원인, 인과관계 또는 설비 고장을 뜻하지 않습니다.

## 검증

```powershell
python -m unittest discover -s tests -p test_f03_f06.py -v
```

테스트는 미래 정보와 현재 관측의 기준선 제외, 결측/일정 기준선, IF 시점 및 임계값
일치를 확인합니다.
