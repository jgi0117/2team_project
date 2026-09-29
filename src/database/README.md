# MySQL 데이터베이스

대시보드 운영 데이터와 화면에서 생성한 발주 요청·조치 이력을
`maintenance_dashboard` 데이터베이스에 저장합니다. 로그인/사용자 테이블은 아직 포함하지
않으며, 관련 사용자 ID 컬럼은 nullable 상태로 준비되어 있습니다.

## 초기화

각 컴퓨터에 MySQL Server 8.x와 Python 3.12를 설치하고 MySQL 서비스를 먼저 실행합니다.
그런 다음 프로젝트 루트의 PowerShell에서 다음 설정 스크립트를 실행합니다.

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup_local_db.ps1
```

스크립트가 가상환경과 패키지를 준비하고 MySQL 계정을 입력받아 `.env`를 만든 뒤,
`maintenance_dashboard`와 초기 데이터를 구성합니다. 설정 후에는 다음 명령으로 실행합니다.

```powershell
.\scripts\run_dashboard.ps1
```

수동으로 설정하려면 `.env.example`을 `.env`로 복사하고 접속 정보를 바꾼 뒤 실행합니다.

```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m src.database.bootstrap
```

초기화 명령은 데이터베이스가 없으면 생성하고 빈 테이블만 적재합니다. 이미 데이터가 있는
테이블은 건너뛰므로 대시보드에서 작성한 발주 요청과 조치 이력을 삭제하지 않습니다.

센서 원본 876,100건을 제외한 빠른 초기화가 필요하면 다음 옵션을 사용합니다.

```powershell
.venv\Scripts\python.exe -m src.database.bootstrap --skip-telemetry
```

`DB_ENABLED=false`로 설정하면 기존 CSV 읽기로 대체됩니다.

## 다른 컴퓨터에서 로컬 실행

다른 컴퓨터에서도 위 설정 스크립트를 한 번 실행하면 동일한 초기 데이터로 대시보드를
실행할 수 있습니다. 단, 각 컴퓨터의 `localhost` MySQL은 서로 다른 데이터베이스입니다.
한 컴퓨터에서 만든 발주 요청이나 To-Do 조치가 다른 컴퓨터에 자동 동기화되지는 않습니다.
실시간 공유가 필요해지는 시점에는 한 대의 MySQL 서버나 관리형 클라우드 MySQL을 공용
`DB_HOST`로 지정해야 합니다.

## 같은 네트워크에서 대시보드 공개

서버 PC의 `.env`에서 `DASH_HOST=0.0.0.0`으로 설정하고 TCP 8050을 로컬 서브넷에만
허용하면 다른 컴퓨터는 `http://서버-PC-IP:8050`으로 접속할 수 있습니다. 이 구성에서는
MySQL은 서버 PC의 localhost에 유지하므로 3306 포트를 공개할 필요가 없습니다. 서버 PC의
IP가 바뀌지 않도록 공유기에서 DHCP 주소 예약을 권장합니다.

Windows 방화벽은 관리자 권한 PowerShell에서 한 번만 설정합니다.

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\allow_dashboard_firewall.ps1
```

## 저장 범위

- 설비, 부품, 공급업체, 비용 기준
- 기존 발주, 재고 로트·이동, 정비 기록
- 센서, 오류, 고장, 부품 교체 원천 이벤트
- 고장 확률, 위험 곡선, 이상 탐지 결과
- 대시보드 발주 요청 헤더·품목·상태 이력
- To-Do 숨김/복원 등 조치 이력
- 사용자 계정, Argon2id 비밀번호 해시, 로그인 성공·실패 이력

학습용 feature/label, 평가 리포트, 모델 파일, 다시 계산할 수 있는 일별 집계 CSV는
DB 원본 데이터에 포함하지 않습니다.

## 로그인 계정 관리

설정 스크립트는 최초 관리자 계정을 만들고 비밀번호를 터미널에서 안전하게 입력받습니다.
비밀번호 원문은 저장하지 않고 Argon2id 해시만 저장합니다. 로그인 접속 IP는
AES-256-GCM으로 암호화하여 감사 이력에 저장합니다.

추가 계정 생성과 비밀번호 변경은 다음 명령을 사용합니다.

```powershell
.venv\Scripts\python.exe -m src.database.auth create-user --username operator
.venv\Scripts\python.exe -m src.database.auth change-password --username operator
```

로그인은 5회 연속 실패하면 해당 계정을 15분간 잠급니다. 로그인 세션은 8시간 유지됩니다.

## 데모 실행 데이터 초기화

`DB_RESET_ON_EXIT=true`이면 대시보드 시작 직전과 정상 종료 시 다음 실행 데이터가 삭제됩니다.

- 대시보드에서 생성한 발주 요청·품목·상태 이력
- To-Do 작업 및 조치 이력
- 로그인 성공·실패 감사 로그

설비·센서·예측·재고·정비·기존 발주 원장과 `users` 계정은 유지됩니다. 시작할 때도
정리하므로 이전 실행이 강제 종료되었거나 전원이 꺼졌던 경우 다음 실행 시 초기화됩니다.
