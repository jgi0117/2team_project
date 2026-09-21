# 스마트 에너지·설비 예지보전 통합 프로젝트

전력·생산·기상 데이터를 이용한 에너지 분석과 Kaggle AI4I 2020 설비 고장 분석을 수행하고, 결과를 Plotly·Dash 대시보드로 통합하는 40시간 팀 프로젝트입니다.

현재 저장소는 **설계 문서와 기본 디렉토리만 준비된 상태**입니다. 실제 데이터, 모델, 분석 결과, 실행 가능한 Dash 앱은 아직 포함하지 않습니다.

## 프로젝트 문서

- [원본 프로젝트 개요 및 설계서](docs/프로젝트_개요_및_설계서_Kaggle반영.pdf)
- [프로젝트 정의 및 요구사항](docs/PROJECT_SPEC.md)
- [수행 단계와 제출 체크리스트](docs/WORK_PLAN.md)
- [데이터 출처 기록](DATA_SOURCES.md)

## 디렉토리 구조

```text
2team_project/
├── docs/                       # 원본 PDF, 프로젝트 정의, 수행 계획
├── data/
│   ├── raw/
│   │   ├── energy/             # integrated_energy_project.csv
│   │   ├── weather/            # 제공 기상 데이터
│   │   ├── public_power/       # 공공 전력 데이터
│   │   └── ai4i/               # Kaggle AI4I 2020
│   └── processed/
│       ├── energy/             # 에너지 트랙 전처리 결과
│       └── ai4i/               # 예지보전 트랙 전처리 결과
├── notebooks/
│   ├── energy/                 # 에너지 전처리, EDA, 회귀, Prophet
│   └── maintenance/            # AI4I EDA, 분류, 군집화·이상 탐지
├── src/
│   ├── common/                 # 공통 경로·입출력·품질 검사
│   ├── energy/                 # 에너지 KPI, 회귀, 시계열 코드
│   └── maintenance/            # AI4I 전처리, 분류, 이상 탐지 코드
├── app/
│   ├── pages/                  # 에너지·예측·예지보전·조회·요약 화면
│   ├── components/             # 공통 필터, 표, 그래프
│   └── assets/                 # CSS, 이미지
├── configs/                    # 컬럼, 경로, 모델 설정
├── models/
│   ├── energy/                 # 학습된 에너지 모델 (Git 제외)
│   └── maintenance/            # 학습된 예지보전 모델 (Git 제외)
├── reports/
│   ├── figures/                # 그래프, 혼동행렬
│   ├── tables/                 # KPI, 모델 비교·평가표
│   └── final/                  # 최종 보고서 PDF
├── presentations/              # 최종 발표 자료
├── tests/                      # 향후 전처리·모델·대시보드 검증
├── DATA_SOURCES.md
├── requirements.txt
└── .gitignore
```

빈 디렉토리는 `.gitkeep`으로 추적합니다. 원본·가공 데이터와 학습 모델은 Git에서 제외하며, 파일 준비 방법과 출처는 문서로 공유합니다.

## 작업 시작

저장소 루트에서 Python 가상환경을 만들고 기본 의존성을 설치합니다.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

`requirements.txt`는 설계서에 따른 시작용 목록이며, 전체 패키지 설치 및 호환성 검증은 아직 수행하지 않았습니다. 팀 실행 환경이 정해지면 검증한 버전을 고정합니다.

1. `DATA_SOURCES.md`에 실제 데이터 URL, 접근일, 라이선스, 파일명을 기록합니다.
2. 데이터를 `data/raw/`의 해당 폴더에 준비합니다.
3. 두 트랙의 품질 검사와 EDA를 각각 진행합니다.
4. 에너지 회귀·Prophet, AI4I 분류·비지도 이상 탐지를 구현하고 평가합니다.
5. `app/`에 Dash 앱을 구현하고 보고서·발표자료를 작성합니다.

## 브랜치

`main`은 통합 브랜치이며 `GJ`, `GE`, `JH`는 팀원별 작업 브랜치입니다. 이번 기본 구조는 네 브랜치에 동일하게 반영합니다. 담당 분석 영역은 아직 배정하지 않았습니다.

```powershell
git switch GJ
# 작업 후 커밋하고 본인 브랜치에 푸시
git push -u origin GJ
```

공통 변경은 팀 검토 후 `main`에 통합합니다. 데이터 경로는 저장소 기준 상대 경로를 사용합니다.
