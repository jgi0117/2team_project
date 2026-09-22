"""
실행: python -m src.data_pipeline.step3_labels
출력  _work/train_table.parquet   학습용 (한 행 = 한 판단)
      _work/seq_bundle.npz        딥러닝용 30일 묶음
      data/processed/labels.csv   계약서 규격 (긴 형식)
      data/processed/features.csv 계약서 규격

★ 절대 규칙
   판단시점 t 에서  입력 = t-1 까지,  정답 = t 부터 t+H-1 까지.
   이 선이 무너지면 시험점수만 좋고 실전은 망한다.
"""
import numpy as np
import pandas as pd
from src.common.paths import WORK, PROCESSED
from src.common.contract import *
from src.common import labels

p = pd.read_parquet(WORK / "features.parquet")
p = p.sort_values(["machineID", "date"]).reset_index(drop=True)
machines = sorted(p.machineID.unique())
dates = pd.date_range(DATA_START, DATA_END, freq="D")

print("1/4 정답 만드는 중...")
_, ind = labels.failure_grid(machines, dates)
mid = p["machineID"].values
lab = p[["machineID", "date"]].copy()
for c in COMPONENTS:
    v = ind.get(c, np.zeros(len(p)))
    for H in HORIZONS:
        lab[f"y_{c}_{H}"] = labels.forward_label(v, mid, H)
        lab[f"ok_{c}_{H}"] = (p["date"] + pd.Timedelta(days=H - 1) <= DATA_END).astype(int)

print("2/4 경계선 긋는 중 (입력은 어제까지, 정답은 오늘부터)...")
feat = p.copy()
feat[COL_ASOF] = feat["date"] + pd.Timedelta(days=1)
lab = lab.rename(columns={"date": COL_ASOF})
ds = feat.drop(columns=["date"]).merge(lab, on=["machineID", COL_ASOF], how="inner")
ds = ds[ds[COL_ASOF] >= DATA_START + pd.Timedelta(days=WARMUP_DAYS)].reset_index(drop=True)
ds["split"] = np.where(ds[COL_ASOF] <= TRAIN_END, "train", "test")
ds.to_parquet(WORK / "train_table.parquet", index=False)

print("3/4 딥러닝용 시퀀스...")
SEQ = ([f"{s}_mean" for s in SENSORS] + [f"{s}_std" for s in SENSORS]
       + [f"{e}_7d" for e in ERRORS] + ["err_any_7d", "was_missing"])
STATIC = ([f"dsr_{c}" for c in COMPONENTS] + [f"dsf_{c}" for c in COMPONENTS]
          + [f"nfail_{c}" for c in COMPONENTS] + ["age", "model_num"]
          + [f"{s}_z" for s in SENSORS] + [f"{s}_trend" for s in SENSORS])

m2i = {m: i for i, m in enumerate(machines)}
d2i = {d: i for i, d in enumerate(dates)}
cube = np.zeros((len(machines), len(dates), len(SEQ)), dtype=np.float32)
cube[p.machineID.map(m2i).values, p.date.map(d2i).values] = p[SEQ].fillna(0).values

ycols  = [f"y_{c}_{H}" for c in COMPONENTS for H in HORIZONS]
okcols = [f"ok_{c}_{H}" for c in COMPONENTS for H in HORIZONS]
np.savez_compressed(
    WORK / "seq_bundle.npz", cube=cube,
    rowm=ds.machineID.map(m2i).values,
    rowd=(ds[COL_ASOF] - pd.Timedelta(days=1)).map(d2i).values,
    static=ds[STATIC].fillna(0).values.astype(np.float32),
    y=ds[ycols].values.astype(np.float32),
    mask=ds[okcols].values.astype(np.float32),
    asof=ds[COL_ASOF].values.astype("datetime64[D]").astype(int),
    machine=ds.machineID.values,
    seq_cols=np.array(SEQ), static_cols=np.array(STATIC))

print("4/4 계약서 규격으로 내보내는 중...")
exp = ds[ds[COL_ASOF].isin(pd.date_range(DATA_START, DATA_END, freq=EXPORT_FREQ))]
rows = []
for c in COMPONENTS:
    for H in HORIZONS:
        rows.append(pd.DataFrame({
            COL_MACHINE: exp.machineID.values, COL_COMP: c,
            COL_ASOF: exp[COL_ASOF].dt.date.values, COL_H: H,
            COL_Y: exp[f"y_{c}_{H}"].values, COL_OK: exp[f"ok_{c}_{H}"].values,
            "split": exp["split"].values, "label_version": labels.LABEL_VERSION}))
pd.concat(rows).to_csv(PROCESSED / "labels.csv", index=False)

fcols = [c for c in exp.columns if not c.startswith(("y_", "ok_"))]
exp[fcols].assign(**{COL_ASOF: exp[COL_ASOF].dt.date}).to_csv(
    PROCESSED / "features.csv", index=False)

print(f"✅ 학습표 {len(ds):,}행 / 내보내기 {len(exp):,}시점")
print("\n[부품별 고장 비율] 0%거나 60% 넘으면 이상신호")
for c in COMPONENTS:
    r = [f"{H}일 {ds.loc[ds[f'ok_{c}_{H}']==1, f'y_{c}_{H}'].mean():5.1%}"
         for H in HORIZONS]
    print(f"  {c}  " + " | ".join(r))
