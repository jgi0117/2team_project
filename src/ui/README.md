# 통합 Dash 대시보드

메인, 설비별, 통계 화면을 하나의 Dash 앱에서 실행합니다. 프로젝트 루트에서 다음 명령을 실행하세요.

```powershell
python -m pip install -r requirements.txt
python -m src.ui.app
```

브라우저에서 `http://127.0.0.1:8050`으로 접속합니다.

| 경로 | 화면 | 구현 |
| --- | --- | --- |
| `/` | 메인 대시보드 | `pages/main.py` |
| `/detail` | 설비별 상세 | `pages/detail/page.py` |
| `/statistics` | 통계 | `pages/statistics/` |

`app.py`가 세 화면의 경로와 통계 히트맵에서 설비 상세로 가는 동작을 연결합니다. `shared/sidebar.py`는 세 화면의 공통 메뉴입니다. 메인 화면의 요약·캘린더·TOP5 값은 현재 UI 확인용 예시 데이터입니다.
