# F06 · 시간별 센서 이상 분석

설비의 시간별 센서 관측, IF 결과, 3-Sigma/IQR 이탈을 비교합니다. 고장 예측은
F05의 별도 입력입니다. 센서 이탈을 고장 확률이나 물리적 고장 원인으로 바꾸지 않습니다.
F06은 LLM을 호출하지 않고 수치와 판정만 반환합니다. Dash와 API/CLI에서 사용할 수 있습니다.

## 실행

```powershell
python -m src.F06 --machine-id 1 --as-of "2015-12-28 06:00:00" --if-predictions outputs/model3/predictions.csv
```

`--telemetry`는 기본 `data/raw/azure_pdm/PdM_telemetry.csv`, `--window-hours`는
기본 72입니다. IF 결과를 생략하면 통계 분석만 수행하고 IF 값은 `null`로 둡니다.

## 분석 기준

- 조회시점 이전의 마지막 관측 t를 선택합니다. `observed_at`과 관측 경과시간을 반환합니다.
- 최근 72시간의 각 시각 t에 대해 같은 설비의 `[t-72시간, t)`를 기준선으로 사용합니다.
  현재 관측과 미래 데이터는 제외합니다.
- 매시간 관측과 해당 센서 값이 모두 있어야 통계 판정합니다. 결측은 판정 미확정입니다.
- 3-Sigma: 평균 ± 3 × 모집단 표준편차(`ddof=0`).
- IQR: Q1 − 1.5 × IQR ~ Q3 + 1.5 × IQR. 경계값과 같으면 이탈이 아닙니다.
- 기준선 분산/IQR가 0이면 해당 사실을 결과에 표시하고 축소된 범위와 직접 비교합니다.
  0으로 나누거나 임의 epsilon으로 점수를 증폭하지 않습니다.
- IF는 기존 `src/model3`의 저장 결과를 읽습니다. 같은 설비·관측시점만 연결하고
  `anomaly_score > threshold`와 저장된 판정이 일치하는지 확인합니다.
- IF는 여러 센서 특징을 이용한 별도 탐지입니다. 3-Sigma/IQR 이탈 센서가
  IF 판단의 원인이라고 단정하지 않습니다. 과거 기준선도 검증된 정상 구간은 아닙니다.

## Python API와 결과

```python
from src.F06 import analyze_equipment

result = analyze_equipment(telemetry, machine_id=1, as_of="2015-12-28 06:00:00",
                           if_predictions=if_predictions)
```

`telemetry`는 `machineID, datetime`(또는 `as_of`)과
`volt, rotate, pressure, vibration` 열을 받습니다. IF 결과는
`machineID, as_of, anomaly_score, threshold, is_anomaly` 열을 받습니다.

결과의 `timeline`에는 시간별 센서 3-Sigma/IQR 판정과 설비 전체 IF 판정이 들어갑니다.
과거 기준선이 모자라거나 관측이 없으면 해당 시각은 미판정으로 표시합니다.
`sensors`에는 마지막 시점의 센서별 실제 값·기준 범위·판정·결측 상태가 들어갑니다.
`trend`는 관측 구간의 원래 센서값이며 보간하지 않습니다. 마지막 시점의 `if`와
`interpretation`도 제공합니다. 화면은 선택한 센서값과 IQR·3-Sigma 경계를
상단 선그래프에, 설비 전체 IF 점수·경고 기준을 하단 선그래프에 표시합니다.
IQR의 탐지 상·하한은 화면에서 UDL/LDL, 3-Sigma의 관리 상·하한은
UCL/LCL로 표시합니다. 이상 시점은 빨간 표식으로 구분하고, 이상이 없으면
이상 0건을 명시합니다.

## 검증

```powershell
python -m unittest discover -s tests -p test_f03_f06.py -v
```

미래 정보 제외, 현재 관측의 기준선 제외, 결측/일정한 기준선, IF 시점 일치를 검사합니다.
