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

DB를 완전히 비우고 다시 만들 때는 다음 명령을 사용합니다.

```powershell
.venv\Scripts\python.exe -m src.ge_db.setup --rebuild
```

처음 접속하면 서버 PC의 `http://127.0.0.1:8050/setup`에서 관리자 계정을 만듭니다.
초기 관리자 생성은 localhost에서만 허용됩니다.

## GE-DB 연결 범위와 검증

- `GE`에서 분기했으며 GJ의 SQLAlchemy/PyMySQL 연결, 트랜잭션 및 인증 구성을 참고했습니다.
- `.env`의 접속 정보를 사용합니다. `.env`는 Git에 포함하지 않습니다.
- 예측·센서·재고 분석 입력은 GE의 기존 CSV/모델 파일을 사용합니다. 원본 데이터 전체를 MySQL로 이관하지 않습니다.
- 설정·완료 처리·발주 목록은 GE 콜백이 반환한 값을 사용자별로 MySQL에 기록합니다.
- 브라우저 저장소의 기존 동작을 유지합니다. DB 기록을 새 브라우저 세션으로 자동 복원하는 기능은 없습니다.
- `order_records.unit_price`는 GE 화면과 같은 만원 단위입니다.
- 저장 트랜잭션 실패 시 화면 응답은 유지하고 서버에 오류 유형을 기록합니다. 실패한 변경의 자동 재전송은 지원하지 않습니다.
- DB 연결/읽기/쓰기 제한 시간은 각각 3/5/5초입니다. `DB_ENABLED=false`이면 DB 저장과 DB 인증을 사용하지 않습니다.
- 초기화는 기존 데이터를 유지하는 `python -m src.ge_db.setup`을 사용하세요. `--rebuild`는 DB 전체를 삭제합니다.

검증 명령:

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

MySQL 통합 테스트는 임시 사용자를 만들고 해당 사용자의 테스트 기록만 정리합니다.
실제 DB에서 저장·중복 처리·롤백, 설정 콜백, DB 장애 시 응답 유지와 GE 회귀 테스트를 검증합니다.
