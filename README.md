data/
docs/
# 설비 고장 예측 기반 정비 의사결정 지원 시스템

설비별 고장 위험, 센서 이상, 재고·조달·정비 비용을 연결해 점검 우선순위와 발주·정비 시점 결정을 지원합니다. 고장 예측을 실제 대응 계획으로 연결하는 것이 핵심입니다.

## 프로젝트 개요

- 대상: Azure Predictive Maintenance 시뮬레이션의 설비 100대와 부품 `comp1`~`comp4`
- 외부 데이터: 센서 telemetry, 오류, 정비, 고장, 설비 마스터
- 내부 구축 데이터: 부품·협력사·재고·발주·정비·비용을 표현한 합성 운영 시나리오
- 화면: 메인 대시보드, 설비 상세, 통계, 발주
- 운영 DB: MySQL `dashboard`; `DB_ENABLED=false`이면 DB 읽기·쓰기·인증을 사용하지 않음

원본 Azure 데이터는 실제 공장 실측이 아닌 공개 시뮬레이션 데이터입니다. 재고·발주·비용 데이터도 실적이 아니라 가정에 기반한 합성 데이터입니다. 원본 데이터의 라이선스와 재배포 조건은 [데이터 안내](data/README.md)를 확인하세요.

## 데이터와 분석

| 데이터 | 행 수 | 활용 |
| --- | ---: | --- |
| `PdM_machines.csv` | 100 | 설비 모델·연령 |
| `PdM_telemetry.csv` | 876,100 | 시간별 전압·회전속도·압력·진동 |
| `PdM_errors.csv` | 3,919 | 오류 종류·시점, 과거 오류 특징 |
| `PdM_maint.csv` | 3,286 | 부품 교체 이력·교체 후 경과일 |
| `PdM_failures.csv` | 761 | 고장 부품·발생 시점 및 정답 라벨 |

고장 위험 예측은 원본 검사, 일 단위 센서 요약, 이동 통계와 이력 특징 생성, 미래 고장 라벨 생성을 거칩니다. 입력은 판단 시점 전까지의 정보만 사용하고 정답은 이후 예측 기간의 고장 여부로 만듭니다. 최근 발표자료의 EDA에서는 센서 분포와 고장 전 변화, 모델별 설비 연령, 오류·정비 유형, 반복 고장 간격을 비교했습니다.

센서 이상 탐지는 telemetry만 사용합니다. 직전 6·24·72시간의 센서 특징 44개를 만들고, 이력이 충분한 시점만 시간 순으로 학습·시험 구간에 나눕니다. 검증된 이상 정답 라벨은 없으므로 이상 점수는 고장 확률로 해석하지 않습니다.

## 모델과 결과

고장 위험 예측은 부품별·기간별 분류 문제이며 LightGBM을 사용합니다. 발표자료의 동일 조건 비교에서는 79개 입력 변수를 사용한 학습/시험 데이터에서 Random Forest의 평균 AUC가 0.830, LightGBM이 0.826이었고, 학습 시간은 각각 2.5초와 1.0초로 보고되어 재학습 속도를 고려해 LightGBM을 선택했습니다. 이는 발표자료의 해당 실험 결과이며 데이터나 실행환경에 따라 달라질 수 있습니다.

Isolation Forest는 라벨 없는 센서 패턴을 다변량으로 탐지하는 보조 신호입니다. 발표자료는 실제 이상 라벨 대신 경고율, 고장 전 탐지율과 lift 등 운영 대리 지표로 비교합니다. 경고 점수는 확률이 아니며 특정 고장 원인을 뜻하지 않습니다.

## 기능

| ID | 기능 | 역할 |
| --- | --- | --- |
| F01 | 설비 이상 및 고장 위험 탐지 | 위험 상승과 우선 확인 설비 표시 |
| F02 | 부품 재고 및 조달 위험 계산 | 가용 재고·조달기간·준비기간으로 발주 마감과 대응 여유 계산 |
| F03 | AI 한 줄 대응 요약 | 위험 및 운영 계획을 한 문장으로 요약 |
| F04 | 대응 이력 및 성과 추적 | 예방 대응률과 과거 조치 추이 제공 |
| F05 | 부품별 고장 위험 예측 | 설비 내 부품 위험과 예측 기간 비교 |
| F06 | 센서 이상 및 위험 근거 분석 | Isolation Forest, 3-Sigma, IQR 신호를 함께 확인 |
| F07 | 최적 발주 시점 및 비용 분석 | 발주 지연별 구매·보유·긴급·정지 비용 시나리오 비교 |
| F08 | 담당자 및 조치 이력 관리 | 협력사, 발주 품목, 정비 이력 확인 및 관리 |
| F09 | 설비별 고장 예측 히트맵 | 설비 간 부품 고장 위험 비교 |
| F10 | 설비별 이상 위험 히트맵 | Isolation Forest 이상 점수 분포 비교 |

## 요구사항

- Windows 64비트
- Python **3.12** (requirements.txt 검증 환경)
- MySQL 및 MySQL 계정 (GE-DB 대시보드를 DB 연결로 실행할 때)
- Qwen 요약을 처음 사용할 때 인터넷 연결과 모델 다운로드 공간 (선택 기능)

## 설치

프로젝트 루트의 PowerShell에서 실행합니다.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

`.env`에 MySQL 연결정보와 충분히 긴 인증·암호화 키를 설정합니다. `.env`에는 비밀번호와 비밀키가 들어가므로 Git에 추가하거나 다른 사람에게 전달하지 마세요. `.env.example`은 설정 형식의 예시이며 실제 접속정보가 아닙니다.

## 데이터베이스 초기화

MySQL 서버를 실행한 뒤, `.env`의 DB 계정에 데이터베이스 생성 권한이 있는지 확인합니다. 최초 생성 또는 CSV 재적재:

```powershell
.\.venv\Scripts\python.exe -m src.ge_db.setup
```

`--rebuild`는 `DB_NAME`으로 지정한 데이터베이스 전체를 삭제하고 다시 만듭니다. 사용자, 로그인 기록, 발주·조치 기록도 삭제되므로 백업 없이 운영 DB에 사용하지 마세요.

자세한 DB 테이블과 초기화 정책은 [GE-DB 안내](src/ge_db/README.md)를 참고하세요.

## 대시보드 실행

```powershell
.\.venv\Scripts\python.exe app.py
```

기본 접속 주소는 `http://127.0.0.1:8050`입니다. 최초 관리자 계정은 서버 PC에서 `http://127.0.0.1:8050/setup`을 열어 생성합니다. 다음 실행부터는 로그인 화면을 사용합니다.

다른 PC에서 같은 사설 네트워크로 접속하려면 서버 `.env`의 `DASH_HOST=0.0.0.0`으로 바꾸고 앱을 재시작한 뒤, Windows 방화벽에서 TCP 8050을 허용합니다. 클라이언트는 `http://서버PC의IPv4주소:8050`으로 접속합니다. MySQL 포트 3306은 클라이언트에 공개하지 말고, DB 연결정보도 공유하지 마세요.

## 모델 실행 및 결과

고장 위험 예측 파이프라인을 순서대로 실행합니다.

```powershell
.\.venv\Scripts\python.exe -m src.failure_prediction.run_all
```

파이프라인은 데이터 검사, 정제, 특징·라벨 생성, LightGBM 학습, 선택적 딥러닝 학습, 결과 통합을 수행합니다. 딥러닝 단계가 실패하면 ML 결과만으로 계속 진행합니다. 주요 산출물은 `data/processed/predictions.csv`, `risk_curve.csv`, `model_metrics.csv`입니다.

센서 이상 탐지 모델은 별도 실행합니다.

```powershell
.\.venv\Scripts\python.exe src/model3/preprocessing.py
.\.venv\Scripts\python.exe src/model3/train.py
```

산출물은 `outputs/model3/isolation_forest.joblib` 및 `outputs/model3/predictions.csv`입니다. `anomaly_score`는 확률이 아닙니다.

## 검증과 문서

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

MySQL 통합 테스트는 DB 초기화 후 실행합니다. 데이터 필드와 예측 입출력 계약은 [DATA_CONTRACT.md](docs/DATA_CONTRACT.md), 데이터 설명은 [data/README.md](data/README.md), 가상 운영 시나리오는 [data/operations/README.md](data/operations/README.md), 화면 명세는 [UI 기능 명세 기획서](docs/UI기능_명세_기획서.pptx)를 참고하세요.
