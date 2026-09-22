"""
실행: python -m src.failure_prediction.step4_train_ml
LightGBM 으로 부품 × 기간 조합을 각각 학습. 딥러닝의 비교 기준선이자 백업.
"""
import warnings
import joblib
import numpy as np
import pandas as pd
import lightgbm as lgb
from sklearn.metrics import roc_auc_score, average_precision_score
from src.common.paths import WORK, PROCESSED, MODELS
from src.common.contract import *
warnings.filterwarnings("ignore")

ds = pd.read_parquet(WORK / "train_table.parquet")
drop = ["machineID", COL_ASOF, "model", "split"] + \
       [c for c in ds.columns if c.startswith(("y_", "ok_"))]
FEATS = [c for c in ds.columns if c not in drop and ds[c].dtype != object]
DROP_ID = ["age", "model_num", "age_bin"]
FEATS = [c for c in FEATS if c not in DROP_ID and not c.startswith("nfail_")]
print(f"피처 {len(FEATS)}개 / {len(ds):,}행\n")


P = dict(objective="binary", learning_rate=0.05, num_leaves=31, min_child_samples=50,
         feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=1, lambda_l2=1.0,
         n_estimators=1000, random_state=SEED, verbose=-1)

met, preds, imps = [], [], []
for c in COMPONENTS:
    for H in HORIZONS:
        y, ok = f"y_{c}_{H}", f"ok_{c}_{H}"
        d = ds[ds[ok] == 1]
        cut  = TRAIN_END - pd.Timedelta(days=H)   # 정답이 시험구간을 넘보지 않게
        vcut = cut - pd.Timedelta(days=45)
        tr = d[d[COL_ASOF] <= vcut]
        va = d[(d[COL_ASOF] > vcut) & (d[COL_ASOF] <= cut)]
        te = d[d[COL_ASOF] >= TEST_START]
        if tr[y].sum() < 20 or te[y].sum() < 5:
            print(f"⚠️  {c} {H:>2}일 건너뜀 (사례부족 tr={int(tr[y].sum())} te={int(te[y].sum())})")
            continue

        m = lgb.LGBMClassifier(**P)
        m.fit(tr[FEATS], tr[y], eval_set=[(va[FEATS], va[y])], eval_metric="auc",
              callbacks=[lgb.early_stopping(60, verbose=False)])
        s = m.predict_proba(te[FEATS])[:, 1]
        auc  = roc_auc_score(te[y], s)
        ap   = average_precision_score(te[y], s)
        base = te[y].mean()
        rule = te[f"dsr_{c}"].fillna(0)
        rauc = roc_auc_score(te[y], rule) if te[y].nunique() > 1 else np.nan
        k = max(1, int(len(te) * 0.1))
        lift = te[y].iloc[np.argsort(-s)[:k]].mean() / base if base else np.nan

        joblib.dump({"model": m, "feats": FEATS, "component": c, "horizon": H,
                     "train_end": str(TRAIN_END.date()), "version": MODEL_VERSION},
                    MODELS / f"ml_{c}_{H}d.pkl")

        for name, val in [("auc", auc), ("pr_auc", ap), ("base_rate", base),
                          ("rule_auc", rauc), ("lift_top10", lift),
                          ("n_test", len(te)), ("pos_test", int(te[y].sum()))]:
            met.append({COL_VER: MODEL_VERSION, COL_COMP: c, COL_H: H,
                        "split": "test", "metric": name, "value": round(float(val), 4),
                        "source": "ml"})
        preds.append(pd.DataFrame({COL_MACHINE: te.machineID.values, COL_COMP: c,
                                   COL_ASOF: te[COL_ASOF].values, COL_H: H,
                                   COL_P: s, COL_Y: te[y].values, "source": "ml"}))
        imps.append(pd.DataFrame({COL_COMP: c, COL_H: H,
                                  "feature": FEATS,
                                  "gain": m.booster_.feature_importance("gain")}))
        flag = "🚨누수의심" if auc > 0.98 else ("⚠️약함" if auc < 0.65 else "✅")
        print(f"{flag} {c} {H:>2}일 | AUC {auc:.3f} (규칙 {rauc:.3f}) | "
              f"고장률 {base:5.1%} | 상위10% {lift:.1f}배")

pd.DataFrame(met).to_csv(WORK / "metrics_ml.csv", index=False)
pd.concat(preds).to_parquet(WORK / "pred_ml.parquet", index=False)
pd.concat(imps).to_csv(PROCESSED / "feature_importance.csv", index=False)
print(f"\n✅ 모델 {len(preds)}개 저장")
