"""센서 이상 탐지용 전처리. 입력은 PdM_telemetry.csv 하나뿐이다.

실행: python src/model3/preprocessing.py [--test-size 0.2] [--output-dir PATH]
출력: dataset.csv 하나. split=train/test로 시간순 학습/테스트 구간을 구분한다.
한 행은 machineID/as_of의 센서 관측이다. 현재 센서는 사용하지만 모든
이동 통계는 [as_of - window, as_of)만 사용한다. 최초 72시간과 이력이
불완전한 행은 저장하지 않는다. 극단값은 탐지 대상이므로 제거하지 않는다.

CSV: machineID, as_of, split 및 센서 특징 44개. METADATA_COLUMNS를 제외한
열을 모델 입력으로 사용한다. 결측 대체/스케일러/임계값은 학습 구간에서만
적합해야 한다. 학습 구간 역시 이상이 포함될 수 있는 미라벨 데이터다.

원본에 센서 이상 정답이 없어 라벨은 만들지 않는다. train/test는 데이터
분할이며 정상/이상 정답이 아니다. 정밀도/재현율 평가는 별도로 검토한
센서 이상 라벨이 필요하다. 고장 이력으로 이상 정답을 대신하지 않는다.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Iterator

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_DIR = ROOT / "data" / "raw" / "azure_pdm"
DEFAULT_OUTPUT_DIR = ROOT / "data" / "processed" / "model3"
SENSORS = ("volt", "rotate", "pressure", "vibration")
WINDOWS = (6, 24, 72)
RAW_COLUMNS = ("datetime", "machineID", *SENSORS)
METADATA_COLUMNS = ("machineID", "as_of", "split")


def load_data(data_dir: str | Path = DEFAULT_DATA_DIR) -> pd.DataFrame:
    """센서 파일만 로드. 오류/정비/고장/설비 메타데이터 파일은 읽지 않는다."""
    path = Path(data_dir) / "PdM_telemetry.csv"
    frame = pd.read_csv(path)
    missing = set(RAW_COLUMNS) - set(frame.columns)
    if missing:
        raise ValueError(f"{path.name}: missing columns {sorted(missing)}")
    frame = frame.loc[:, list(RAW_COLUMNS)].copy()
    frame["datetime"] = pd.to_datetime(frame["datetime"], format="ISO8601", errors="coerce")
    if not pd.api.types.is_datetime64_any_dtype(frame.datetime) or frame.datetime.dt.tz is not None:
        raise ValueError("Expected timezone-naive timestamps; no timezone conversion is performed")
    for column in ("machineID", *SENSORS):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


def audit_data(telemetry: pd.DataFrame) -> dict:
    """수정/삭제 없이 품질 검사. 잘못된 키/값은 차단, 결측 센서는 보고 후 보존."""
    missing = set(RAW_COLUMNS) - set(telemetry.columns)
    if missing:
        raise ValueError(f"Missing columns: {sorted(missing)}")
    report: dict = {
        "rows": len(telemetry), "machines": int(telemetry.machineID.nunique()),
        "missing_values": {c: int(v) for c, v in telemetry.isna().sum().items()},
        "duplicate_keys": int(telemetry.duplicated(["machineID", "datetime"]).sum()),
        "infinite_values": int(np.isinf(telemetry[["machineID", *SENSORS]].to_numpy()).sum()),
        "errors": [], "warnings": [],
    }
    if telemetry.empty:
        report["errors"].append("telemetry: empty required table")
    if telemetry[["machineID", "datetime"]].isna().any().any():
        report["errors"].append("telemetry: invalid/missing keys")
    ids = telemetry.machineID
    if ((ids <= 0) | (ids % 1 != 0)).any():
        report["errors"].append("machineID must be a positive integer")
    for issue in ("duplicate_keys", "infinite_values"):
        if report[issue]:
            report["errors"].append(f"telemetry: {issue}={report[issue]}")
    telemetry = telemetry.sort_values(["machineID", "datetime"])
    intervals = telemetry.groupby("machineID").datetime.diff().dropna()
    summary = telemetry[list(SENSORS)].replace([np.inf, -np.inf], np.nan).describe()
    summary = summary.astype(object).where(summary.notna(), None)
    report["telemetry"] = {
        "non_hourly_intervals": int((intervals != pd.Timedelta(hours=1)).sum()),
        "missing_hour_slots": int(
            ((intervals / pd.Timedelta(hours=1) - 1).clip(lower=0)).sum()
        ),
        "sensor_summary": summary.to_dict(),
    }
    if (intervals % pd.Timedelta(hours=1) != pd.Timedelta(0)).any():
        report["errors"].append("telemetry: observations must follow an hourly grid")
    if report["telemetry"]["non_hourly_intervals"]:
        report["warnings"].append("Telemetry has gaps; no interpolation is performed.")
    if telemetry[list(SENSORS)].isna().any().any():
        report["warnings"].append("Missing sensors are retained; incomplete rows are not ready.")
    if (telemetry[list(SENSORS)] <= 0).any().any():
        report["warnings"].append("Nonpositive sensors found; confirm units/physical limits.")
    report["warnings"].extend([
        "Sensor anomaly labels are unavailable; train/test rows are unlabeled, not verified normal.",
        "Sensor units, physical limits and timestamp timezone are unspecified.",
        "Extreme sensor values are retained because they may be anomaly signals.",
    ])
    report["valid"] = not report["errors"]
    return report


def _ready_mask(sensors: pd.DataFrame) -> pd.Series:
    """현재 센서와 직전 72개 시간 관측이 모두 존재하는 행."""
    counts = sensors.rolling("72h", closed="left", min_periods=72).count()
    return sensors.notna().all(axis=1) & counts.eq(72).all(axis=1)


def iter_feature_frames(telemetry: pd.DataFrame) -> Iterator[pd.DataFrame]:
    """검증된 데이터로 설비 단위 특징 생성. 최대 72시간 이력을 함께 전달해야 한다.

    과거 [t-w, t)의 w개 센서가 모두 있어야 평균/표준편차를 생성한다.
    처음 72시간과 관측 공백은 NaN + is_ready=False로 유지한다.
    기준선은 직전 72시간이며 검증된 '정상' 구간을 의미하지 않는다.
    """
    for machine_id, rows in telemetry.groupby("machineID", sort=True):
        rows = rows.sort_values("datetime").set_index("datetime")
        times = pd.DatetimeIndex(rows.index)
        sensors = rows.loc[:, list(SENSORS)]
        columns = {sensor: sensors[sensor] for sensor in SENSORS}
        consecutive = times.to_series().diff().eq(pd.Timedelta(hours=1))
        for hours in WINDOWS:
            rolling = sensors.rolling(f"{hours}h", closed="left", min_periods=hours)
            mean, std = rolling.mean(), rolling.std(ddof=0)
            for sensor in SENSORS:
                columns[f"{sensor}_mean_{hours}h"] = mean[sensor]
                columns[f"{sensor}_std_{hours}h"] = std[sensor]
                if hours == 72:
                    deviation = sensors[sensor] - mean[sensor]
                    columns[f"{sensor}_deviation_72h"] = deviation
                    # 0 분산을 임의 epsilon으로 증폭하지 않는다. 원래 편차도 보존한다.
                    zscore = deviation / std[sensor].replace(0, np.nan)
                    columns[f"{sensor}_zscore_72h"] = zscore.mask(
                        std[sensor].eq(0) & deviation.eq(0), 0.0
                    )
                    columns[f"{sensor}_baseline_constant_72h"] = std[sensor].eq(0)
        for sensor in SENSORS:
            columns[f"{sensor}_delta_1h"] = sensors[sensor].diff().where(consecutive)

        frame = pd.DataFrame(columns, index=times)
        # 0 분산 이후 값이 달라진 경우의 zscore는 NaN이며 편차/constant 열도 함께 사용한다.
        frame["is_ready"] = _ready_mask(sensors)
        frame.insert(0, "as_of", times)
        frame.insert(0, "machineID", int(machine_id))
        yield frame.reset_index(drop=True)


def build_features(telemetry: pd.DataFrame) -> pd.DataFrame:
    """메모리 내 사용용 API. 대용량 CLI는 설비별로 저장해 메모리를 제한한다."""
    report = audit_data(telemetry)
    if not report["valid"]:
        raise ValueError("Invalid input: " + "; ".join(report["errors"]))
    return pd.concat(iter_feature_frames(telemetry), ignore_index=True)


def run_preprocessing(
    data_dir: str | Path = DEFAULT_DATA_DIR,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    *,
    audit_only: bool = False,
    test_size: float = 0.2,
) -> dict:
    """이력이 충분한 행만 dataset.csv에 저장. 검사 결과는 반환/콘솔 출력만 한다.

    설비 전체의 사용 가능한 고유 시각을 기준으로 마지막 test_size 비율을
    테스트로 배정한다. 같은 시각은 모든 설비에서 같은 split을 갖는다.
    """
    if not 0 < test_size < 1:
        raise ValueError("test_size must be between 0 and 1 (exclusive)")
    telemetry = load_data(data_dir)
    report = audit_data(telemetry)
    output_dir = Path(output_dir)
    # 원본 디렉터리를 출력 위치로 잘못 지정해도 원본이 수정되지 않도록 차단.
    if output_dir.resolve() == Path(data_dir).resolve():
        raise ValueError("output_dir must differ from data_dir")
    if not report["valid"]:
        raise ValueError(f"Data validation failed: {report['errors']}")
    if audit_only:
        return report

    # 특징 전체를 메모리에 쌓지 않고, 준비된 시각만 수집하여 공통 경계를 정한다.
    eligible_times = set()
    for _, rows in telemetry.groupby("machineID", sort=False):
        sensors = rows.sort_values("datetime").set_index("datetime")[list(SENSORS)]
        eligible_times.update(sensors.index[_ready_mask(sensors)])
    times = sorted(eligible_times)
    boundary_index = int(len(times) * (1 - test_size))
    if not 0 < boundary_index < len(times):
        raise ValueError("Not enough ready timestamps for a nonempty train/test split")
    test_start = times[boundary_index]

    output_dir.mkdir(parents=True, exist_ok=True)
    count = train_count = test_count = 0
    feature_count = 0
    # 생성에 실패해도 기존 dataset.csv가 손상되지 않도록 완료 후 교체한다.
    temporary_path = None
    try:
        with NamedTemporaryFile(mode="w", encoding="utf-8", newline="",
                                dir=output_dir, suffix=".tmp", delete=False) as stream:
            temporary_path = Path(stream.name)
            for frame in iter_feature_frames(telemetry):
                frame = frame.loc[frame.is_ready].drop(columns="is_ready").copy()
                if frame.empty:
                    continue
                feature_count = len(frame.columns) - 2  # machineID, as_of 제외
                frame.insert(2, "split", np.where(frame.as_of < test_start, "train", "test"))
                frame.to_csv(stream, index=False, header=count == 0, float_format="%.8g")
                count += len(frame)
                train_count += int(frame.split.eq("train").sum())
                test_count += int(frame.split.eq("test").sum())
        temporary_path.replace(output_dir / "dataset.csv")
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
    report["output"] = {
        "file": str(output_dir / "dataset.csv"), "rows": count,
        "train_rows": train_count, "test_rows": test_count,
        "excluded_rows": len(telemetry) - count,
        "features": feature_count, "test_start": str(test_start),
    }
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--audit-only", action="store_true", help="원본 품질 검사만 실행")
    parser.add_argument("--test-size", type=float, default=0.2, help="마지막 테스트 기간 비율 (기본 0.2)")
    args = parser.parse_args()
    report = run_preprocessing(args.data_dir, args.output_dir,
                               audit_only=args.audit_only, test_size=args.test_size)
    print(json.dumps({"valid": report["valid"], "output_dir": str(args.output_dir),
                      "output": report.get("output"), "warnings": report["warnings"]},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
