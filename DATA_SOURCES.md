# 데이터 출처 기록

아래는 설계서에 필요한 데이터의 확보 현황입니다. Azure PdM은 다운로드와 기본 검사를 완료했으며, 나머지 데이터는 아직 확보하지 않았습니다. 라이선스를 임의로 추정하지 않습니다.

현재 작업 데이터는 Azure PdM입니다. 아래 에너지·AI4I 항목은 초기 계획의 기록으로 남겨두며, 해당 행의 저장 폴더는 이전 계획 경로입니다. 실제 데이터가 없던 해당 폴더들은 정리했습니다.

| 분석 트랙 | 데이터 | 원 URL | 접근일 | 라이선스·이용 조건 | 실제 파일명 | 저장 폴더 | 상태 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 에너지 | 제공 전력·생산 데이터 | 제공 경로 기록 예정 | 미확인 | 미확인 | integrated_energy_project.csv (설계서 기준) | data/raw/energy/ | 미확보 |
| 에너지 | 제공 기상 데이터 | 제공 경로 기록 예정 | 미확인 | 미확인 | 확인 예정 | data/raw/weather/ | 미확보 |
| 에너지 | 공공데이터포털 전력 데이터 또는 한국전력공사 지역별 전력판매량 | 실제 선택한 원 URL 기록 예정 | 미확인 | 미확인 | 확인 예정 | data/raw/public_power/ | 미선정 |
| 예지보전 | Kaggle Predictive Maintenance Dataset (AI4I 2020) | 실제 사용한 Kaggle 원 URL 기록 예정 | 미확인 | 미확인 | 확인 예정 | data/raw/ai4i/ | 미확보 |
| 예지보전 확장 | Microsoft Azure Predictive Maintenance | [Kaggle 배포본](https://www.kaggle.com/datasets/arnabbiswas1/microsoft-azure-predictive-maintenance) | 2026-09-21 | 데이터 라이선스·재배포 조건 미확인 | PdM_telemetry.csv, PdM_errors.csv, PdM_maint.csv, PdM_failures.csv, PdM_machines.csv | data/raw/azure_pdm/ | 다운로드·기본 검사 완료 |

## Azure PdM 확보 기록

- 실제 다운로드: https://www.kaggle.com/api/v1/datasets/download/arnabbiswas1/microsoft-azure-predictive-maintenance
- 기존 원본 주소: `https://azuremlsampleexperiments.blob.core.windows.net/datasets/PdM_telemetry.csv` 등. 이번 환경에서는 DNS 조회에 실패하여 Kaggle 배포본을 사용했습니다.
- [Microsoft의 해당 100대 설비 예제 노트북](https://github.com/microsoft/sqlworkshops/blob/master/SQLServerAndAzureMachineLearning/ML%20Services%20for%20SQL%20Server/notebooks/Predictive%20Maintenance%20in%20Python%20Notebook.ipynb)의 Problem Description은 데이터가 시뮬레이션으로 생성되었다고 명시합니다. 실제 R2R 공장의 실측 자료로 표현하지 않습니다.
- 원본 CSV는 ZIP에서 추출한 그대로 보관했으며 컬럼명 변경, 행 삭제, 날짜 보정은 하지 않았습니다.
- 파일별 SHA-256, 바이트 수, 행·열, 날짜 범위, 고장 집계: [검사 결과 JSON](reports/tables/azure_pdm_profile.json).
- 모든 파일에서 빈 필드와 검사 기준 중복 키가 0건입니다. 센서 물리 범위, 전체 시간 간격, 파일 간 참조 무결성, 예측 가능성까지 검증한 것은 아닙니다.
- 중복 키 기준: telemetry는 `(datetime, machineID)`, machines는 `machineID`, 이벤트 파일은 전체 컬럼입니다. 서로 다른 부품의 동시 고장은 별개 기록입니다.
- 센서 CSV의 실제 컬럼은 `volt`, `rotate`, `pressure`, `vibration`입니다. 설명에 쓰인 voltage/rotation과 이름이 다릅니다.
- 공개 원본과 프로젝트에서 가정하는 조달·비용 조건은 별도로 관리합니다. 운영조건은 고장예측 학습 입력에 섞지 않습니다.
- 부품별 조달기간·목표 예비재고·입고 후 사용 가능 기간·보관 제약과 로트별 재고·입고일은 원본 CSV에 없습니다. 별도 기준정보·재고 기록으로 관리하며, 가정한 값은 표시합니다. `산화 이슈로 입고 후 30일 이내 공정 투입`은 사용자 제안의 시나리오 예시이며 comp2의 실제 사양이 아닙니다. 사용 기한은 실제 입고 시각을 기준으로 계산하고, 기한 정보가 없으면 `기한 확인 필요`로 표시합니다. `PdM_maint.csv`의 교체일을 입고일로 간주하지 않습니다.
- 다운로드 재현 방법과 분석 설계: [Azure PdM 안내](docs/AZURE_PDM_GUIDE.md).

## 데이터별 추가 기록 양식

각 데이터 확보 후 아래 항목을 복사하여 작성합니다.

- 데이터명 / 제공 기관 / 담당자:
- 원 URL / 접근일 / 라이선스 / 재배포 가능 여부:
- 원본 파일명 / 저장 위치 / 버전 또는 SHA-256:
- 기간 / 시간 단위 / 지역·공장·설비 범위:
- 행·열 수 / 주요 컬럼 / 단위 / 타깃:
- 결측·중복·범위·자료형 검사 결과:
- 가공 코드 또는 노트북 경로:
- 가공 과정 / 처리 전후 행 수 / 처리 근거:
- 생성한 가공 파일 경로:
- 결합 키 / 집계 단위 / 시간 정렬 기준 (에너지 트랙):
- 예측 시점의 기상 변수 확보 가능 여부:
- 데이터 및 분석의 한계:

에너지 데이터와 AI4I 데이터는 행 단위로 결합하지 않고 독립적으로 분석합니다.
