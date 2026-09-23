
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

# ============================================================
# 0. 파일 경로
# ============================================================
PDM_DIR = Path("./pdm")       # PdM CSV 5개가 있는 폴더
OPS_DIR = Path("./ops")       # 운영 데이터 CSV 폴더

# ============================================================
# 1. 데이터 불러오기
# ============================================================
telemetry = pd.read_csv(PDM_DIR / "PdM_telemetry.csv", parse_dates=["datetime"])
failures = pd.read_csv(PDM_DIR / "PdM_failures.csv", parse_dates=["datetime"])
maint = pd.read_csv(PDM_DIR / "PdM_maint.csv", parse_dates=["datetime"])
errors = pd.read_csv(PDM_DIR / "PdM_errors.csv", parse_dates=["datetime"])
machines = pd.read_csv(PDM_DIR / "PdM_machines.csv")

part_master = pd.read_csv(OPS_DIR / "part_master.csv")
inventory = pd.read_csv(OPS_DIR / "inventory_lots.csv",
                        parse_dates=["received_at", "use_by_at", "ready_at", "as_of"])
purchase = pd.read_csv(OPS_DIR / "purchase_orders.csv",
                       parse_dates=["ordered_at", "expected_receipt_at", "actual_receipt_at"])
costs = pd.read_csv(OPS_DIR / "costs.csv")

plt.rcParams["axes.unicode_minus"] = False

# ============================================================
# 2. EDA ① 부품별 고장 건수
# 목적: 어떤 부품에 고장이 많이 발생했는지 확인
# ============================================================
failure_count = (
    failures["failure"]
    .value_counts()
    .reindex(["comp1", "comp2", "comp3", "comp4"])
)

plt.figure(figsize=(8, 4.5))
plt.bar(failure_count.index, failure_count.values)
plt.title("Failure count by component")
plt.xlabel("Component")
plt.ylabel("Failure events")
plt.show()

# ============================================================
# 3. EDA ② 월별 고장 추이
# 목적: 고장이 특정 시기에 몰리는지, 시간 흐름에 패턴이 있는지 확인
# ============================================================
monthly_failure = failures.set_index("datetime").resample("MS").size()

plt.figure(figsize=(9, 4.5))
plt.plot(monthly_failure.index, monthly_failure.values, marker="o")
plt.title("Monthly failure events")
plt.xlabel("Month")
plt.ylabel("Failure events")
plt.xticks(rotation=45)
plt.show()

# ============================================================
# 4. EDA ③ 동일 설비의 고장 간격
# 목적: 반복 고장이 얼마나 자주 발생하는지 확인
# 주의: 같은 고장이 여러 행으로 이어지는 문제를 확인할 때 중요
# ============================================================
tmp = failures.sort_values(["machineID", "datetime"]).copy()
tmp["previous_failure"] = tmp.groupby("machineID")["datetime"].shift()

failure_interval = (
    tmp["datetime"] - tmp["previous_failure"]
).dt.total_seconds() / 86400

failure_interval = failure_interval.dropna()

plt.figure(figsize=(8, 4.5))
plt.hist(failure_interval.clip(upper=180), bins=30)
plt.axvline(30, linestyle="--", label="30 days")
plt.title("Interval between consecutive failures")
plt.xlabel("Days")
plt.ylabel("Failure transitions")
plt.legend()
plt.show()

# ============================================================
# 5. EDA ④ 고장 전 센서 변화
# 목적: 고장에 가까워질수록 센서가 실제로 변하는지 확인
# ============================================================
rows = []

for machine_id, failure_group in failures.groupby("machineID"):
    machine_telemetry = telemetry[
        telemetry["machineID"] == machine_id
    ].sort_values("datetime")

    for failure in failure_group.itertuples(index=False):
        window = machine_telemetry[
            (machine_telemetry["datetime"] >= failure.datetime - pd.Timedelta(days=30))
            & (machine_telemetry["datetime"] <= failure.datetime)
        ].copy()

        if window.empty:
            continue

        window["days_before"] = (
            (failure.datetime - window["datetime"])
            .dt.total_seconds() / 86400
        ).round().astype(int).clip(0, 30)

        daily = (
            window.groupby("days_before")
            [["volt", "rotate", "pressure", "vibration"]]
            .mean()
            .reset_index()
        )
        rows.append(daily)

trajectory = pd.concat(rows, ignore_index=True)

# 센서 단위가 서로 달라 한 그래프에서 비교하기 위해 표준화
for col in ["volt", "rotate", "pressure", "vibration"]:
    trajectory[col] = (
        trajectory[col] - telemetry[col].mean()
    ) / telemetry[col].std()

trajectory_mean = (
    trajectory.groupby("days_before")
    [["volt", "rotate", "pressure", "vibration"]]
    .mean()
    .sort_index()
)

plt.figure(figsize=(9, 5))
for col in ["volt", "rotate", "pressure", "vibration"]:
    plt.plot(
        trajectory_mean.index,
        trajectory_mean[col],
        label=col
    )

plt.axhline(0, linestyle=":")
plt.gca().invert_xaxis()
plt.title("Standardized sensor level before failure")
plt.xlabel("Days before failure (0 = failure)")
plt.ylabel("Standardized mean")
plt.legend()
plt.show()

# ============================================================
# 6. EDA ⑤ 고장 전 24시간 오류 발생 여부
# 목적: 오류 데이터가 고장 예측에 쓸 만한 신호인지 탐색
# 주의: 높은 비율이라고 바로 Feature로 확정하면 안 됨.
# 정상 구간과 비교해야 실제 예측력이 있는지 판단 가능
# ============================================================
error_counts = []

for failure in failures.itertuples(index=False):
    count = (
        (errors["machineID"] == failure.machineID)
        & (errors["datetime"] < failure.datetime)
        & (errors["datetime"] >= failure.datetime - pd.Timedelta(hours=24))
    ).sum()
    error_counts.append(count)

failures_eda = failures.copy()
failures_eda["error_24h"] = error_counts

error_rate = (
    failures_eda.groupby("failure")["error_24h"]
    .apply(lambda s: (s >= 1).mean() * 100)
    .reindex(["comp1", "comp2", "comp3", "comp4"])
)

plt.figure(figsize=(8, 4.5))
plt.bar(error_rate.index, error_rate.values)
plt.ylim(0, 100)
plt.title("Failures with >=1 error in previous 24 hours")
plt.xlabel("Failure component")
plt.ylabel("Share of failure events (%)")
plt.show()

# ============================================================
# 7. EDA ⑥ 고장 전 30일 정비 이력
# 목적: 최근 정비 이력이 고장과 함께 자주 나타나는지 확인
# 주의: '정비했다 = 곧 고장'이라고 해석하면 안 됨.
# ============================================================
maintenance_counts = []

for failure in failures.itertuples(index=False):
    count = (
        (maint["machineID"] == failure.machineID)
        & (maint["datetime"] < failure.datetime)
        & (maint["datetime"] >= failure.datetime - pd.Timedelta(days=30))
    ).sum()
    maintenance_counts.append(count)

failures_eda["maint_30d"] = maintenance_counts

maintenance_rate = (
    failures_eda.groupby("failure")["maint_30d"]
    .apply(lambda s: (s >= 1).mean() * 100)
    .reindex(["comp1", "comp2", "comp3", "comp4"])
)

plt.figure(figsize=(8, 4.5))
plt.bar(maintenance_rate.index, maintenance_rate.values)
plt.ylim(0, 100)
plt.title("Failures with >=1 maintenance event in previous 30 days")
plt.xlabel("Failure component")
plt.ylabel("Share of failure events (%)")
plt.show()

# ============================================================
# 8. 운영 데이터 ① 계획 조달기간 vs 실제 조달기간
# 목적: 대시보드의 '조달기간'을 실제 운영 데이터로 설명
# ============================================================
purchase["planned_lead"] = (
    purchase["expected_receipt_at"] - purchase["ordered_at"]
).dt.total_seconds() / 86400

purchase["actual_lead"] = (
    purchase["actual_receipt_at"] - purchase["ordered_at"]
).dt.total_seconds() / 86400

lead = (
    purchase.groupby("component")[["planned_lead", "actual_lead"]]
    .mean()
    .reindex(["comp1", "comp2", "comp3", "comp4"])
)

x = np.arange(len(lead))
width = 0.35

plt.figure(figsize=(8, 4.5))
plt.bar(x - width / 2, lead["planned_lead"], width, label="Planned")
plt.bar(x + width / 2, lead["actual_lead"], width, label="Actual")
plt.xticks(x, lead.index)
plt.ylabel("Days")
plt.title("Planned vs actual procurement lead time")
plt.legend()
plt.show()

# ============================================================
# 9. 운영 데이터 ② 가용 재고 vs 목표재고
# 목적: 모델 결과와 결합했을 때 '대응 가능한가?'를 판단할 기반
# ============================================================
inventory["available_qty"] = (
    inventory["quantity_on_hand"] - inventory["quantity_reserved"]
)

available = (
    inventory.groupby("component")["available_qty"]
    .sum()
    .reindex(["comp1", "comp2", "comp3", "comp4"])
)

target = (
    part_master.set_index("component")["target_stock"]
    .reindex(available.index)
)

x = np.arange(len(available))

plt.figure(figsize=(8, 4.5))
plt.bar(x - width / 2, available.values, width, label="Available")
plt.bar(x + width / 2, target.values, width, label="Target stock")
plt.xticks(x, available.index)
plt.ylabel("Quantity")
plt.title("Available inventory vs target stock")
plt.legend()
plt.show()

# ============================================================
# 10. 대시보드에 바로 연결 가능한 예시
# 특정 설비의 센서 흐름 + 고장 시점
# ============================================================
# 첫 번째로 충분한 telemetry가 있는 고장 사례를 선택
for failure in failures.sort_values("datetime").itertuples(index=False):
    selected = telemetry[
        (telemetry["machineID"] == failure.machineID)
        & (telemetry["datetime"] >= failure.datetime - pd.Timedelta(days=7))
        & (telemetry["datetime"] <= failure.datetime + pd.Timedelta(hours=6))
    ]

    if len(selected) > 50:
        break

plt.figure(figsize=(10, 4.5))

for col in ["volt", "rotate", "pressure", "vibration"]:
    z = (
        selected[col] - telemetry[col].mean()
    ) / telemetry[col].std()

    plt.plot(
        selected["datetime"],
        z,
        label=col
    )

plt.axvline(
    failure.datetime,
    linestyle="--",
    label=f"Failure: {failure.failure}"
)

plt.title(
    f"Machine {failure.machineID} sensor trend around failure"
)
plt.xlabel("Datetime")
plt.ylabel("Standardized sensor value")
plt.xticks(rotation=45)
plt.legend()
plt.tight_layout()
plt.show()
