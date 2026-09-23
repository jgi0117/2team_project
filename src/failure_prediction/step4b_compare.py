"""
실행: python -m src.failure_prediction.step4b_compare
모델 4종을 같은 데이터로 학습해서 성적 비교.
"""
import warnings, time
import numpy as np, pandas as pd, lightgbm as lgb
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.impute import SimpleImputer
from sklearn.metrics import roc_auc_score, average_precision_score
from src.common.paths import WORK, PROCESSED
from src.common.contract import *
warnings.filterwarnings("ignore")

DEC = {"comp1": 8, "comp2": 42, "comp3": 16, "comp4": 24}   # 부품별 결정 시한

ds = pd.read_parquet(WORK / "train_table.parquet")
drop = ["machineID", COL_ASOF, "model", "split"] + \
       [c for c in ds.columns if c.startswith(("y_", "ok_"))]
FEATS = [c for c in ds.columns if c not in drop and ds[c].dtype != object]
DROP_ID = ["age", "model_num", "age_bin"]
FEATS = [c for c in FEATS if c not in DROP_ID and not c.startswith("nfail_")]
print(f"피처 {len(FEATS)}개\n")

def models():
    return {
        "로지스틱회귀": make_pipeline(SimpleImputer(), StandardScaler(),
                        LogisticRegression(max_iter=2000, random_state=SEED)),
        "랜덤포레스트": RandomForestClassifier(n_estimators=300, min_samples_leaf=20,
                        n_jobs=-1, random_state=SEED),
        "LightGBM":   lgb.LGBMClassifier(objective="binary", learning_rate=0.05,
                        num_leaves=31, min_child_samples=50, n_estimators=400,
                        random_state=SEED, verbose=-1),
        "신경망(MLP)": make_pipeline(SimpleImputer(), StandardScaler(),
                        MLPClassifier(hidden_layer_sizes=(64, 32), max_iter=300,
                                      early_stopping=True, random_state=SEED)),
    }

rows = []
for c, H in DEC.items():
    y, ok = f"y_{c}_{H}", f"ok_{c}_{H}"
    d = ds[ds[ok] == 1]
    cut = TRAIN_END - pd.Timedelta(days=H)
    tr = d[d[COL_ASOF] <= cut]
    te = d[d[COL_ASOF] >= TEST_START]
    base = te[y].mean()
    k = max(1, int(len(te) * 0.1))

    # 기준선: 마지막 교체 후 경과일만 사용
    r = te[f"dsr_{c}"].fillna(0).values
    rows.append(dict(부품=c, 기간=H, 모델="[기준선] 경과일",
                     AUC=roc_auc_score(te[y], r),
                     PR_AUC=average_precision_score(te[y], r),
                     Lift=te[y].iloc[np.argsort(-r)[:k]].mean() / base, 초=0.0))

    for name, m in models().items():
        t0 = time.time()
        m.fit(tr[FEATS], tr[y])
        s = m.predict_proba(te[FEATS])[:, 1]
        rows.append(dict(부품=c, 기간=H, 모델=name,
                         AUC=roc_auc_score(te[y], s),
                         PR_AUC=average_precision_score(te[y], s),
                         Lift=te[y].iloc[np.argsort(-s)[:k]].mean() / base,
                         초=round(time.time() - t0, 1)))
        print(f"{c} {H:>2}일 | {name:12s} AUC {rows[-1]['AUC']:.3f} "
              f"PR {rows[-1]['PR_AUC']:.3f} Lift {rows[-1]['Lift']:.1f}배 "
              f"({rows[-1]['초']}초)")
    print()

df = pd.DataFrame(rows).round(3)
df.to_csv(PROCESSED / "model_comparison.csv", index=False, encoding="utf-8-sig")

print("\n===== 모델별 평균 =====")
print(df.groupby("모델")[["AUC", "PR_AUC", "Lift", "초"]].mean().round(3)
        .sort_values("AUC", ascending=False))
print("\n✅ data/processed/model_comparison.csv")
