"""
실행: python -m src.failure_prediction.step6_predict
출력  data/processed/predictions.csv     계약서 규격 (필수 필드 준수)
      data/processed/model_metrics.csv   계약서 규격 (긴 형식)
      data/processed/risk_curve.csv      확장 필드: 위험 상승 구간

주의: failure_probability 는 아직 보정 전 점수다.
      0.65 가 '65%'라는 뜻이 아니라 '순위가 높다'는 뜻이다.
      calibrated=False 로 표시해 두었다.

[v2 변경]
 ① risk_rise 계산 교체
    (기존) 0일=확률0 이라는 가짜 점을 넣고 총위험의 20%/80% 지점을 보간
           -> 첫 눈금이 7일이라 결과가 전부 0~7일로 눌림 (1.4~5.9 뭉침)
    (신규) 부품 평균 고장률의 1배/2배/3배를 넘는 날. 보간은 눈금(7~42일) 안에서만.
 ② to_wide 의 bfill 제거 (긴 기간 값으로 짧은 기간을 메우는 낙관 편향)
 ③ 쓰이지 않던 A_curve/H_curve 블록 삭제
 ④ model_adopted 추가. comp2 는 모델 미채택(안전재고 대응) -> 확률은 남기되 플래그로 구분
"""
import numpy as np
import pandas as pd
from src.common.paths import WORK, PROCESSED
from src.common.contract import *

# 모델 채택 여부. comp2 는 42일 예측 성능 미달 -> 안전재고 정책으로 대응.
# 평가지표 확정되면 이 줄만 고치면 된다.
MODEL_ADOPTED = {"comp1": True, "comp2": False, "comp3": True, "comp4": True}

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
    # bfill 금지: 긴 기간 값으로 짧은 기간을 채우면 초반 위험이 부풀려진다.
    A = np.maximum.accumulate(w[H].ffill(axis=1).fillna(0.0).values, axis=1)
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
pred["model_adopted"] = pred[COL_COMP].map(MODEL_ADOPTED).fillna(True)
pred = pred[pred[COL_ASOF].isin(
    pd.date_range(DATA_START, DATA_END, freq=EXPORT_FREQ).date)]
pred.to_csv(PROCESSED / "predictions.csv", index=False)

# ── 확장 필드: 위험 상승 구간 ─────────────────────────────────
# 기준선 = 부품·기간별 실제 평균 고장률. 없으면 예측 확률 평균으로 대체.
ycol = COL_Y if "COL_Y" in dir() and COL_Y in ml.columns else COL_P
BASE = ml.groupby([COL_COMP, COL_H])[ycol].mean().to_dict()
print(f"기준 고장률 산출: {ycol}")

Harr = np.array(H, dtype=float)

def cross_day(row, thr):
    """확률 곡선이 thr 을 처음 넘는 날. 눈금 사이만 선형보간, 0일 가정 없음."""
    if not np.isfinite(thr) or thr <= 0:
        return np.nan
    if row[-1] < thr:            # 42일까지 가도 안 넘음 = 정상
        return np.nan
    if row[0] >= thr:            # 첫 눈금부터 이미 넘음
        return float(Harr[0])
    j = int(np.argmax(row >= thr))
    x0, x1, y0, y1 = Harr[j - 1], Harr[j], row[j - 1], row[j]
    if y1 - y0 < 1e-12:
        return float(x1)
    return float(x0 + (thr - y0) * (x1 - x0) / (y1 - y0))


cur = base.copy()
cur["decision_horizon_days"] = cur[COL_COMP].map(DECISION_HORIZON)

# 부품별 임계값: 결정시한에서의 평균 고장률 × 1 / 2 / 3 (상한 0.60)
lo = np.array([BASE.get((c, DECISION_HORIZON.get(c)), np.nan)
               for c in cur[COL_COMP].values], dtype=float)
mid = np.minimum(lo * 2, 0.60)
hi = np.minimum(lo * 3, 0.60)

cur["risk_rise_from_days"] = [cross_day(r, t) for r, t in zip(A, lo)]
cur["risk_rise_mid_days"]  = [cross_day(r, t) for r, t in zip(A, mid)]
cur["risk_rise_to_days"]   = [cross_day(r, t) for r, t in zip(A, hi)]
cur["risk_threshold"] = lo.round(4)

def status(r, l, h):
    if not np.isfinite(l) or r[-1] < l:
        return "정상"
    if r[0] >= h:
        return "즉시"
    if r[-1] >= h:
        return "주의"
    return "관찰"

cur["risk_status"] = [status(r, l, h) for r, l, h in zip(A, lo, hi)]
cur["p_at_decision_horizon"] = [
    r[H.index(h)] if h in H else np.nan
    for r, h in zip(A, cur["decision_horizon_days"])]
cur["model_adopted"] = cur[COL_COMP].map(MODEL_ADOPTED).fillna(True)
cur[COL_ASOF] = pd.to_datetime(cur[COL_ASOF]).dt.date
cur[COL_VER], cur["calibrated"] = MODEL_VERSION, False
cur = cur[cur[COL_ASOF].isin(pd.date_range(DATA_START, DATA_END, freq=EXPORT_FREQ).date)]
cur.to_csv(PROCESSED / "risk_curve.csv", index=False)

# ── 계약서 규격 model_metrics.csv ──────────────────────────────
mets = [pd.read_csv(WORK / "metrics_ml.csv")]
if (WORK / "metrics_dl.csv").exists():
    mets.append(pd.read_csv(WORK / "metrics_dl.csv"))
pd.concat(mets).to_csv(PROCESSED / "model_metrics.csv", index=False)

# ── 검증 출력 ─────────────────────────────────────────────────
print(f"\n✅ predictions {len(pred):,}행 / risk_curve {len(cur):,}행")

print("\n[risk_rise_from_days 분포] 값이 7~42 사이에 퍼져야 정상")
print(cur.groupby(COL_COMP)["risk_rise_from_days"]
        .agg(계산됨="count", 최소="min", 중앙값="median", 최대="max").round(1).to_string())

print("\n[위험 등급 분포]")
print(pd.crosstab(cur[COL_COMP], cur["risk_status"]).to_string())

print("\n[위험 상위 10]")
print(cur.nlargest(10, "p_at_decision_horizon")[
    [COL_ASOF, COL_MACHINE, COL_COMP, "p_at_decision_horizon",
     "risk_rise_from_days", "risk_rise_to_days", "risk_status"]].to_string(index=False))
