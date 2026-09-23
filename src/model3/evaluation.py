"""Isolation Forest, 3-Sigma, IQR 이상 경고를 비교 평가한다.

Isolation Forest 자체의 점수 분포, 설비/시간별 이상률, 연속 이벤트를 분석하고,
학습 구간에서 만든 설비별 3-Sigma 및 IQR 센서 기준선과 비교한다. 세 방식의
경고를 실제 고장 전 24/48/72시간과 연결하여 고장 사전 탐지율, 경고 이벤트
적중률, 오경보율, 선행시간, Lift를 계산한다.

PdM_failures.csv는 센서 이상 자체의 정답이 아니라 이후 고장이라는 운영 결과로
사용한다. 따라서 이 평가는 일반적인 이상 분류 정확도가 아니라 고장 예측에 대한
경고의 실용성을 측정한다.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_PREDICTIONS = ROOT / "outputs" / "model3" / "predictions.csv"
DEFAULT_MODEL = ROOT / "outputs" / "model3" / "isolation_forest.joblib"
DEFAULT_OUTPUT = ROOT / "outputs" / "model3" / "evaluation"
DEFAULT_FAILURES = ROOT / "data" / "raw" / "azure_pdm" / "PdM_failures.csv"
DEFAULT_DATASET = ROOT / "data" / "processed" / "model3" / "dataset.csv"

SENSORS = ("volt", "rotate", "pressure", "vibration")
MODEL_ALERT_COLUMNS = {
    "Isolation Forest": "is_anomaly",
    "3-Sigma": "three_sigma_alert",
    "IQR": "iqr_alert",
}
MODEL_COLORS = {
    "Isolation Forest": "#1f77b4",
    "3-Sigma": "#ff7f0e",
    "IQR": "#2ca02c",
}


# ---------------------------------------------------------
# 1. 결과 불러오기
# ---------------------------------------------------------

def load_predictions(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path)

    required = {
        "machineID",
        "as_of",
        "anomaly_score",
        "threshold",
        "is_anomaly",
    }

    missing = required - set(df.columns)

    if missing:
        raise ValueError(
            f"predictions.csv에 필요한 컬럼이 없습니다: {sorted(missing)}"
        )

    df["as_of"] = pd.to_datetime(
        df["as_of"],
        format="ISO8601",
        errors="raise"
    )

    df["machineID"] = pd.to_numeric(
        df["machineID"],
        errors="raise"
    ).astype(int)

    df["anomaly_score"] = pd.to_numeric(
        df["anomaly_score"],
        errors="raise"
    )

    df["threshold"] = pd.to_numeric(
        df["threshold"],
        errors="raise"
    )

    df["is_anomaly"] = df["is_anomaly"].astype(int)

    return df.sort_values(
        ["machineID", "as_of"]
    ).reset_index(drop=True)


def load_failures(path: str | Path) -> pd.DataFrame:
    """Load failure events and normalize their timestamp/key columns."""
    failures = pd.read_csv(path)
    required = {"datetime", "machineID", "failure"}
    missing = required - set(failures.columns)
    if missing:
        raise ValueError(
            f"PdM_failures.csv is missing required columns: {sorted(missing)}"
        )

    failures = failures.loc[:, ["datetime", "machineID", "failure"]].copy()
    failures["failure_time"] = pd.to_datetime(
        failures.pop("datetime"), format="ISO8601", errors="raise"
    )
    failures["machineID"] = pd.to_numeric(
        failures["machineID"], errors="raise"
    ).astype(int)
    return failures.sort_values(
        ["machineID", "failure_time"]
    ).reset_index(drop=True)


def build_statistical_baselines(
    df: pd.DataFrame,
    dataset_path: str | Path,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Fit per-machine sensor thresholds on train rows and score test rows."""
    required = {"machineID", *SENSORS}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(
            f"predictions.csv is missing baseline columns: {sorted(missing)}"
        )

    train = pd.read_csv(
        dataset_path,
        usecols=["machineID", "split", *SENSORS],
    )
    train = train.loc[train["split"].eq("train"), ["machineID", *SENSORS]]
    if train.empty:
        raise ValueError("The processed dataset has no train rows")
    train["machineID"] = pd.to_numeric(
        train["machineID"], errors="raise"
    ).astype(int)

    grouped = train.groupby("machineID", sort=True)
    thresholds = pd.DataFrame(index=grouped.size().index)
    thresholds.index.name = "machineID"

    for sensor in SENSORS:
        mean = grouped[sensor].mean()
        std = grouped[sensor].std()
        q1 = grouped[sensor].quantile(0.25)
        q3 = grouped[sensor].quantile(0.75)
        iqr = q3 - q1

        thresholds[f"{sensor}_3sigma_lower"] = mean - 3 * std
        thresholds[f"{sensor}_3sigma_upper"] = mean + 3 * std
        thresholds[f"{sensor}_iqr_lower"] = q1 - 1.5 * iqr
        thresholds[f"{sensor}_iqr_upper"] = q3 + 1.5 * iqr

    thresholds = thresholds.reset_index()
    scored = df.merge(
        thresholds,
        on="machineID",
        how="left",
        validate="many_to_one",
    )
    threshold_columns = [column for column in scored if column.endswith(("_lower", "_upper"))]
    if scored[threshold_columns].isna().any().any():
        missing_machines = sorted(
            scored.loc[scored[threshold_columns].isna().any(axis=1), "machineID"].unique()
        )
        raise ValueError(
            f"No training baseline is available for machines: {missing_machines}"
        )

    sigma_flags = []
    iqr_flags = []
    for sensor in SENSORS:
        sigma_flags.append(
            scored[sensor].lt(scored[f"{sensor}_3sigma_lower"])
            | scored[sensor].gt(scored[f"{sensor}_3sigma_upper"])
        )
        iqr_flags.append(
            scored[sensor].lt(scored[f"{sensor}_iqr_lower"])
            | scored[sensor].gt(scored[f"{sensor}_iqr_upper"])
        )

    scored["three_sigma_alert"] = np.logical_or.reduce(sigma_flags).astype("int8")
    scored["iqr_alert"] = np.logical_or.reduce(iqr_flags).astype("int8")
    scored = scored.drop(columns=threshold_columns)
    return scored, thresholds


# ---------------------------------------------------------
# 2. 기본 평가
# ---------------------------------------------------------

def basic_metrics(df: pd.DataFrame) -> dict:

    total = len(df)

    anomaly_count = int(
        df["is_anomaly"].sum()
    )

    anomaly_rate = (
        anomaly_count / total
        if total > 0
        else np.nan
    )

    threshold = float(
        df["threshold"].iloc[0]
    )

    return {
        "total_rows": total,
        "anomaly_rows": anomaly_count,
        "anomaly_rate": anomaly_rate,
        "threshold": threshold,
        "score_mean": float(df["anomaly_score"].mean()),
        "score_median": float(df["anomaly_score"].median()),
        "score_std": float(df["anomaly_score"].std()),
        "score_min": float(df["anomaly_score"].min()),
        "score_max": float(df["anomaly_score"].max()),
    }


# ---------------------------------------------------------
# 3. Threshold 주변 데이터
# ---------------------------------------------------------

def threshold_proximity(
    df: pd.DataFrame,
    margin_ratio: float = 0.05,
) -> dict:

    threshold = float(
        df["threshold"].iloc[0]
    )

    # threshold의 ±5% 범위
    margin = abs(threshold) * margin_ratio

    lower = threshold - margin
    upper = threshold + margin

    near = df[
        df["anomaly_score"].between(
            lower,
            upper
        )
    ]

    return {
        "threshold": threshold,
        "lower_bound": lower,
        "upper_bound": upper,
        "near_threshold_rows": len(near),
        "near_threshold_rate": len(near) / len(df),
    }


# ---------------------------------------------------------
# 4. 설비별 이상탐지율
# ---------------------------------------------------------

def machine_anomaly_rate(
    df: pd.DataFrame
) -> pd.DataFrame:

    result = (
        df.groupby("machineID")
        .agg(
            observations=("is_anomaly", "size"),
            anomaly_count=("is_anomaly", "sum"),
        )
        .reset_index()
    )

    result["anomaly_rate"] = (
        result["anomaly_count"]
        / result["observations"]
    )

    return result.sort_values(
        "anomaly_rate",
        ascending=False
    )


# ---------------------------------------------------------
# 5. 시간별 이상탐지율
# ---------------------------------------------------------

def time_anomaly_rate(
    df: pd.DataFrame,
    freq: str = "D",
) -> pd.DataFrame:

    temp = df.copy()

    temp["period"] = (
        temp["as_of"]
        .dt.to_period(freq)
        .astype(str)
    )

    result = (
        temp.groupby("period")
        .agg(
            observations=("is_anomaly", "size"),
            anomaly_count=("is_anomaly", "sum"),
        )
        .reset_index()
    )

    result["anomaly_rate"] = (
        result["anomaly_count"]
        / result["observations"]
    )

    return result


# ---------------------------------------------------------
# 6. 연속 이상 이벤트 분석
# ---------------------------------------------------------

def detect_anomaly_events(
    df: pd.DataFrame,
    alert_column: str = "is_anomaly",
    model_name: str | None = None,
) -> pd.DataFrame:

    events = []

    for machine_id, group in df.groupby(
        "machineID",
        sort=True
    ):

        group = group.sort_values("as_of").copy()

        anomaly_times = group.loc[
            group[alert_column].eq(1),
            "as_of"
        ].tolist()

        if not anomaly_times:
            continue

        start = anomaly_times[0]
        previous = anomaly_times[0]

        for current in anomaly_times[1:]:

            # 시간 간격이 1시간이면 같은 이벤트
            if current - previous == pd.Timedelta(hours=1):
                previous = current

            else:
                events.append({
                    "model": model_name or alert_column,
                    "machineID": machine_id,
                    "start": start,
                    "end": previous,
                    "duration_hours": (
                        (previous - start)
                        / pd.Timedelta(hours=1)
                        + 1
                    ),
                })

                start = current
                previous = current

        # 마지막 이벤트
        events.append({
            "model": model_name or alert_column,
            "machineID": machine_id,
            "start": start,
            "end": previous,
            "duration_hours": (
                (previous - start)
                / pd.Timedelta(hours=1)
                + 1
            ),
        })

    return pd.DataFrame(
        events,
        columns=["model", "machineID", "start", "end", "duration_hours"],
    )


def event_metrics(
    events: pd.DataFrame
) -> dict:

    if events.empty:

        return {
            "event_count": 0,
            "mean_duration_hours": np.nan,
            "median_duration_hours": np.nan,
            "max_duration_hours": np.nan,
        }

    return {
        "event_count": len(events),
        "mean_duration_hours": events[
            "duration_hours"
        ].mean(),

        "median_duration_hours": events[
            "duration_hours"
        ].median(),

        "max_duration_hours": events[
            "duration_hours"
        ].max(),
    }


def _future_failure_labels(
    rows: pd.DataFrame,
    failures: pd.DataFrame,
    horizon_hours: int,
) -> np.ndarray:
    """Mark rows followed by a same-machine failure inside the horizon."""
    labels = np.zeros(len(rows), dtype=bool)
    horizon = np.timedelta64(horizon_hours, "h")
    failure_groups = {
        machine_id: group["failure_time"].to_numpy(dtype="datetime64[ns]")
        for machine_id, group in failures.groupby("machineID")
    }

    for machine_id, index in rows.groupby("machineID").groups.items():
        failure_times = failure_groups.get(machine_id)
        if failure_times is None or len(failure_times) == 0:
            continue
        row_times = rows.loc[index, "as_of"].to_numpy(dtype="datetime64[ns]")
        positions = np.searchsorted(failure_times, row_times, side="right")
        valid = positions < len(failure_times)
        next_failures = np.empty(len(row_times), dtype="datetime64[ns]")
        next_failures[:] = np.datetime64("NaT", "ns")
        next_failures[valid] = failure_times[positions[valid]]
        labels[np.asarray(index)] = valid & ((next_failures - row_times) <= horizon)

    return labels


def compare_failure_prediction(
    df: pd.DataFrame,
    failures: pd.DataFrame,
    horizons=(24, 48, 72),
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Compare failure recall, event precision, lead time, false alarms, and lift."""
    evaluation_start = df["as_of"].min()
    evaluation_end = df["as_of"].max()
    failures = failures.loc[
        failures["failure_time"].between(evaluation_start, evaluation_end)
    ].copy()

    events_by_model = {
        model: detect_anomaly_events(df, column, model)
        for model, column in MODEL_ALERT_COLUMNS.items()
    }
    all_events = pd.concat(events_by_model.values(), ignore_index=True)
    metric_rows = []
    failure_rows = []

    for horizon_hours in horizons:
        horizon = pd.Timedelta(hours=horizon_hours)
        eligible_failures = failures.loc[
            failures["failure_time"] >= evaluation_start + horizon
        ].copy()

        row_subset = df.loc[df["as_of"] <= evaluation_end - horizon].copy()
        future_failure = _future_failure_labels(
            row_subset.reset_index(drop=True), failures, horizon_hours
        )
        base_failure_rate = float(future_failure.mean()) if len(future_failure) else np.nan

        for model, alert_column in MODEL_ALERT_COLUMNS.items():
            detected_count = 0
            lead_times = []

            for failure in eligible_failures.itertuples(index=False):
                warning_start = failure.failure_time - horizon
                warning_times = df.loc[
                    df["machineID"].eq(failure.machineID)
                    & df[alert_column].eq(1)
                    & df["as_of"].ge(warning_start)
                    & df["as_of"].lt(failure.failure_time),
                    "as_of",
                ]
                detected = not warning_times.empty
                lead_hours = (
                    (failure.failure_time - warning_times.min())
                    / pd.Timedelta(hours=1)
                    if detected
                    else np.nan
                )
                detected_count += int(detected)
                if detected:
                    lead_times.append(float(lead_hours))
                failure_rows.append({
                    "model": model,
                    "horizon_hours": horizon_hours,
                    "machineID": failure.machineID,
                    "failure_time": failure.failure_time,
                    "component": failure.failure,
                    "detected": int(detected),
                    "lead_time_hours": lead_hours,
                })

            eligible_events = events_by_model[model].loc[
                events_by_model[model]["end"] <= evaluation_end - horizon
            ].copy()
            matched_events = 0
            for event in eligible_events.itertuples(index=False):
                matched = failures["machineID"].eq(event.machineID) & failures[
                    "failure_time"
                ].between(event.start, event.end + horizon, inclusive="both")
                matched_events += int(matched.any())

            alert_mask = row_subset[alert_column].eq(1).to_numpy()
            conditional_failure_rate = (
                float(future_failure[alert_mask].mean())
                if alert_mask.any()
                else np.nan
            )
            lift = (
                conditional_failure_rate / base_failure_rate
                if base_failure_rate and not np.isnan(conditional_failure_rate)
                else np.nan
            )
            event_count = len(eligible_events)
            false_event_count = event_count - matched_events

            metric_rows.append({
                "model": model,
                "horizon_hours": horizon_hours,
                "alert_rows": int(df[alert_column].sum()),
                "alert_rate": float(df[alert_column].mean()),
                "alert_event_count": event_count,
                "eligible_failures": len(eligible_failures),
                "detected_failures": detected_count,
                "failure_detection_rate": (
                    detected_count / len(eligible_failures)
                    if len(eligible_failures)
                    else np.nan
                ),
                "matched_alert_events": matched_events,
                "alert_precision": (
                    matched_events / event_count if event_count else np.nan
                ),
                "false_alert_events": false_event_count,
                "false_alert_rate": (
                    false_event_count / event_count if event_count else np.nan
                ),
                "mean_lead_time_hours": (
                    float(np.mean(lead_times)) if lead_times else np.nan
                ),
                "median_lead_time_hours": (
                    float(np.median(lead_times)) if lead_times else np.nan
                ),
                "base_failure_rate": base_failure_rate,
                "alert_failure_rate": conditional_failure_rate,
                "lift": lift,
            })

    failure_matches = pd.DataFrame(failure_rows)
    component_comparison = (
        failure_matches.groupby(["model", "horizon_hours", "component"], as_index=False)
        .agg(
            eligible_failures=("detected", "size"),
            detected_failures=("detected", "sum"),
            mean_lead_time_hours=("lead_time_hours", "mean"),
        )
    )
    component_comparison["failure_detection_rate"] = (
        component_comparison["detected_failures"]
        / component_comparison["eligible_failures"]
    )
    return pd.DataFrame(metric_rows), all_events, component_comparison


def pre_failure_alert_profile(
    df: pd.DataFrame,
    failures: pd.DataFrame,
    max_hours: int = 72,
) -> pd.DataFrame:
    """Calculate the fraction of failures with an alert at each pre-failure hour."""
    start = df["as_of"].min()
    end = df["as_of"].max()
    eligible = failures.loc[
        failures["failure_time"].between(
            start + pd.Timedelta(hours=max_hours), end
        )
    ]
    rows = []
    for model, alert_column in MODEL_ALERT_COLUMNS.items():
        alert_index = pd.MultiIndex.from_frame(
            df.loc[df[alert_column].eq(1), ["machineID", "as_of"]]
        )
        for hours_before in range(max_hours, 0, -1):
            probe = pd.DataFrame({
                "machineID": eligible["machineID"].to_numpy(),
                "as_of": (
                    eligible["failure_time"] - pd.Timedelta(hours=hours_before)
                ).to_numpy(),
            })
            matches = pd.MultiIndex.from_frame(probe).isin(alert_index)
            rows.append({
                "model": model,
                "hours_before_failure": hours_before,
                "alert_rate": float(matches.mean()) if len(matches) else np.nan,
                "eligible_failures": len(matches),
            })
    return pd.DataFrame(rows)


def select_sample_machines(
    df: pd.DataFrame,
    sample_size: int = 4,
    random_state: int = 42,
) -> list[int]:
    """Select a reproducible random sample of machines for visual comparison."""
    machine_ids = np.sort(df["machineID"].unique())
    if sample_size <= 0:
        raise ValueError("sample_size must be positive")
    if sample_size > len(machine_ids):
        raise ValueError(
            f"sample_size={sample_size} exceeds available machines={len(machine_ids)}"
        )
    generator = np.random.default_rng(random_state)
    return sorted(generator.choice(machine_ids, size=sample_size, replace=False).tolist())


def unlabeled_method_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Summarize alert burden and temporal behavior without anomaly labels."""
    rows = []
    for model, alert_column in MODEL_ALERT_COLUMNS.items():
        events = detect_anomaly_events(df, alert_column, model)
        daily_rate = (
            df.assign(day=df["as_of"].dt.floor("D"))
            .groupby("day")[alert_column]
            .mean()
        )
        machine_rate = df.groupby("machineID")[alert_column].mean()
        rows.append({
            "model": model,
            "alert_rows": int(df[alert_column].sum()),
            "alert_rate": float(df[alert_column].mean()),
            "alert_event_count": len(events),
            "mean_event_duration_hours": (
                float(events["duration_hours"].mean()) if len(events) else np.nan
            ),
            "median_event_duration_hours": (
                float(events["duration_hours"].median()) if len(events) else np.nan
            ),
            "max_event_duration_hours": (
                float(events["duration_hours"].max()) if len(events) else np.nan
            ),
            "machines_with_alerts": int(
                df.loc[df[alert_column].eq(1), "machineID"].nunique()
            ),
            "daily_alert_rate_std": float(daily_rate.std(ddof=0)),
            "machine_alert_rate_std": float(machine_rate.std(ddof=0)),
        })
    return pd.DataFrame(rows)


def pairwise_alert_agreement(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate pairwise hourly alert overlap for the three detectors."""
    rows = []
    models = list(MODEL_ALERT_COLUMNS)
    for left_index, left_model in enumerate(models):
        left = df[MODEL_ALERT_COLUMNS[left_model]].eq(1).to_numpy()
        for right_model in models[left_index + 1:]:
            right = df[MODEL_ALERT_COLUMNS[right_model]].eq(1).to_numpy()
            intersection = int(np.logical_and(left, right).sum())
            union = int(np.logical_or(left, right).sum())
            rows.append({
                "model_a": left_model,
                "model_b": right_model,
                "both_alert_rows": intersection,
                "either_alert_rows": union,
                "jaccard_similarity": intersection / union if union else np.nan,
                "model_a_only_rows": int(np.logical_and(left, ~right).sum()),
                "model_b_only_rows": int(np.logical_and(~left, right).sum()),
            })
    return pd.DataFrame(rows)


def incremental_alert_value(
    df: pd.DataFrame,
    failures: pd.DataFrame,
    horizons=(24, 48, 72),
) -> pd.DataFrame:
    """Measure whether IF-only alerts add failure-associated signal beyond baselines.

    The result is an operational proxy, not anomaly-label accuracy. A row is positive
    when the same machine has a recorded failure within the specified future horizon.
    """
    evaluation_end = df["as_of"].max()
    rows = []
    for horizon_hours in horizons:
        eligible = df.loc[
            df["as_of"] <= evaluation_end - pd.Timedelta(hours=horizon_hours)
        ].reset_index(drop=True)
        future_failure = _future_failure_labels(eligible, failures, horizon_hours)
        base_rate = float(future_failure.mean()) if len(eligible) else np.nan
        isolation = eligible["is_anomaly"].eq(1).to_numpy()
        legacy = eligible[["three_sigma_alert", "iqr_alert"]].eq(1).any(axis=1).to_numpy()
        segments = {
            "Isolation Forest only": isolation & ~legacy,
            "Isolation Forest and legacy": isolation & legacy,
            "Legacy only": ~isolation & legacy,
            "No alert": ~isolation & ~legacy,
        }
        for segment, mask in segments.items():
            count = int(mask.sum())
            failure_rate = float(future_failure[mask].mean()) if count else np.nan
            rows.append({
                "horizon_hours": horizon_hours,
                "segment": segment,
                "rows": count,
                "row_share": count / len(eligible) if len(eligible) else np.nan,
                "future_failure_rate": failure_rate,
                "base_failure_rate": base_rate,
                "lift": failure_rate / base_rate if base_rate and count else np.nan,
            })
    return pd.DataFrame(rows)


def sampled_machine_alert_rows(
    df: pd.DataFrame,
    machine_ids: list[int],
) -> pd.DataFrame:
    """Return hourly detector flags for the selected machines."""
    result = df.loc[
        df["machineID"].isin(machine_ids),
        ["machineID", "as_of", *MODEL_ALERT_COLUMNS.values()],
    ].copy()
    return result.sort_values(["machineID", "as_of"]).reset_index(drop=True)


# ---------------------------------------------------------
# 7. Score Distribution 시각화
# ---------------------------------------------------------

def plot_score_distribution(
    df: pd.DataFrame,
    output_dir: Path,
):

    threshold = float(
        df["threshold"].iloc[0]
    )

    plt.figure(figsize=(10, 6))

    plt.hist(
        df["anomaly_score"],
        bins=60
    )

    plt.axvline(
        threshold,
        linestyle="--",
        label=f"Threshold = {threshold:.4f}"
    )

    plt.xlabel("Anomaly Score")
    plt.ylabel("Number of Observations")
    plt.title("Isolation Forest Anomaly Score Distribution")
    plt.legend()

    plt.tight_layout()

    plt.savefig(
        output_dir / "score_distribution.png",
        dpi=150
    )

    plt.close()


# ---------------------------------------------------------
# 8. Machine별 이상탐지율 시각화
# ---------------------------------------------------------

def plot_machine_anomaly_rate(
    machine_df: pd.DataFrame,
    output_dir: Path,
):

    plt.figure(figsize=(12, 6))

    plt.bar(
        machine_df["machineID"].astype(str),
        machine_df["anomaly_rate"]
    )

    plt.xlabel("Machine ID")
    plt.ylabel("Anomaly Rate")
    plt.title("Anomaly Rate by Machine")

    plt.xticks(rotation=90)

    plt.tight_layout()

    plt.savefig(
        output_dir / "machine_anomaly_rate.png",
        dpi=150
    )

    plt.close()


# ---------------------------------------------------------
# 9. 시간별 이상탐지율 시각화
# ---------------------------------------------------------

def plot_time_anomaly_rate(
    time_df: pd.DataFrame,
    output_dir: Path,
):

    plt.figure(figsize=(12, 6))

    plt.plot(
        time_df["period"],
        time_df["anomaly_rate"],
        marker="o"
    )

    plt.xlabel("Period")
    plt.ylabel("Anomaly Rate")
    plt.title("Anomaly Rate Over Time")

    plt.xticks(rotation=45)

    plt.tight_layout()

    plt.savefig(
        output_dir / "time_anomaly_rate.png",
        dpi=150
    )

    plt.close()


def plot_model_comparison(
    comparison: pd.DataFrame,
    output_dir: Path,
):
    """Plot operational failure-prediction metrics on a shared model view."""
    colors = {
        "Isolation Forest": "#1f77b4",
        "3-Sigma": "#ff7f0e",
        "IQR": "#2ca02c",
    }
    figure, axes = plt.subplots(2, 3, figsize=(17, 10))
    line_metrics = [
        ("failure_detection_rate", "Failure detection rate", "Rate"),
        ("alert_precision", "Alert event precision", "Rate"),
        ("false_alert_rate", "False alert event rate", "Rate"),
        ("lift", "Failure lift after alert", "Lift"),
        ("mean_lead_time_hours", "Mean lead time", "Hours"),
    ]

    for axis, (column, title, ylabel) in zip(axes.flat[:5], line_metrics):
        for model in MODEL_ALERT_COLUMNS:
            model_rows = comparison.loc[comparison["model"].eq(model)].sort_values(
                "horizon_hours"
            )
            axis.plot(
                model_rows["horizon_hours"],
                model_rows[column],
                marker="o",
                linewidth=2,
                label=model,
                color=colors[model],
            )
        axis.set_title(title)
        axis.set_xlabel("Prediction horizon (hours)")
        axis.set_ylabel(ylabel)
        axis.set_xticks(sorted(comparison["horizon_hours"].unique()))
        axis.grid(alpha=0.25)
        if column.endswith("rate") or column == "alert_precision":
            axis.set_ylim(0, 1.05)

    alert_rates = (
        comparison.sort_values("horizon_hours")
        .drop_duplicates("model")
        .set_index("model")
        .reindex(MODEL_ALERT_COLUMNS)
    )
    axes.flat[5].bar(
        alert_rates.index,
        alert_rates["alert_rate"],
        color=[colors[model] for model in alert_rates.index],
    )
    axes.flat[5].set_title("Hourly alert rate")
    axes.flat[5].set_ylabel("Rate")
    axes.flat[5].set_ylim(0, max(0.05, alert_rates["alert_rate"].max() * 1.2))
    axes.flat[5].tick_params(axis="x", rotation=20)
    axes.flat[5].grid(axis="y", alpha=0.25)

    handles, labels = axes.flat[0].get_legend_handles_labels()
    figure.legend(handles, labels, loc="upper center", ncol=3, frameon=False)
    figure.suptitle(
        "Failure Prediction Comparison: Isolation Forest vs Statistical Baselines",
        fontsize=15,
        y=0.98,
    )
    figure.tight_layout(rect=(0, 0, 1, 0.94))
    figure.savefig(output_dir / "model_failure_comparison.png", dpi=160)
    plt.close(figure)


def plot_pre_failure_profile(
    profile: pd.DataFrame,
    output_dir: Path,
):
    """Plot smoothed alert prevalence during the 72 hours before failures."""
    colors = {
        "Isolation Forest": "#1f77b4",
        "3-Sigma": "#ff7f0e",
        "IQR": "#2ca02c",
    }
    plt.figure(figsize=(12, 6))
    for model in MODEL_ALERT_COLUMNS:
        model_rows = profile.loc[profile["model"].eq(model)].copy()
        model_rows["relative_hour"] = -model_rows["hours_before_failure"]
        model_rows = model_rows.sort_values("relative_hour")
        model_rows["smoothed_alert_rate"] = model_rows["alert_rate"].rolling(
            6, center=True, min_periods=1
        ).mean()
        plt.plot(
            model_rows["relative_hour"],
            model_rows["smoothed_alert_rate"],
            linewidth=2,
            label=model,
            color=colors[model],
        )

    plt.axvline(0, color="black", linestyle="--", linewidth=1, label="Failure")
    plt.xlabel("Hours relative to failure")
    plt.ylabel("Failures with an alert at that hour")
    plt.title("Alert Prevalence Before Failure (6-hour moving average)")
    plt.grid(alpha=0.25)
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_dir / "pre_failure_alert_profile.png", dpi=160)
    plt.close()


def plot_sampled_machine_alert_timeline(
    sampled_rows: pd.DataFrame,
    failures: pd.DataFrame,
    output_dir: Path,
):
    """Plot hourly alert timestamps as detector lanes for sampled machines."""
    machine_ids = sampled_rows["machineID"].drop_duplicates().tolist()
    figure, axes = plt.subplots(
        len(machine_ids), 1, figsize=(16, 2.6 * len(machine_ids)), sharex=True,
    )
    axes = np.atleast_1d(axes)
    lane_positions = {
        "Isolation Forest": 2,
        "3-Sigma": 1,
        "IQR": 0,
    }

    for axis, machine_id in zip(axes, machine_ids):
        machine_rows = sampled_rows.loc[sampled_rows["machineID"].eq(machine_id)]
        for model, alert_column in MODEL_ALERT_COLUMNS.items():
            alert_times = machine_rows.loc[
                machine_rows[alert_column].eq(1), "as_of"
            ]
            axis.scatter(
                alert_times,
                np.full(len(alert_times), lane_positions[model]),
                s=13,
                marker="|",
                linewidths=1.4,
                color=MODEL_COLORS[model],
                label=model,
            )

        machine_failures = failures.loc[
            failures["machineID"].eq(machine_id)
            & failures["failure_time"].between(
                machine_rows["as_of"].min(), machine_rows["as_of"].max()
            )
        ]
        for failure_time in machine_failures["failure_time"]:
            axis.axvline(failure_time, color="#b22222", linewidth=0.8, alpha=0.45)

        axis.set_yticks([0, 1, 2])
        axis.set_yticklabels(["IQR", "3-Sigma", "IF"])
        axis.set_ylim(-0.6, 2.6)
        axis.set_title(f"Machine {machine_id}", loc="left", fontsize=11)
        axis.grid(axis="x", alpha=0.18)

    handles = [
        Line2D([], [], color=MODEL_COLORS[model], marker="|", linestyle="None",
               markersize=10, label=model)
        for model in MODEL_ALERT_COLUMNS
    ]
    handles.append(
        Line2D([], [], color="#b22222", linewidth=1, alpha=0.6,
               label="Recorded failure")
    )
    figure.legend(
        handles=handles,
        loc="upper center",
        bbox_to_anchor=(0.5, 0.963),
        ncol=4,
        frameon=False,
    )
    axes[-1].set_xlabel("Hourly timestamp")
    figure.suptitle(
        "Hourly Alert Timeline for Reproducibly Sampled Machines",
        fontsize=15,
        y=0.995,
    )
    figure.tight_layout(rect=(0, 0, 1, 0.92))
    figure.savefig(output_dir / "sampled_machine_alert_timeline.png", dpi=180)
    plt.close(figure)


# ---------------------------------------------------------
# 10. contamination 민감도
# ---------------------------------------------------------

def contamination_sensitivity(
    model_path: str | Path,
    df: pd.DataFrame,
    contamination_values=(0.005, 0.01, 0.02, 0.03, 0.05),
) -> pd.DataFrame:

    bundle = joblib.load(model_path)

    pipeline = bundle["pipeline"]

    detector = pipeline.named_steps["detector"]

    # 이미 학습된 모델의 contamination을 직접 바꾸는 것이 아니라,
    # score의 분포를 이용하여 각 contamination에서 threshold를 계산한다.
    scores = df["anomaly_score"].to_numpy()

    rows = []

    for contamination in contamination_values:

        # 높은 score부터 contamination 비율을 이상으로 간주
        threshold = np.quantile(
            scores,
            1 - contamination
        )

        anomaly_rate = (
            scores > threshold
        ).mean()

        rows.append({
            "contamination": contamination,
            
            "threshold": threshold,
            "anomaly_rate": anomaly_rate,
        })

    return pd.DataFrame(rows)


# ---------------------------------------------------------
# 11. 전체 평가 실행
# ---------------------------------------------------------

def evaluate(
    predictions_path=DEFAULT_PREDICTIONS,
    model_path=DEFAULT_MODEL,
    failures_path=DEFAULT_FAILURES,
    dataset_path=DEFAULT_DATASET,
    output_dir=DEFAULT_OUTPUT,
    sample_size: int = 4,
    sample_seed: int = 42,
):

    output_dir = Path(output_dir)
    output_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    df = load_predictions(
        predictions_path
    )
    failures_df = load_failures(failures_path)
    df, baseline_thresholds = build_statistical_baselines(df, dataset_path)

    # 기본
    basic = basic_metrics(df)

    # threshold 근처
    threshold_info = threshold_proximity(df)

    # machine
    machine_df = machine_anomaly_rate(df)

    # time
    time_df = time_anomaly_rate(df)

    # events
    events_df = detect_anomaly_events(df)
    events = event_metrics(events_df)

    comparison_df, all_model_events_df, component_comparison_df = (
        compare_failure_prediction(df, failures_df)
    )
    alert_profile_df = pre_failure_alert_profile(df, failures_df)
    method_summary_df = unlabeled_method_summary(df)
    agreement_df = pairwise_alert_agreement(df)
    incremental_value_df = incremental_alert_value(df, failures_df)
    sampled_machine_ids = select_sample_machines(
        df, sample_size=sample_size, random_state=sample_seed
    )
    sampled_alerts_df = sampled_machine_alert_rows(df, sampled_machine_ids)

    # 시각화
    plot_score_distribution(
        df,
        output_dir
    )

    plot_machine_anomaly_rate(
        machine_df,
        output_dir
    )

    plot_time_anomaly_rate(
        time_df,
        output_dir
    )

    plot_model_comparison(
        comparison_df,
        output_dir,
    )

    plot_pre_failure_profile(
        alert_profile_df,
        output_dir,
    )

    plot_sampled_machine_alert_timeline(
        sampled_alerts_df,
        failures_df,
        output_dir,
    )

    # 민감도
    sensitivity_df = contamination_sensitivity(
        model_path,
        df
    )

    # 저장
    machine_df.to_csv(
        output_dir / "machine_anomaly_rate.csv",
        index=False
    )

    time_df.to_csv(
        output_dir / "time_anomaly_rate.csv",
        index=False
    )

    events_df.to_csv(
        output_dir / "anomaly_events.csv",
        index=False
    )

    sensitivity_df.to_csv(
        output_dir / "contamination_sensitivity.csv",
        index=False
    )

    df.loc[:, [
        "machineID", "as_of", "is_anomaly", "three_sigma_alert", "iqr_alert"
    ]].to_csv(
        output_dir / "model_alerts.csv",
        index=False,
    )

    baseline_thresholds.to_csv(
        output_dir / "baseline_thresholds.csv",
        index=False,
    )

    comparison_df.to_csv(
        output_dir / "model_failure_comparison.csv",
        index=False,
    )

    component_comparison_df.to_csv(
        output_dir / "component_failure_comparison.csv",
        index=False,
    )

    all_model_events_df.to_csv(
        output_dir / "all_model_alert_events.csv",
        index=False,
    )

    alert_profile_df.to_csv(
        output_dir / "pre_failure_alert_profile.csv",
        index=False,
    )

    method_summary_df.to_csv(
        output_dir / "unlabeled_method_summary.csv",
        index=False,
    )

    agreement_df.to_csv(
        output_dir / "pairwise_alert_agreement.csv",
        index=False,
    )

    incremental_value_df.to_csv(
        output_dir / "incremental_alert_value.csv",
        index=False,
    )

    sampled_alerts_df.to_csv(
        output_dir / "sampled_machine_alert_timeline.csv",
        index=False,
    )

    pd.DataFrame({
        "machineID": sampled_machine_ids,
        "sample_seed": sample_seed,
    }).to_csv(
        output_dir / "sampled_machine_ids.csv",
        index=False,
    )

    # 최종 요약
    summary = {
        **basic,
        **threshold_info,
        **events,
    }

    summary_df = pd.DataFrame(
        [summary]
    )

    summary_df.to_csv(
        output_dir / "metrics_summary.csv",
        index=False
    )

    # 콘솔 출력
    print("\n========== Isolation Forest Evaluation ==========\n")

    print("[Basic]")
    print(
        f"Test observations : {basic['total_rows']:,}"
    )
    print(
        f"Anomaly observations : {basic['anomaly_rows']:,}"
    )
    print(
        f"Anomaly rate : {basic['anomaly_rate']:.2%}"
    )

    print("\n[Score]")
    print(
        f"Mean : {basic['score_mean']:.6f}"
    )
    print(
        f"Median : {basic['score_median']:.6f}"
    )
    print(
        f"Std : {basic['score_std']:.6f}"
    )
    print(
        f"Min : {basic['score_min']:.6f}"
    )
    print(
        f"Max : {basic['score_max']:.6f}"
    )

    print("\n[Threshold]")
    print(
        f"Threshold : {threshold_info['threshold']:.6f}"
    )
    print(
        f"Near threshold rate : "
        f"{threshold_info['near_threshold_rate']:.2%}"
    )

    print("\n[Anomaly Events]")
    print(
        f"Event count : {events['event_count']:,}"
    )
    print(
        f"Mean duration : "
        f"{events['mean_duration_hours']:.2f} hours"
    )
    print(
        f"Median duration : "
        f"{events['median_duration_hours']:.2f} hours"
    )
    print(
        f"Max duration : "
        f"{events['max_duration_hours']:.2f} hours"
    )

    print("\n[Saved]")
    print(
        f"Output directory : {output_dir}"
    )

    print("\n[Failure Prediction Comparison]")
    display_columns = [
        "model", "horizon_hours", "alert_rate", "failure_detection_rate",
        "alert_precision", "false_alert_rate", "mean_lead_time_hours", "lift",
    ]
    print(comparison_df[display_columns].to_string(index=False))

    print("\n[Unlabeled Method Summary]")
    print(method_summary_df.to_string(index=False))

    print("\n[Pairwise Hourly Alert Agreement]")
    print(agreement_df.to_string(index=False))

    print(
        f"\n[Sampled Machines] seed={sample_seed}: "
        + ", ".join(map(str, sampled_machine_ids))
    )

    return {
        "method_summary": method_summary_df,
        "agreement": agreement_df,
        "incremental_value": incremental_value_df,
        "sampled_machine_ids": sampled_machine_ids,
    }



# ---------------------------------------------------------
# 12. CLI
# ---------------------------------------------------------

def main():

    parser = argparse.ArgumentParser(
        description="Evaluate Isolation Forest without anomaly labels."
    )

    parser.add_argument(
        "--predictions",
        type=Path,
        default=DEFAULT_PREDICTIONS
    )

    parser.add_argument(
        "--model",
        type=Path,
        default=DEFAULT_MODEL
    )

    parser.add_argument(
        "--failures",
        type=Path,
        default=DEFAULT_FAILURES
    )

    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_DATASET
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT
    )

    parser.add_argument(
        "--sample-size",
        type=int,
        default=4,
        help="Number of machines in the hourly comparison chart (default: 4)",
    )

    parser.add_argument(
        "--sample-seed",
        type=int,
        default=42,
        help="Random seed for reproducible machine sampling (default: 42)",
    )

    args = parser.parse_args()

    evaluate(
        predictions_path=args.predictions,
        model_path=args.model,
        failures_path=args.failures,
        dataset_path=args.dataset,
        output_dir=args.output_dir,
        sample_size=args.sample_size,
        sample_seed=args.sample_seed,
    )


if __name__ == "__main__":
    main()
