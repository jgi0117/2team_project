# GE-DB MySQL 연결

## 실행

```powershell
.venv\Scripts\python.exe -m src.ge_db.setup
.venv\Scripts\python.exe -m src.ge_app
```

접속: http://127.0.0.1:8050
최초 관리자 계정은 서버 PC의 `/setup`에서 생성합니다.
접속 정보는 Git에 포함하지 않는 `.env`에서 읽습니다.
`src.ui.app`은 CSV 실행용이며, DB 연결 실행은 `src.ge_app`을 사용합니다.

## 현재 데이터로 DB 재생성

```powershell
.venv\Scripts\python.exe -m src.ge_db.setup --rebuild
```

`--rebuild`는 **DB_NAME으로 지정한 DB 전체를 삭제**합니다. 백업을 만들지 않으며,
기존 사용자·로그인·발주·설정·완료 처리 기록도 사라집니다. 원본 CSV는 변경하지 않습니다.
다른 MySQL 데이터베이스는 삭제하지 않습니다.
플래그 없이 실행하면 운영 기록을 유지하고 변경된 CSV만 다시 적재합니다.
데이터 갱신 후에는 대시보드를 재시작해 메모리 캐시를 비우세요.

## 데이터 구조

- `data/raw/azure_pdm/*.csv`: 설비, 센서, 오류, 고장, 정비 원본
- `data/operations/*.csv`: 부품, 공급업체, 재고, 구매, 정비 및 비용
- `data/processed/*.csv`: 예측·위험·특성·라벨·재고/구매 이력
- `outputs/model3/predictions.csv`, `outputs/model3/evaluation/*.csv`: 이상탐지 결과 및 평가

각 CSV를 `data_...` 테이블에 실제 컬럼과 행 순서로 적재합니다.
`datasets`에서 파일 경로와 테이블명, 행 수, 원래 자료형 및 SHA-256을 확인할 수 있습니다.
`source_manifest`는 원본 파일 정보입니다. float64 점수는 MySQL DOUBLE로 저장합니다.
2026-09-30 재구축 기준 CSV 40개, 총 1,530,644행입니다.
Parquet/학습 모델 파일은 기존 GE 계산에서 그대로 사용합니다.

`src.ge_app`에서는 히트맵, 설비 데이터, 운영 스냅샷, 발주 계획과 AI 요약 입력의 CSV 조회를 DB로 연결합니다.
DB 값은 원본 자료형·행 순서로 복원한 뒤 기존 GE 계산 함수에 전달합니다.
DB 장애나 원본 CSV 변경 시 CSV를 사용하고 로그를 남깁니다. 미적재 파일은 CSV를 사용합니다.

## 운영 기록과 화면

- 사용자 및 암호화된 로그인 감사 기록
- 사용자별 설정, 완료 처리, 발주 목록과 변경 이력
- 발주 상세 및 취소 상태 (`unit_price`는 GE와 같은 **만원** 단위)
- 서버 오류 기록

로그인 후 새로고침하면 설정·완료·발주 기록을 DB에서 복원합니다.
이전 계정의 브라우저 저장소 값은 사용하지 않습니다. 아직 제출하지 않은 장바구니는 새로고침 시 초기화됩니다.
설정 창에서 실제 계정 로그인 이력을 조회하고, 사이드바에서 로그아웃할 수 있습니다.
Bootstrap CSS를 로컬 제공하므로 설정 창 스타일은 외부 CDN에 의존하지 않습니다.
히트맵은 작은 화면에서도 최소 높이를 유지하며 좁은 화면에서는 가로 스크롤됩니다.

DB 저장은 트랜잭션으로 처리합니다. 저장 실패 시 화면 응답을 유지하고 오류 유형을 서버에 기록합니다.
실패한 변경의 자동 재전송은 지원하지 않습니다.
`DB_ENABLED=false`이면 DB 조회·저장·인증을 사용하지 않습니다.
DB 연결/읽기/쓰기 제한 시간은 각각 3/5/5초입니다.

## 검증

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

MySQL 초기화 후 실행하세요. 통합 테스트는 임시 계정과 해당 계정 기록만 만들고 정리합니다.
원본과 DB 자료형·값 일치, 히트맵, 설정 저장/초기화, 로그인/로그아웃,
DB 상태 복원, 발주 중복 처리·롤백 및 기존 GE 기능을 검증합니다.
