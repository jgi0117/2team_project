# 설비 예지보전·정비 의사결정 프로젝트

Azure PdM 공개 예제 데이터로 고장을 예측하고, 가상 조달기간·재고·비용 조건을 적용해 경제적인 경고·정비 정책을 비교하는 프로젝트입니다.

현재 저장소는 **설계 문서와 기본 디렉토리가 준비된 상태**입니다. 2026-09-21에 예지보전 확장 검토용 Azure PdM 공개 데이터 5종을 `data/raw/azure_pdm/`에 다운로드하고 기본 품질 검사를 완료했습니다. 원본 CSV는 Git에서 제외됩니다. 모델, 예측 성능 결과, 실행 가능한 Dash 앱은 아직 포함하지 않습니다.

현재 분석 방향은 **Azure PdM + 가상 조달·비용 조건을 이용한 경고 시점 평가**입니다. 기존 에너지·AI4I 전용 빈 폴더와 임시 다운로드·미리보기 폴더는 정리했습니다. 원본 PDF와 초기 설계서는 참고 이력으로 보관하며, 새 데이터의 사용 방법과 한계는 [Azure PdM 분석 안내](docs/AZURE_PDM_GUIDE.md)를 참고합니다.

## 프로젝트 문서

- [원본 프로젝트 개요 및 설계서](docs/프로젝트_개요_및_설계서_Kaggle반영.pdf)
- [초기 프로젝트 정의 및 요구사항](docs/PROJECT_SPEC.md)
- [초기 수행 단계와 제출 체크리스트](docs/WORK_PLAN.md)
- [데이터 출처 기록](DATA_SOURCES.md)
- [Azure PdM 설명·다운로드 방법](docs/AZURE_PDM_GUIDE.md)
- [Azure PdM 원본 검사 결과](reports/tables/azure_pdm_profile.json)

## 디렉토리 구조

```text
2team_project/
├── docs/                       # 원본 PDF, 프로젝트 정의, 수행 계획
├── data/
│   ├── raw/
│   │   └── azure_pdm/          # Azure PdM 공개 예제 CSV 5종 (로컬)
│   └── processed/             # 향후 특징·타깃 등 가공 결과
├── notebooks/
│   └── maintenance/            # Azure PdM EDA, 예측·비용 분석
├── src/
│   ├── common/                 # 공통 경로·입출력·품질 검사
│   └── maintenance/            # 전처리, 고장예측, 비용 시뮬레이션
├── app/
│   ├── pages/                  # 설비·고장예측·정비 의사결정 화면
│   ├── components/             # 공통 필터, 표, 그래프
│   └── assets/                 # CSS, 이미지
├── configs/                    # 컬럼, 경로, 모델 설정
├── models/
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
3. Azure PdM의 설비별 시계열·정비·고장 이력을 탐색하고 특징·타깃을 생성합니다.
4. 기간별 고장예측을 시간순으로 평가하고, 별도 운영조건으로 비용 시뮬레이션을 수행합니다.
5. `app/`에 Dash 앱을 구현하고 보고서·발표자료를 작성합니다.

## 브랜치

`main`은 통합 브랜치이며 `GJ`, `GE`, `JH`는 팀원별 작업 브랜치입니다. 현재 데이터 준비와 폴더 정리는 `GJ`에서 진행했으며 다른 브랜치에 통합하지 않았습니다. 담당 분석 영역은 아직 배정하지 않았습니다.

```powershell
git switch GJ
# 작업 후 커밋하고 본인 브랜치에 푸시
git push -u origin GJ
```

공통 변경은 팀 검토 후 `main`에 통합합니다. 데이터 경로는 저장소 기준 상대 경로를 사용합니다.
