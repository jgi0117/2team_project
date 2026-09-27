# 통계·설비 상세 대시보드 UI

`docs/UI기능_명세_기획서.pptx` 14페이지의 오른쪽 UI Frame을 기준으로 작성했습니다.
통계 화면은 왼쪽 사이드바와 위쪽 F10 센서 이상 위험 / 아래쪽 F09 고장 위험 히트맵으로 구성했습니다. 설비 상세 화면은 GE의 UI 프레임을 포함하며, 설비 선택과 부품별 예측 확률을 저장된 데이터에 연결했습니다. 종합 진단·센서 분석·발주·이력 영역은 아직 프레임입니다.
기능 이름과 번호는 PPT 10페이지의 기능명세서를 따릅니다.

저장소 루트의 통합 `requirements.txt`로 의존성을 설치한 뒤 실행합니다.

```powershell
python -m pip install -r requirements.txt
python -m src.UI.dashboard
```

브라우저에서 http://127.0.0.1:8050 에 접속합니다.

## 팀 작업 연결

- `dashboard.py`: 통계 화면과 설비 상세 화면을 하나의 Dash 앱으로 실행하며 사이드바 링크로 화면을 전환합니다.
- `pages/statistics/`: 통계 화면 구성(`page.py`, `layout.py`)과 공통 히트맵 패널(`heatmap_panel.py`)입니다.
- `pages/detail/page.py`: GE 설비 상세 UI 프레임과 설비 선택·부품 확률 콜백입니다.
- `shared/sidebar.py`: 두 화면에서 사용하는 사이드바와 현재 화면 표시입니다.
- `stats-f10-content`: 설비별 이상 위험 히트맵입니다. 저장된 IF 결과를 사용합니다.
- `stats-f09-content`: 설비별 고장 위험 히트맵입니다. 부품 예측 결과를 설비별로 요약합니다.
- `assets/shared/dashboard.css`: 공통 사이드바 스타일입니다. `assets/statistics/`와 `assets/detail/`의 CSS는 각 화면 스타일입니다.

통계 화면은 `/`, 설비 상세 화면은 `/detail`에서 확인할 수 있습니다. 사이드바의 설비별·통계 항목으로 화면을 전환합니다. 설비 상세 프레임은 GE의 `src/ui/pages/detail.py`와 `src/ui/assets/detail.css`에서 가져왔습니다.
통계 화면의 F09·F10 히트맵에서 설비 칸이나 번호를 클릭하면 `/detail?machine=<설비번호>`로 이동해 해당 설비가 선택됩니다.
