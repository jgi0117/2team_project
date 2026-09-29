# 설비 상세 페이지 UI 프레임 v1

## 파일
- app.py            Dash 실행 엔트리 (앱 생성은 여기 한 곳만)
- pages/detail.py   상세 페이지 레이아웃 + 펼침/접힘 콜백
- assets/detail.css 반응형 스타일 (없으면 화면 전부 깨짐)

## 설치 위치
프로젝트의 src/ 안에 ui 폴더를 통째로 넣으세요 → src/ui/...

## 실행
.\.venv\Scripts\python.exe -m pip install dash dash-bootstrap-components
.\.venv\Scripts\python.exe -m src.ui.app     →  http://127.0.0.1:8050
※ dash 2.16 미만이면 app.py 마지막 줄 app.run → app.run_server

## 화면 구조
F05  설비 이미지 무대 (좌상단 종합진단 / 부품 말풍선 4개 / 우하단 교체이력 버튼)
F06  F05 위에 겹치는 오버레이 (센서 이상·위험 근거)
F07  부품 말풍선 클릭 시 아래로 펼침 (비용곡선 / 발주정보 / 시나리오)
F08  '담기' → 협력사 정보,  '교체 이력 보기' → 교체 이력  (각각 독립 펼침)

## 현재 상태
빈 박스 + id만 있는 프레임입니다. 값은 전부 "--" 로 표시됩니다.
데이터 연결은 다음 단계이며, id 목록은 "id 계약서 v1" 문서를 참고하세요.
