# 통계·설비 상세 대시보드 UI

`docs/UI기능_명세_기획서.pptx` 14페이지의 오른쪽 UI Frame을 기준으로 작성했습니다.
통계 화면은 왼쪽 사이드바와 위쪽 F10 / 아래쪽 F09 자리로 구성했습니다. 설비 상세 화면은 GE의 UI 프레임을 포함합니다. 실제 데이터·히트맵·필터·모델 연동은 구현하지 않았습니다.
기능 이름과 번호는 PPT 10페이지의 기능명세서를 따릅니다.

저장소 루트의 통합 `requirements.txt`로 의존성을 설치한 뒤 실행합니다.

```powershell
python -m pip install -r requirements.txt
python -m src.UI.dashboard
```

브라우저에서 http://127.0.0.1:8050 에 접속합니다.

## 팀 작업 연결

- `dashboard.py`: 통계 화면과 설비 상세 화면을 하나의 Dash 앱으로 실행하며 사이드바 링크로 화면을 전환합니다.
- `statistics_page.py`: 통계 콘텐츠와 사이드바를 배치합니다.
- `sidebar.py`: `create_sidebar(main_href=None, equipment_href=None, active="statistics")`은 현재 화면을 표시하고 통계·설비 상세 링크를 제공합니다.
- `statistics.py`: `create_statistics_layout()`을 다른 Dash 앱의 페이지 콘텐츠로 넣을 수 있습니다.
- `stats-f10-content`: 공정별 이상 위험 히트맵이 들어갈 상단 영역입니다.
- `stats-f09-content`: 설비별 고장 예측 히트맵이 들어갈 하단 영역입니다.
- 각 영역의 `children`을 실제 기능으로 교체하면 됩니다. 제목을 교체할 때는 `aria-labelledby`에 연결된 제목 ID도 유지하거나 함께 수정합니다.
- `assets/dashboard.css`: 통합 앱의 assets 폴더에 포함합니다. 바깥 레이아웃에 `ui-dashboard` 클래스를 적용하면 사이드바와 통계 화면이 나란히 배치됩니다.

통계 화면은 `/`, 설비 상세 화면은 `/detail`에서 확인할 수 있습니다. 사이드바의 설비별·통계 항목으로 화면을 전환합니다. 설비 상세 프레임은 GE의 `src/ui/pages/detail.py`와 `src/ui/assets/detail.css`에서 가져왔습니다.
