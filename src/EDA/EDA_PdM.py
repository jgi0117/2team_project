import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from pathlib import Path


# ============================================================
# 0. 설정
# ============================================================

PDM_DIR = Path(r"C:\Users\USER\Desktop\프로젝트\data\raw\azure_pdm")


def style_axis(ax):
    """Apply the shared visual style to a chart axis."""
    ax.set_facecolor("white")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_linewidth(0.8)
    ax.spines["bottom"].set_linewidth(0.8)
    ax.grid(axis="y", linewidth=0.8, alpha=0.25)
    ax.tick_params(axis="both", labelsize=9, length=3)


SENSORS = [
    "volt",
    "rotate",
    "pressure",
    "vibration"
]

# ============================================================
# 1. 데이터 불러오기
# ============================================================

telemetry = pd.read_csv(
    PDM_DIR / "PdM_telemetry.csv",
    parse_dates=["datetime"]
)

failures = pd.read_csv(
    PDM_DIR / "PdM_failures.csv",
    parse_dates=["datetime"]
)


# ============================================================
# ① 센서별 값의 분포
#
# 질문:
#   센서마다 값의 범위와 분포가 어떻게 다른가?
#
# 연결:
#   → 센서의 현재값뿐 아니라
#     평균 / 표준편차 / 변화량 등의 Feature 활용
# ============================================================

fig, axes = plt.subplots(
    2, 2,
    figsize=(10.5, 6.5)
)

for ax, sensor in zip(
    axes.ravel(),
    SENSORS
):

    ax.hist(
        telemetry[sensor].dropna(),
        bins=40,
        alpha=0.85
    )

    ax.set_title(
        sensor,
        fontsize=10,
        pad=7
    )

    ax.set_xlabel(
        "Sensor value",
        fontsize=9
    )

    ax.set_ylabel(
        "Frequency",
        fontsize=9
    )

    style_axis(ax)


fig.suptitle(
    "Sensor value distribution",
    fontsize=12,
    y=0.99
)

fig.subplots_adjust(
    left=0.08,
    right=0.98,
    bottom=0.10,
    top=0.88,
    wspace=0.22,
    hspace=0.30
)

plt.show()
plt.close()


# ============================================================
# ② 부품별 고장 발생량
#
# 질문:
#   부품별 고장 발생량이 동일한가?
#
# 연결:
#   → 부품별 Label 구성
#   → 부품별 예측 문제
# ============================================================

failure_count = (
    failures["failure"]
    .value_counts()
    .reindex(
        ["comp1", "comp2", "comp3", "comp4"],
        fill_value=0
    )
)

fig, ax = plt.subplots(
    figsize=(8.5, 4.5)
)

bars = ax.bar(
    failure_count.index,
    failure_count.values
)

ax.set_title(
    "Failure events by component",
    fontsize=11,
    pad=9
)

ax.set_xlabel(
    "Component",
    fontsize=9
)

ax.set_ylabel(
    "Failure events",
    fontsize=9
)

# 막대 위 값 표시
for bar, value in zip(
    bars,
    failure_count.values
):
    ax.text(
        bar.get_x() + bar.get_width() / 2,
        bar.get_height(),
        f"{value:,}",
        ha="center",
        va="bottom",
        fontsize=8.5
    )

style_axis(ax)

ax.grid(
    axis="y",
    linewidth=0.8,
    alpha=0.25
)

fig.subplots_adjust(
    left=0.09,
    right=0.98,
    bottom=0.15,
    top=0.86
)

plt.show()
plt.close()


# ============================================================
# ③ 반복 고장까지의 간격
#
# 질문:
#   동일 설비에서 고장이 반복되는 특성이 있는가?
#
# 연결:
#   → 과거 고장 이력 활용
#   → 고장 횟수 / 마지막 고장 이후 경과시간 Feature
# ============================================================

failure_sorted = (
    failures
    .sort_values(
        ["machineID", "datetime"]
    )
    .copy()
)

failure_sorted["previous_failure"] = (
    failure_sorted
    .groupby("machineID")["datetime"]
    .shift()
)

failure_interval = (
    failure_sorted["datetime"]
    - failure_sorted["previous_failure"]
)

failure_interval = (
    failure_interval
    .dt.total_seconds()
    .div(86400)
    .dropna()
)

fig, ax = plt.subplots(
    figsize=(8.5, 4.5)
)

ax.hist(
    failure_interval.clip(upper=180),
    bins=30,
    alpha=0.85
)

ax.set_title(
    "Interval between repeated failures",
    fontsize=11,
    pad=9
)

ax.set_xlabel(
    "Days",
    fontsize=9
)

ax.set_ylabel(
    "Failure transitions",
    fontsize=9
)

style_axis(ax)

fig.subplots_adjust(
    left=0.09,
    right=0.98,
    bottom=0.15,
    top=0.86
)

plt.show()
plt.close()


# ============================================================
# ④ 고장 전 센서 수준 변화
#
# 질문:
#   고장에 가까워질수록 센서 수준이 변하는가?
#
# 연결:
#   → Rolling mean
#   → Trend
#   → Deviation / Z-score
# ============================================================

trajectory_rows = []

for machine_id, failure_group in failures.groupby(
    "machineID"
):

    machine_telemetry = (
        telemetry[
            telemetry["machineID"] == machine_id
        ]
        .sort_values("datetime")
    )

    for failure in failure_group.itertuples(
        index=False
    ):

        window = machine_telemetry[
            (
                machine_telemetry["datetime"]
                >= failure.datetime
                - pd.Timedelta(days=30)
            )
            &
            (
                machine_telemetry["datetime"]
                <= failure.datetime
            )
        ].copy()

        if window.empty:
            continue

        window["days_before"] = (
            (
                failure.datetime
                - window["datetime"]
            )
            .dt.total_seconds()
            .div(86400)
            .round()
            .astype(int)
            .clip(0, 30)
        )

        daily_mean = (
            window
            .groupby("days_before")[SENSORS]
            .mean()
            .reset_index()
        )

        trajectory_rows.append(
            daily_mean
        )


trajectory = pd.concat(
    trajectory_rows,
    ignore_index=True
)


# 센서별 표준화
for sensor in SENSORS:

    trajectory[sensor] = (
        trajectory[sensor]
        - telemetry[sensor].mean()
    ) / telemetry[sensor].std()


trajectory_mean = (
    trajectory
    .groupby("days_before")[SENSORS]
    .mean()
    .sort_index()
)


fig, ax = plt.subplots(
    figsize=(9.5, 4.8)
)

for sensor in SENSORS:

    ax.plot(
        trajectory_mean.index,
        trajectory_mean[sensor],
        marker="o",
        markersize=2.5,
        linewidth=1.6,
        label=sensor
    )

# 기준선
ax.axhline(
    0,
    linestyle=":",
    linewidth=0.9,
    alpha=0.7
)

ax.invert_xaxis()

ax.set_title(
    "Standardized sensor level before failure",
    fontsize=11,
    pad=9
)

ax.set_xlabel(
    "Days before failure",
    fontsize=9
)

ax.set_ylabel(
    "Standardized level",
    fontsize=9
)

# 범례를 위쪽에 한 줄로 배치
ax.legend(
    ncol=4,
    loc="upper center",
    bbox_to_anchor=(0.5, 1.14),
    frameon=False,
    fontsize=8.5,
    handlelength=1.8,
    columnspacing=1.2
)

style_axis(ax)

fig.subplots_adjust(
    left=0.09,
    right=0.98,
    bottom=0.16,
    top=0.79
)

plt.show()
plt.close()


# ============================================================
# ⑤ 고장 전 센서 변동성
#
# 질문:
#   고장에 가까워질수록 센서 변동성이 증가하는가?
#
# 연결:
#   → 현재 EDA에서 뚜렷한 증가가 없으면
#     이 그래프만으로 std/range의 필요성을
#     주장하지 않음
# ============================================================

volatility_rows = []

for machine_id, failure_group in failures.groupby(
    "machineID"
):

    machine_telemetry = (
        telemetry[
            telemetry["machineID"] == machine_id
        ]
        .sort_values("datetime")
    )

    for failure in failure_group.itertuples(
        index=False
    ):

        window = machine_telemetry[
            (
                machine_telemetry["datetime"]
                >= failure.datetime
                - pd.Timedelta(days=30)
            )
            &
            (
                machine_telemetry["datetime"]
                <= failure.datetime
            )
        ].copy()

        if window.empty:
            continue

        window["days_before"] = (
            (
                failure.datetime
                - window["datetime"]
            )
            .dt.total_seconds()
            .div(86400)
            .round()
            .astype(int)
            .clip(0, 30)
        )

        daily_std = (
            window
            .groupby("days_before")[SENSORS]
            .std()
            .reset_index()
        )

        volatility_rows.append(
            daily_std
        )


volatility = pd.concat(
    volatility_rows,
    ignore_index=True
)

volatility_mean = (
    volatility
    .groupby("days_before")[SENSORS]
    .mean()
    .sort_index()
)


fig, ax = plt.subplots(
    figsize=(9.5, 4.8)
)

for sensor in SENSORS:

    ax.plot(
        volatility_mean.index,
        volatility_mean[sensor],
        marker="o",
        markersize=2.5,
        linewidth=1.6,
        label=sensor
    )

ax.invert_xaxis()

ax.set_title(
    "Sensor variability before failure",
    fontsize=11,
    pad=9
)

ax.set_xlabel(
    "Days before failure",
    fontsize=9
)

ax.set_ylabel(
    "Mean variability",
    fontsize=9
)

ax.legend(
    ncol=4,
    loc="upper center",
    bbox_to_anchor=(0.5, 1.14),
    frameon=False,
    fontsize=8.5,
    handlelength=1.8,
    columnspacing=1.2
)

style_axis(ax)

fig.subplots_adjust(
    left=0.09,
    right=0.98,
    bottom=0.16,
    top=0.79
)

# ============================================================
# 0-1. 그래프 디자인
# ============================================================

font_path = Path(r"C:/Windows/Fonts/malgun.ttf")

if font_path.exists():
    font_name = fm.FontProperties(
        fname=font_path
    ).get_name()

    plt.rcParams["font.family"] = font_name

plt.rcParams["axes.unicode_minus"] = False


plt.show()
plt.close()
