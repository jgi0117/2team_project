# 통합 Dash 대시보드

메인, 설비별, 통계 화면을 하나의 Dash 앱에서 실행합니다. 프로젝트 루트에서 다음 명령을 실행하세요.

```powershell
python -m pip install -r requirements.txt
python -m src.ui.app
```

브라우저에서 `http://127.0.0.1:8050`으로 접속합니다.

새 컴퓨터에서는 64비트 Python 3.12 가상환경과 인터넷 연결이 필요합니다.
F03 또는 F05를 처음 요청할 때 공개 Qwen3-1.7B의 가중치·토크나이저·설정을
프로젝트의 `.venv/huggingface/hub`에 내려받습니다. 이후에는 로컬 파일을 재사용합니다.
가중치 용량은 약 4GB이며 로딩을 위한 여유 메모리도 필요합니다. 인터넷이 없고
로컬 캐시도 없으면 Qwen 설명은 템플릿으로 대체됩니다.

| 경로 | 화면 | 구현 |
| --- | --- | --- |
| `/` | 메인 대시보드 | `pages/main.py` |
| `/detail` | 설비별 상세 | `pages/detail/page.py` |
| `/statistics` | 통계 | `pages/statistics/` |

`app.py`가 세 화면의 경로와 통계 히트맵에서 설비 상세로 가는 동작을 연결합니다. `shared/sidebar.py`는 세 화면의 공통 메뉴입니다.

메인의 F03은 `data/processed/predictions.csv`의 최신 고장 위험과, 파일이 있으면 `data/processed/maintenance_plan.csv`의 재고·조달 정보를 요약합니다. 설비 상세의 F05는 동일한 예측 기간으로 부품 위험을 비교하고, 선택 설비의 센서 이상 신호를 별도 근거로 Qwen 종합진단을 표시합니다. F06은 `data/raw/azure_pdm/PdM_telemetry.csv`와 `outputs/model3/predictions.csv`를 사용해 최근 72시간의 선택 센서값·IQR·3-Sigma 경계와 설비 전체의 IF(AI) 점수·기준을 두 개의 시계열 선그래프로 보여줍니다. F06은 LLM을 호출하지 않습니다. `src/ui/ai_data.py`에서 F03과 F05가 Qwen 모델을 재사용합니다. IF 점수는 고장 확률이 아니며 미보정 고장 위험 점수도 확률로 표시하지 않습니다.

F06은 선택한 72시간 구간에 이상이 없으면 0건을 표시합니다. IQR 탐지 상·하한은 UDL/LDL, 3-Sigma 관리 상·하한은 UCL/LCL로 표시하며, IF의 경고 기준은 아래 그래프에 따로 표시합니다. 첫 화면 로딩 시 로컬 Qwen 가중치를 불러오므로 수 초 걸릴 수 있습니다. 메인의 캘린더·TOP5와 나머지 프레임 값은 현재 UI 확인용 예시 데이터입니다.
