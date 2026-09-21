# 데이터 전처리

## 작업 범위

원본 CSV 검증과 설비·부품·예측시점별 특징 및 정답 생성을 담당합니다.

## 입출력

- 입력: data/raw/azure_pdm/ 원본 CSV 5종
- 출력: data/processed/features.csv, labels.csv

## 공통 규칙

machineID와 datetime을 기준으로 과거 오류 횟수와 교체 후 경과시간을 계산합니다. 미래 관측 구간이 부족한 정답은 정상으로 채우지 않습니다.

[공통 데이터 계약](../../docs/DATA_CONTRACT.md)을 따릅니다. 담당자는 팀에서 정하고 본인 브랜치에서 이 디렉토리를 중심으로 작업합니다. 현재는 개발 구조만 준비한 상태입니다.
