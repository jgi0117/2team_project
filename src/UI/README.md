# 통계 페이지 UI 프레임

`docs/UI기능_명세_기획서.pptx` 14페이지의 오른쪽 UI Frame을 기준으로 작성했습니다.
왼쪽 사이드바와 위쪽 F10 / 아래쪽 F09 자리만 구성하며, 실제 데이터·히트맵·필터·모델 연동은 구현하지 않았습니다.
기능 이름과 번호는 PPT 10페이지의 기능명세서를 따릅니다.

저장소 루트의 통합 `requirements.txt`로 의존성을 설치한 뒤 실행합니다.

```powershell
python -m pip install -r requirements.txt
python -m src.UI.app
```

브라우저에서 http://127.0.0.1:8050 에 접속합니다.

## 팀 작업 연결

- `sidebar.py`: `create_sidebar(main_href=None, equipment_href=None)`은 공통 메뉴를 생성합니다. 메인화면·설비별 화면이 준비되면 실제 경로를 전달해 비활성 메뉴를 링크로 바꿉니다. 현재 통계 화면용으로 통계 메뉴가 선택되어 있습니다.
- `statistics.py`: `create_statistics_layout()`을 다른 Dash 앱의 페이지 콘텐츠로 넣을 수 있습니다.
- `stats-f10-content`: 공정별 이상 위험 히트맵이 들어갈 상단 영역입니다.
- `stats-f09-content`: 설비별 고장 예측 히트맵이 들어갈 하단 영역입니다.
- 각 영역의 `children`을 실제 기능으로 교체하면 됩니다. 제목을 교체할 때는 `aria-labelledby`에 연결된 제목 ID도 유지하거나 함께 수정합니다.
- `assets/dashboard.css`: 통합 앱의 assets 폴더에 포함합니다. 바깥 레이아웃에 `ui-dashboard` 클래스를 적용하면 사이드바와 통계 화면이 나란히 배치됩니다.

메인화면과 설비별 상세화면, 해당 화면의 라우팅은 포함하지 않습니다.
