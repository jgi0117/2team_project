# 데이터 전처리

## 작업 범위

원본 CSV 검증과 설비·부품·예측시점별 특징 및 정답 생성을 담당합니다.

## 입출력

- 입력: data/raw/azure_pdm/ 원본 CSV 5종
- 출력: data/processed/features.csv, labels.csv

## 공통 규칙

machineID와 datetime을 기준으로 과거 오류 횟수와 교체 후 경과시간을 계산합니다. 미래 관측 구간이 부족한 정답은 정상으로 채우지 않습니다.

[공통 데이터 계약](../../docs/DATA_CONTRACT.md)을 따릅니다. 담당자는 팀에서 정하고 본인 브랜치에서 이 디렉토리를 중심으로 작업합니다.

## 구현한 기능

`generate_operations.py`는 과거 교체 수요에 맞춰 가상 조달·재고·정비 운영 데이터를 생성합니다. 원본 센서 전처리나 고장 모델 학습은 아직 구현하지 않았습니다.

```powershell
python -m src.data_pipeline.generate_operations
python -m unittest discover -s src/data_pipeline/tests -v
```

설정과 생성 근거는 [운영 데이터 안내](../../data/operations/README.md)를 확인합니다. 기본 명령은 생성 CSV를 다시 쓰며 원본은 수정하지 않습니다.
