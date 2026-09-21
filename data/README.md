# 프로젝트 데이터

## Azure PdM 원본

Microsoft Azure Predictive Maintenance 공개 시뮬레이션 데이터입니다. 2026-09-21에 Kaggle 배포본을 확보했습니다. 원본 CSV를 Git으로 공유하며 변경하지 않습니다.

| 파일 | 행 수 | 주요 컬럼 |
| --- | ---: | --- |
| PdM_machines.csv | 100 | machineID, model, age |
| PdM_telemetry.csv | 876,100 | datetime, machineID, volt, rotate, pressure, vibration |
| PdM_errors.csv | 3,919 | datetime, machineID, errorID |
| PdM_maint.csv | 3,286 | datetime, machineID, comp |
| PdM_failures.csv | 761 | datetime, machineID, failure |

센서는 100대 설비의 2015-01-01 06시~2016-01-01 06시 관측입니다. 정비 이력은 2014-06-01부터 포함합니다. 타임스탬프 시간대는 미확인입니다. 고장은 comp1 192건, comp2 259건, comp3 131건, comp4 179건이며 설비 정지 횟수와 동일하지 않습니다. comp1~comp4의 실제 부품명은 제공되지 않습니다.

빈 필드·검사 키 중복은 0건입니다. 원본 해시·집계·검사 범위는 [manifest.json](manifest.json)에 보존했습니다. 센서 물리 범위나 모델 성능까지 검증했다는 뜻은 아닙니다.

## 추가 구축 데이터

`operations/`에는 부품 기준정보, 로트 재고, 발주, 정비 기록, 비용의 헤더만 있는 CSV 양식을 둡니다. 원본에 없는 값은 추후 근거와 함께 채우며 실제값과 가정을 구분합니다. `processed/`는 전처리·예측·계획·통계 결과 위치입니다. 이 데이터들도 Git 추적 대상입니다.

## 출처

- 배포본: https://www.kaggle.com/datasets/arnabbiswas1/microsoft-azure-predictive-maintenance
- 다운로드: https://www.kaggle.com/api/v1/datasets/download/arnabbiswas1/microsoft-azure-predictive-maintenance
- Microsoft 시뮬레이션 설명: https://github.com/microsoft/sqlworkshops/blob/master/SQLServerAndAzureMachineLearning/ML%20Services%20for%20SQL%20Server/notebooks/Predictive%20Maintenance%20in%20Python%20Notebook.ipynb
- 데이터 라이선스·재배포 조건은 아직 확인하지 않았습니다. 원본 코드 저장소의 라이선스를 자동 적용하지 않습니다.
