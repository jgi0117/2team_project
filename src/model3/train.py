"""Isolation Forest 학습 및 테스트 구간 결과 저장. 평가 지표는 계산하지 않는다.

실행 (프로젝트 루트):
    python src/model3/train.py
    python src/model3/train.py --contamination 0.01 --n-estimators 200

입력: data/processed/model3/dataset.csv (원본 파일을 변경하지 않음)
출력: outputs/model3/isolation_forest.joblib, outputs/model3/predictions.csv

학습에는 split=train 행의 센서 특징 44개만 사용한다. 결측 대체 역시 학습
구간의 중앙값만 사용한다. 전체 학습 값이 결측인 특징은 0으로 대체한다.
Isolation Forest에는 스케일러를 추가하지 않는다.

anomaly_score는 -score_samples로, 클수록 더 이례적인 패턴이다(확률 아님).
is_anomaly는 anomaly_score > threshold일 때 1, 아니면 0인 모델의 판정이다.
기본 contamination='auto'는 알고리즘 기본 임계값이며 검증된 이상 기준이 아니다.
0.01처럼 지정하면 학습 점수의 상위 약 1%를 경고하는 기준을 설정한다.
이 비율은 실제 이상 비율이나 테스트 구간 경고 비율을 보장하지 않는다.

팀원 연동: fit_model(train_rows), predict_rows(bundle, rows)를 사용하거나,
joblib.load()로 bundle을 읽는다. predictions.csv는 machineID/as_of로 연결한다.
직접 전달하는 rows에도 preprocessing.py와 동일한 센서 파생 특징이 필요하다.
정답 라벨, 성능 지표, severity/원인 센서 판정은 생성하지 않는다.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import IsolationForest
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline

if __package__:
    from .preprocessing import METADATA_COLUMNS, ROOT, SENSORS, WINDOWS
else:
    from preprocessing import METADATA_COLUMNS, ROOT, SENSORS, WINDOWS


DEFAULT_DATA_PATH = ROOT / "data" / "processed" / "model3" / "dataset.csv"
DEFAULT_OUTPUT_DIR = ROOT / "outputs" / "model3"
# 명시적 목록으로 향후 팀원이 추가하는 라벨/예측 결과가 입력에 섞이지 않게 한다.
FEATURE_COLUMNS = tuple(
    column
    for sensor in SENSORS
    for column in (
        sensor,
        *(f"{sensor}_{stat}_{hours}h" for hours in WINDOWS for stat in ("mean", "std")),
        f"{sensor}_deviation_72h", f"{sensor}_zscore_72h",
        f"{sensor}_baseline_constant_72h", f"{sensor}_delta_1h",
    )
)


def _feature_matrix(rows: pd.DataFrame, columns: tuple | list) -> pd.DataFrame:
    missing = set(columns) - set(rows.columns)
    if missing:
        raise ValueError(f"Missing sensor features: {sorted(missing)}")
    matrix = rows.loc[:, list(columns)].astype(np.float32)
    if np.isinf(matrix.to_numpy()).any():
        raise ValueError("Sensor features contain infinite values")
    return matrix


def load_dataset(data_path: str | Path = DEFAULT_DATA_PATH) -> pd.DataFrame:
    """시간순 train/test 분할을 확인하고 명시된 입력 열만 읽는다."""
    columns = [*METADATA_COLUMNS, *FEATURE_COLUMNS]
    data = pd.read_csv(data_path, usecols=columns)
    data["as_of"] = pd.to_datetime(data["as_of"], format="ISO8601", errors="raise")
    data["machineID"] = pd.to_numeric(data["machineID"], errors="raise")
    if data.empty or data[list(METADATA_COLUMNS)].isna().any().any():
        raise ValueError("Empty dataset or missing machineID/as_of/split")
    if ((data.machineID <= 0) | (data.machineID % 1 != 0)).any():
        raise ValueError("machineID must be a positive integer")
    if not data["split"].isin(["train", "test"]).all():
        raise ValueError("split must be train or test")
    if data.duplicated(["machineID", "as_of"]).any():
        raise ValueError("Duplicate machineID/as_of keys")
    train_times = data.loc[data.split.eq("train"), "as_of"]
    test_times = data.loc[data.split.eq("test"), "as_of"]
    if train_times.empty or test_times.empty:
        raise ValueError("Both train and test rows are required")
    if train_times.max() >= test_times.min():
        raise ValueError("Every test timestamp must be after every training timestamp")
    return data.sort_values(["machineID", "as_of"]).reset_index(drop=True)


def fit_model(
    train_rows: pd.DataFrame,
    *,
    n_estimators: int = 200,
    contamination: str | float = "auto",
    random_state: int = 42,
) -> dict:
    """학습 행만 받아 결측 대체와 모델을 fit한다. 평가용 y는 사용하지 않는다."""
    if train_rows.empty or not train_rows["split"].eq("train").all():
        raise ValueError("fit_model requires nonempty train rows only")
    pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="median", keep_empty_features=True)),
        ("detector", IsolationForest(
            n_estimators=n_estimators,
            max_samples="auto",
            contamination=contamination,
            random_state=random_state,
            n_jobs=-1,
        )),
    ])
    pipeline.fit(_feature_matrix(train_rows, FEATURE_COLUMNS))
    return {
        "pipeline": pipeline,
        "feature_columns": list(FEATURE_COLUMNS),
        "threshold": float(-pipeline.named_steps["detector"].offset_),
        "trained_until": str(train_rows["as_of"].max()),
        "sklearn_version": sklearn.__version__,
        "parameters": {"n_estimators": n_estimators, "contamination": contamination,
                       "random_state": random_state},
        "score_definition": "-score_samples; higher is more anomalous, not a probability",
    }


def predict_rows(bundle: dict, rows: pd.DataFrame, *, batch_size: int = 50_000) -> pd.DataFrame:
    """모델의 학습/임계값 변경 없이 행별 점수 계산. 실제 정답/평가 지표는 없음."""
    if rows.empty or batch_size <= 0:
        raise ValueError("Nonempty rows and a positive batch_size are required")
    result_columns = ["machineID", "as_of"]
    if "split" in rows:
        result_columns.append("split")
    result = rows.loc[:, [*result_columns, *SENSORS]].copy().reset_index(drop=True)
    scores = []
    for start in range(0, len(rows), batch_size):
        matrix = _feature_matrix(rows.iloc[start:start + batch_size], bundle["feature_columns"])
        scores.append(-bundle["pipeline"].score_samples(matrix))
    result["anomaly_score"] = np.concatenate(scores)
    result["threshold"] = bundle["threshold"]
    result["is_anomaly"] = (result.anomaly_score > result.threshold).astype("int8")
    return result.sort_values(["as_of", "machineID"]).reset_index(drop=True)


def train_model(
    data_path: str | Path = DEFAULT_DATA_PATH,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    *,
    n_estimators: int = 200,
    contamination: str | float = "auto",
    random_state: int = 42,
) -> tuple[dict, pd.DataFrame]:
    """모델과 테스트 행별 결과만 저장한다. 반환값은 팀원 평가 코드에서 재사용 가능."""
    data = load_dataset(data_path)
    bundle = fit_model(data.loc[data.split.eq("train")], n_estimators=n_estimators,
                       contamination=contamination, random_state=random_state)
    predictions = predict_rows(bundle, data.loc[data.split.eq("test")])
    output_dir = Path(output_dir)
    if Path(data_path).resolve() in {
        (output_dir / "predictions.csv").resolve(),
        (output_dir / "isolation_forest.joblib").resolve(),
    }:
        raise ValueError("Output files must not overwrite the input dataset")
    output_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, output_dir / "isolation_forest.joblib", compress=3)
    predictions.to_csv(output_dir / "predictions.csv", index=False)
    return bundle, predictions


def _contamination(value: str) -> str | float:
    if value == "auto":
        return value
    try:
        ratio = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Use auto or a number in (0, 0.5]") from exc
    if not 0 < ratio <= 0.5:
        raise argparse.ArgumentTypeError("contamination must be in (0, 0.5]")
    return ratio


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-path", type=Path, default=DEFAULT_DATA_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--n-estimators", type=int, default=200)
    parser.add_argument("--contamination", type=_contamination, default="auto")
    parser.add_argument("--random-state", type=int, default=42)
    args = parser.parse_args()
    bundle, predictions = train_model(
        args.data_path, args.output_dir, n_estimators=args.n_estimators,
        contamination=args.contamination, random_state=args.random_state,
    )
    print(f"Model: {args.output_dir / 'isolation_forest.joblib'}")
    print(f"Predictions: {args.output_dir / 'predictions.csv'} ({len(predictions):,} test rows)")
    print(f"Features: {len(bundle['feature_columns'])}; threshold: {bundle['threshold']:.6f}")
    print("Highest anomaly scores (model predictions, not ground-truth labels):")
    print(predictions.nlargest(10, "anomaly_score").to_string(index=False))


if __name__ == "__main__":
    main()
