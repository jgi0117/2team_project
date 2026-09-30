import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import json

# ============================================================
# 0. 파일 경로
# ============================================================
# data/
#   operations/
#       costs.csv
#       generation_report.json
#       inventory_lots.csv
#       inventory_movements.csv
#       maintenance_records.csv
#       part_master.csv
#       purchase_orders.csv

def style_axis(ax):
    """Apply the shared visual style to a chart axis."""
    ax.set_facecolor("white")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_linewidth(0.8)
    ax.spines["bottom"].set_linewidth(0.8)
    ax.grid(axis="y", linewidth=0.8, alpha=0.25)
    ax.tick_params(axis="both", labelsize=9, length=3)


OPS_DIR = Path(r"data/operations")
COMPONENTS = ["comp1", "comp2", "comp3", "comp4"]

# ============================================================
# 1. 데이터 불러오기
# ============================================================
part_master = pd.read_csv(OPS_DIR / "part_master.csv")

inventory = pd.read_csv(
    OPS_DIR / "inventory_lots.csv",
    parse_dates=["received_at", "use_by_at", "ready_at", "as_of"]
)

movements = pd.read_csv(
    OPS_DIR / "inventory_movements.csv",
    parse_dates=["occurred_at"]
)

maintenance = pd.read_csv(
    OPS_DIR / "maintenance_records.csv",
    parse_dates=["planned_at", "completed_at", "source_event_at"]
)

purchase = pd.read_csv(
    OPS_DIR / "purchase_orders.csv",
    parse_dates=["ordered_at", "expected_receipt_at", "actual_receipt_at"]
)

costs = pd.read_csv(OPS_DIR / "costs.csv")

with open(OPS_DIR / "generation_report.json", encoding="utf-8") as f:
    report = json.load(f)

plt.rcParams["axes.unicode_minus"] = False


# ============================================================
# EDA ① 부품별 90일 평균 수요
# 한국어 이름: 부품별 수요 추이
#
# 목적:
#   부품별 교체 수요 수준과 시간에 따른 변동을 확인하고,
#   최근 90일 수요를 발주량 산정에 활용할 근거를 확인한다.
# ============================================================
demand = (
    maintenance
    .assign(date=maintenance["source_event_at"].dt.floor("D"))
    .groupby(["date", "component"])["quantity_requested"]
    .sum()
    .reset_index()
)

daily_demand = (
    demand
    .pivot(index="date", columns="component", values="quantity_requested")
    .reindex(columns=COMPONENTS)
    .fillna(0)
)

rolling_90d = daily_demand.rolling("90D", min_periods=1).mean()

fig, ax = plt.subplots(figsize=(10, 5))

# 실제 일별 수요: 변동성을 보여주기 위한 얇은 선
for comp in COMPONENTS:
    ax.plot(
        daily_demand.index,
        daily_demand[comp],
        linewidth=0.8,
        alpha=0.25
    )

# 최근 90일 이동평균: 발주 수요 수준을 보기 위한 굵은 선
for comp in COMPONENTS:
    ax.plot(
        rolling_90d.index,
        rolling_90d[comp],
        label=comp,
        linewidth=2
    )

ax.set_title("90-day rolling average of daily demand")
ax.set_xlabel("Reference date")
ax.set_ylabel("Average daily demand")
ax.legend(ncol=4, frameon=False)

fig.tight_layout()
plt.show()


# ============================================================
# EDA ② 부품별 대응시간과 사용기한
# 한국어 이름: 부품별 대응시간 vs 사용기한
#
# 목적:
#   부품마다 조달기간·정비 준비기간·사용기한이 다름을 확인한다.
#   조달 + 준비시간을 실제 대응에 필요한 시간으로 계산한다.
# ============================================================
pm = part_master.set_index("component").reindex(COMPONENTS).copy()

pm["response_days"] = (
    pm["lead_time_days"] + pm["preparation_days"]
)

x = np.arange(len(COMPONENTS))
width = 0.36

fig, ax = plt.subplots(figsize=(9, 5))

ax.bar(
    x - width / 2,
    pm["response_days"],
    width,
    label="Lead + preparation"
)

ax.bar(
    x + width / 2,
    pm["shelf_life_days"],
    width,
    label="Shelf life"
)

ax.set_xticks(x)
ax.set_xticklabels(COMPONENTS)
ax.set_xlabel("Component")
ax.set_ylabel("Days")
ax.set_title("Response time vs shelf life")
ax.legend(frameon=False)

fig.tight_layout()
plt.show()

print("\n[부품별 대응시간]")
print(
    pm[
        [
            "lead_time_days",
            "preparation_days",
            "response_days",
            "shelf_life_days"
        ]
    ]
)


# ============================================================
# EDA ③ 계획 조달기간 vs 실제 조달기간
# 한국어 이름: 계획 조달기간 vs 실제 조달기간
#
# 목적:
#   예정 입고일과 실제 입고일 사이의 차이를 확인한다.
#   실제 입고가 완료된 발주만 실제 조달기간을 계산한다.
#   미입고 주문의 actual_receipt_at 결측은 임의로 대체하지 않는다.
# ============================================================
received = purchase[
    purchase["actual_receipt_at"].notna()
].copy()

received["planned_lead"] = (
    received["expected_receipt_at"] - received["ordered_at"]
).dt.total_seconds() / 86400

received["actual_lead"] = (
    received["actual_receipt_at"] - received["ordered_at"]
).dt.total_seconds() / 86400

received["delay_days"] = (
    received["actual_receipt_at"]
    - received["expected_receipt_at"]
).dt.total_seconds() / 86400

lead = (
    received
    .groupby("component")[["planned_lead", "actual_lead"]]
    .mean()
    .reindex(COMPONENTS)
)

x = np.arange(len(COMPONENTS))
width = 0.35

fig, ax = plt.subplots(figsize=(9, 5))

ax.bar(
    x - width / 2,
    lead["planned_lead"],
    width,
    label="Planned"
)

ax.bar(
    x + width / 2,
    lead["actual_lead"],
    width,
    label="Actual"
)

ax.set_xticks(x)
ax.set_xticklabels(COMPONENTS)
ax.set_xlabel("Component")
ax.set_ylabel("Days")
ax.set_title("Planned vs actual procurement lead time")
ax.legend(frameon=False)

fig.tight_layout()
plt.show()

late_rate = (
    received.assign(late=received["delay_days"] > 0)
    .groupby("component")["late"]
    .mean()
    .reindex(COMPONENTS)
    * 100
)

print("\n[계획 대비 실제 조달 지연 비율]")
print(late_rate.round(1))


# ============================================================
# EDA ④ 과거 재고 부족 대기 경험
# 한국어 이름: 부품별 재고 부족 대기 경험
#
# 목적:
#   과거 운영기간 동안 발생한 수요 중 재고 부족을 경험한 수요가
#   부품별로 얼마나 있었는지 확인한다.
#
# 주의:
#   generation_report의 ever_waited는 생성 과정에서 집계된
#   '한 번이라도 재고 부족을 경험한 수요'이다.
#   현재 최종적으로 waiting_for_stock인 건수와는 다른 지표다.
# ============================================================
ever_waited = pd.Series({
    comp: report["component_summary"][comp]["ever_waited"]
    for comp in COMPONENTS
})

demand_total = pd.Series({
    comp: report["component_summary"][comp]["demand"]
    for comp in COMPONENTS
})

ever_waited_rate = (
    ever_waited / demand_total * 100
).round(1)

fig, ax = plt.subplots(figsize=(9, 5))

bars = ax.bar(
    COMPONENTS,
    ever_waited.values
)

for bar, value in zip(bars, ever_waited.values):
    ax.text(
        bar.get_x() + bar.get_width() / 2,
        bar.get_height() + 2,
        f"{int(value)}",
        ha="center"
    )

ax.set_xlabel("Component")
ax.set_ylabel("Demand events")
ax.set_title("Historical stock waiting by component")

fig.tight_layout()
plt.show()

print("\n[부품별 재고 부족 대기 경험]")
print(
    pd.DataFrame({
        "demand": demand_total,
        "ever_waited": ever_waited,
        "ever_waited_rate_%": ever_waited_rate
    })
)


# ============================================================
# EDA ⑤ 비용 구조
# 한국어 이름: 부품별 주요 비용 비교
#
# 목적:
#   비용 항목의 규모 차이를 확인한다.
#   이번 EDA에서는 '비용 최적화가 필요하다'는 당연한 명제를
#   증명하려는 것이 아니라, 이후 의사결정에서 어떤 비용을
#   고려해야 하는지 데이터 구조를 확인한다.
#
#   복잡도를 줄이기 위해 핵심 운영비용 4개만 표시:
#   구매비 / 예방정비 / 긴급정비 / 설비정지
# ============================================================
cost_wide = (
    costs
    .pivot_table(
        index="component",
        columns="cost_type",
        values="amount",
        aggfunc="first"
    )
    .reindex(COMPONENTS)
)

main_cost_types = [
    "purchase",
    "preventive_labor",
    "emergency_labor",
    "downtime"
]

main_cost_types = [
    c for c in main_cost_types
    if c in cost_wide.columns
]

fig, ax = plt.subplots(figsize=(9, 5))

cost_wide[main_cost_types].plot(
    kind="bar",
    ax=ax,
    width=0.75
)

ax.set_xlabel("Component")
ax.set_ylabel("Cost (KRW)")
ax.set_title("Major operating costs by component")
ax.ticklabel_format(axis="y", style="plain")
ax.legend(frameon=False)

fig.tight_layout()
plt.show()

print("\n[주요 비용]")
print(cost_wide[main_cost_types])


# ============================================================
# 최종 요약
# ============================================================
print("\n" + "=" * 60)
print("Operations EDA Summary")
print("=" * 60)

print("""
① 부품별 수요 추이
   → 최근 수요 수준과 변동을 확인하고 90일 수요를 활용

② 부품별 대응시간 vs 사용기한
   → 부품마다 필요한 대응시간이 다르므로 부품별 Horizon을 적용

③ 계획 조달기간 vs 실제 조달기간
   → 계획과 실제 조달기간의 차이를 확인하고 조달 지연을 관리

④ 부품별 재고 부족 대기 경험
   → 과거 수요에서 재고 부족 경험의 부품별 차이를 확인

⑤ 부품별 주요 비용 비교
   → 구매·예방정비·긴급정비·설비정지 등 의사결정에 필요한
     비용 항목의 규모를 확인
""")
