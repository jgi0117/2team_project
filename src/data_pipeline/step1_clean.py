"""
실행: python -m src.data_pipeline.step1_clean
하는 일  ① 중복 제거  ② 빠진 날 자리 만들기  ③ 이상값 처리  ④ 하루 단위 요약
출력    data/processed/_work/daily_panel.parquet
"""
import numpy as np
import pandas as pd
from src.common.paths import RAW_PDM, WORK, find
from src.common.contract import *

print("1/6 읽는 중 (87만 행, 20초쯤)...")
tel = pd.read_csv(find(RAW_PDM, "telemetry"), parse_dates=["datetime"])
err = pd.read_csv(find(RAW_PDM, "error"), parse_dates=["datetime"])
mch = pd.read_csv(find(RAW_PDM, "machine"))

b = len(tel)
tel = tel.drop_duplicates(subset=["machineID", "datetime"], keep="last")
print(f"2/6 중복 {b - len(tel):,}행 제거")

# 이상값 기준은 '학습 구간에서만' 계산한다. 시험 구간을 미리 보면 안 되기 때문.
print("3/6 이상값 점검 (기준: 학습구간 평균 ± 6σ)")
trn = tel[tel.datetime <= TRAIN_END]
for s in SENSORS:
    mu, sd = trn[s].mean(), trn[s].std()
    lo, hi = mu - 6 * sd, mu + 6 * sd
    n = int(((tel[s] < lo) | (tel[s] > hi)).sum())
    tel.loc[(tel[s] < lo) | (tel[s] > hi), s] = np.nan
    print(f"    {s:9s} 정상범위 {lo:8.1f} ~ {hi:8.1f}   벗어남 {n:,}개")

print("4/6 하루 단위 요약...")
tel["date"] = tel["datetime"].dt.normalize()
agg = tel.groupby(["machineID", "date"])[SENSORS].agg(["mean", "std", "min", "max"])
agg.columns = [f"{s}_{a}" for s, a in agg.columns]
agg["n_obs"] = tel.groupby(["machineID", "date"]).size()
agg = agg.reset_index()

machines = sorted(tel.machineID.unique())
dates = pd.date_range(DATA_START, DATA_END, freq="D")
panel = pd.MultiIndex.from_product([machines, dates],
                                   names=["machineID", "date"]).to_frame(index=False)
panel = panel.merge(agg, on=["machineID", "date"], how="left")

miss = int(panel["n_obs"].isna().sum())
short = int((panel["n_obs"].fillna(0) < 24).sum()) - miss
print(f"5/6 완전히 빈 날 {miss:,}개 / 24시간 미만인 날 {short:,}개 → 앞값으로 채움")
panel["was_missing"] = panel["n_obs"].isna().astype(int)
panel["n_obs"] = panel["n_obs"].fillna(0)

panel = panel.sort_values(["machineID", "date"]).reset_index(drop=True)
scols = [c for c in panel.columns if any(c.startswith(s + "_") for s in SENSORS)]
g = panel.groupby("machineID")
panel[scols] = g[scols].ffill()
panel[scols] = panel.groupby("machineID")[scols].bfill()

err["date"] = err["datetime"].dt.normalize()
ec = err.pivot_table(index=["machineID", "date"], columns="errorID",
                     aggfunc="size", fill_value=0).reset_index()
panel = panel.merge(ec, on=["machineID", "date"], how="left")
for e in ERRORS:
    if e not in panel.columns:
        panel[e] = 0
    panel[e] = panel[e].fillna(0).astype(int)

panel = panel.merge(mch, on="machineID", how="left")
panel = panel.sort_values(["machineID", "date"]).reset_index(drop=True)
panel.to_parquet(WORK / "daily_panel.parquet", index=False)

print(f"6/6 ✅ {len(panel):,}행 × {panel.shape[1]}열 → _work/daily_panel.parquet")
print(f"    남은 결측 셀 {int(panel.isna().sum().sum())}개 (0이어야 정상)")
