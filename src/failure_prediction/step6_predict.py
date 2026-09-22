"""
실행: python -m src.failure_prediction.step6_predict
출력  data/processed/predictions.csv     계약서 규격 (필수 필드 준수)
      data/processed/model_metrics.csv   계약서 규격 (긴 형식)
      data/processed/risk_curve.csv      확장 필드: 위험 상승 구간

주의: failure_probability 는 아직 보정 전 점수다.
      0.65 가 '65%'라는 뜻이 아니라 '순위가 높다'는 뜻이다.
      calibrated=False 로 표시해 두었다.
"""
import numpy as np
import pandas as pd
from src.common.paths import WORK, PROCESSED
from src.common.contract import *

ml = pd.read_parquet(WORK / "pred_ml.parquet")
try:
    dl = pd.read_parquet(WORK / "pred_dl.parquet")
except FileNotFoundError:
    dl = None
    print("딥러닝 결과 없음 → 머신러닝만 사용")


def to_wide(df):
    w = df.pivot_table(index=[COL_ASOF, COL_MACHINE, COL_COMP],
                       columns=COL_H, values=COL_P)
    H = [h for h in HORIZONS if h in w.columns]
    A = np.maximum.accumulate(w[H].ffill(axis=1).bfill(axis=1).fillna(0).values, axis=1)
    return w.reset_index()[[COL_ASOF, COL_MACHINE, COL_COMP]], A, H


base, A, H = to_wide(ml)
src = "ml"
if dl is not None:
    b2, A2, H2 = to_wide(dl)
    key = [COL_ASOF, COL_MACHINE, COL_COMP]
    if H2 == H and base[key].equals(b2[key]):
        A, src = 0.5 * A + 0.5 * A2, "ensemble"
    else:
        print("⚠️ ml/dl 행이 달라 앙상블 생략")
print(f"사용: {src}")

# ── 계약서 규격 predictions.csv ────────────────────────────────
rows = []
for i, h in enumerate(H):
    rows.append(pd.DataFrame({
        COL_MACHINE: base[COL_MACHINE].values, COL_COMP: base[COL_COMP].values,
        COL_ASOF: pd.to_datetime(base[COL_ASOF]).dt.date, COL_H: h,
        COL_P: A[:, i], COL_VER: MODEL_VERSION,
        "calibrated": False, "source": src}))
pred = pd.concat(rows)
pred = pred[pred[COL_ASOF].isin(
    pd.date_range(DATA_START, DATA_END, freq=EXPORT_FREQ).date)]
pred.to_csv(PROCESSED / "predictions.csv", index=False)

# ── 확장 필드: 위험 상승 구간 (계약서 2항에 따라 별도 파일) ────
xs = np.r_[0, H]
def q(row, pct):
    tot = row[-1]
    return np.nan if tot < 1e-6 else float(np.interp(pct * tot, np.r_[0, row], xs))

# 곡선은 눈금이 일정한 딥러닝 결과만 사용
if dl is not None and src == "ensemble":
    _, A_curve, H_curve = to_wide(dl)
else:
    A_curve, H_curve = A, H


cur = base.copy()
cur["risk_rise_from_days"] = [q(r, 0.20) for r in A]
cur["risk_rise_to_days"]   = [q(r, 0.80) for r in A]
cur["risk_rise_mid_days"]  = [q(r, 0.50) for r in A]
cur["decision_horizon_days"] = cur[COL_COMP].map(DECISION_HORIZON)
cur["p_at_decision_horizon"] = [
    r[H.index(h)] if h in H else np.nan for r, h in zip(A, cur["decision_horizon_days"])]
cur[COL_ASOF] = pd.to_datetime(cur[COL_ASOF]).dt.date
cur[COL_VER], cur["calibrated"] = MODEL_VERSION, False
cur = cur[cur[COL_ASOF].isin(pd.date_range(DATA_START, DATA_END, freq=EXPORT_FREQ).date)]
cur.to_csv(PROCESSED / "risk_curve.csv", index=False)

# ── 계약서 규격 model_metrics.csv ──────────────────────────────
mets = [pd.read_csv(WORK / "metrics_ml.csv")]
if (WORK / "metrics_dl.csv").exists():
    mets.append(pd.read_csv(WORK / "metrics_dl.csv"))
pd.concat(mets).to_csv(PROCESSED / "model_metrics.csv", index=False)

print(f"✅ predictions {len(pred):,}행 / risk_curve {len(cur):,}행\n")
print(cur.nlargest(10, "p_at_decision_horizon")[
    [COL_ASOF, COL_MACHINE, COL_COMP, "p_at_decision_horizon",
     "risk_rise_from_days", "risk_rise_to_days"]].to_string(index=False))
