"""
실행: python -m src.data_pipeline.step2_features
하는 일: 기계가 알아들을 '힌트' 만들기.
  원본은 "오늘 진동 45.2"뿐이라 높은 건지 알 수 없다.
  "평소보다 3배 튀는 중" 같은 형태로 바꿔준다.
출력: data/processed/_work/features.parquet
"""
import numpy as np
import pandas as pd
from src.common.paths import WORK
from src.common.contract import *
from src.common import labels

p = pd.read_parquet(WORK / "daily_panel.parquet")
p = p.sort_values(["machineID", "date"]).reset_index(drop=True)
g = p.groupby("machineID")

print("1/4 센서 힌트...")
for s in SENSORS:
    base = f"{s}_mean"
    for w in (3, 7, 14, 30):
        p[f"{s}_m{w}"] = g[base].transform(lambda x: x.rolling(w, min_periods=2).mean())
        p[f"{s}_s{w}"] = g[base].transform(lambda x: x.rolling(w, min_periods=2).std())
    p[f"{s}_trend"] = p[f"{s}_m7"] - p[f"{s}_m30"]          # 최근이 평소보다 얼마나 벗어났나
    p[f"{s}_z"]     = p[f"{s}_trend"] / (p[f"{s}_s30"] + 1e-6)
    p[f"{s}_rng"]   = p[f"{s}_max"] - p[f"{s}_min"]          # 하루 안 출렁임
    p[f"{s}_rng7"]  = g[f"{s}_rng"].transform(lambda x: x.rolling(7, min_periods=2).mean())

print("2/4 에러 힌트...")
p["err_any"] = p[ERRORS].sum(axis=1)
g = p.groupby("machineID")
for w in (7, 30):
    for e in ERRORS + ["err_any"]:
        p[f"{e}_{w}d"] = g[e].transform(lambda x: x.rolling(w, min_periods=1).sum())
p = p.drop(columns=ERRORS)

print("3/4 '마지막으로 간 지 며칠'...")
ev = labels.load_events()
p = p.sort_values(["date", "machineID"]).reset_index(drop=True)
left = p[["machineID", "date"]]

def days_since(sub):
    if len(sub) == 0:
        return np.full(len(p), np.nan)
    sub = sub[["machineID", "date"]].sort_values("date").assign(last=lambda d: d["date"])
    m = pd.merge_asof(left, sub, on="date", by="machineID", direction="backward")
    return (p["date"].values - m["last"].values) / np.timedelta64(1, "D")

for c in COMPONENTS:
    p[f"dsr_{c}"] = days_since(ev[ev.component == c])                      # 교체 후 경과일 ★
    p[f"dsf_{c}"] = days_since(ev[(ev.component == c) & (ev.is_emergency == 1)])

print("4/4 누적 고장 횟수 + 마무리...")
p = p.sort_values(["machineID", "date"]).reset_index(drop=True)
_, ind = labels.failure_grid(sorted(p.machineID.unique()),
                             pd.date_range(DATA_START, DATA_END, freq="D"))
for c in COMPONENTS:
    t = p[["machineID"]].copy()
    t["v"] = ind.get(c, np.zeros(len(p)))
    p[f"nfail_{c}"] = t.groupby("machineID")["v"].cumsum()
    p[f"dsr_{c}_per_age"] = p[f"dsr_{c}"] / (p["age"] + 1)

p["model_num"] = p["model"].astype(str).str.extract(r"(\d+)").astype(float)
p = p.drop(columns=[c for c in p.columns
                    if c.endswith(("_min", "_max", "_rng"))], errors="ignore")

p.to_parquet(WORK / "features.parquet", index=False)
print(f"✅ {len(p):,}행 × {p.shape[1]}열 → _work/features.parquet")
