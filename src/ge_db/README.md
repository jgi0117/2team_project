# GE 전용 MySQL 계층

이 패키지는 GE 대시보드 파일을 수정하거나 DB 데이터로 대체하지 않습니다.
GE 화면은 기존 CSV와 모델 결과를 그대로 읽고, MySQL은 다음 운영 정보만 저장합니다.

- 사용자와 로그인 감사 기록
- 설정, 완료 처리, 발주 목록의 변경 이력
- 발주별 설비·부품·공급업체·수량·단가 및 취소 상태
- 서버 오류 로그
- GE 원본 데이터 파일의 SHA-256, 크기, 행 수

## 최초 실행

```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m src.ge_db.setup
.venv\Scripts\python.exe -m src.ge_app
```

처음 접속하면 서버 PC의 `http://127.0.0.1:8050/setup`에서 관리자 계정을 만듭니다.
초기 관리자 생성은 localhost에서만 허용됩니다.
