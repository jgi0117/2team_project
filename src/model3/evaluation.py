"""
Isolation Forest 비지도 평가.

평가 대상:
1. Anomaly Rate
2. Anomaly Score Distribution
3. Threshold 주변 데이터 비율
4. Machine별 Anomaly Rate
5. 시간별 Anomaly Rate
6. 연속 이상 이벤트
7. contamination 변화에 따른 Anomaly Rate

주의:
- 센서 이상 정답 라벨이 없으므로 Accuracy/Precision/Recall/F1은 계산하지 않는다.
- PdM_failures.csv를 센서 이상 정답으로 사용하지 않는다.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_PREDICTIONS = ROOT / "outputs" / "model3" / "predictions.csv"
DEFAULT_MODEL = ROOT / "outputs" / "model3" / "isolation_forest.joblib"
DEFAULT_OUTPUT = ROOT / "outputs" / "model3" / "evaluation"


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
    df: pd.DataFrame
) -> pd.DataFrame:

    events = []

    for machine_id, group in df.groupby(
        "machineID",
        sort=True
    ):

        group = group.sort_values("as_of").copy()

        anomaly_times = group.loc[
            group["is_anomaly"].eq(1),
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
            "machineID": machine_id,
            "start": start,
            "end": previous,
            "duration_hours": (
                (previous - start)
                / pd.Timedelta(hours=1)
                + 1
            ),
        })

    return pd.DataFrame(events)


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
    output_dir=DEFAULT_OUTPUT,
):

    output_dir = Path(output_dir)
    output_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    df = load_predictions(
        predictions_path
    )

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
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT
    )

    args = parser.parse_args()

    evaluate(
        predictions_path=args.predictions,
        model_path=args.model,
        output_dir=args.output_dir,
    )


if __name__ == "__main__":
    main()