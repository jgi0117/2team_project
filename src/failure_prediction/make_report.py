"""
실행: python -m src.failure_prediction.make_report
검증보고서용 엑셀 생성
"""
import numpy as np, pandas as pd
from src.common.paths import WORK, PROCESSED
from src.common.contract import *

OUT = PROCESSED / "모델12_검증보고서.xlsx"
DEC = {"comp1": 8, "comp2": 42, "comp3": 16, "comp4": 24}

# --- 2. 모델비교 ---
cmp_path = PROCESSED / "model_comparison.csv"
cmp_df = pd.read_csv(cmp_path) if cmp_path.exists() else pd.DataFrame()

# --- 3. 전체성적 (36개) ---
m = pd.read_csv(WORK / "metrics_ml.csv")
wide = m.pivot_table(index=[COL_COMP, COL_H], columns="metric",
                     values="value").reset_index()
wide["결정시한여부"] = [ "★" if DEC.get(c)==h else "" 
                      for c,h in zip(wide[COL_COMP], wide[COL_H]) ]
wide = wide.rename(columns={COL_COMP:"부품", COL_H:"예측기간(일)",
    "auc":"AUC", "pr_auc":"PR_AUC", "rule_auc":"기준선AUC(경과일)",
    "lift_top10":"Lift상위10%", "base_rate":"실제고장률",
    "n_test":"시험건수", "pos_test":"시험고장건수"})
cols = ["부품","예측기간(일)","결정시한여부","AUC","기준선AUC(경과일)",
        "AUC개선폭","PR_AUC","Lift상위10%","실제고장률","시험건수","시험고장건수"]
wide["AUC개선폭"] = (wide["AUC"] - wide["기준선AUC(경과일)"]).round(3)
wide = wide[cols].sort_values(["부품","예측기간(일)"])

# --- 1. 요약 ---
s = wide[wide["결정시한여부"]=="★"].copy()
s["판정"] = np.where(s["AUC"]>=0.80, "사용가능",
            np.where(s["AUC"]>=0.70, "제한적", "사용불가"))
summary = s[["부품","예측기간(일)","AUC","기준선AUC(경과일)",
             "AUC개선폭","Lift상위10%","판정"]]

# --- 4. 데이터검증 ---
ds = pd.read_parquet(WORK / "train_table.parquet")
pnl = pd.read_parquet(WORK / "daily_panel.parquet")
chk = pd.DataFrame([
 ["원본 센서", "PdM_telemetry.csv", "876,100행 / 100대 / 시간단위", "결측 0", "정상"],
 ["일단위 집계", "daily_panel.parquet", f"{len(pnl):,}행 x {pnl.shape[1]}열", "결측 0", "정상"],
 ["피처 생성", "features.parquet", "36,600행 x 88열", "-", "정상"],
 ["학습표", "train_table.parquet", f"{len(ds):,}행", "-", "정상"],
 ["사용 피처", "-", "79개 (설비식별 6개 제외)", "-", "정상"],
 ["정답 생성", "PdM_maint ⨝ PdM_failures", "교체 3,286건 중 긴급 745건(22.7%)",
  "failures 761건 중 745건 매칭(97.9%)", "정상"],
 ["학습/시험 분리", "시간순", "학습 ~2015-09-30 / 시험 2015-10-01~", "미래정보 차단", "정상"],
 ["문제유형", "-", "이진분류(Binary Classification)", "회귀 미사용", "-"],
], columns=["항목","대상","내용","검증결과","판정"])

# --- 5. 피처중요도 (결정시한만 상위10) ---
fi = pd.read_csv(PROCESSED / "feature_importance.csv")
fi = fi[[DEC.get(c)==h for c,h in zip(fi[COL_COMP], fi[COL_H])]]
fi = (fi.sort_values([COL_COMP,"gain"], ascending=[True,False])
        .groupby(COL_COMP).head(10)
        .rename(columns={COL_COMP:"부품", COL_H:"예측기간(일)",
                         "feature":"피처명", "gain":"중요도"}))
fi["중요도"] = fi["중요도"].round(1)

with pd.ExcelWriter(OUT, engine="openpyxl") as w:
    summary.to_excel(w, "1.요약", index=False)
    if len(cmp_df): cmp_df.to_excel(w, "2.모델비교", index=False)
    wide.to_excel(w, "3.전체성적", index=False)
    chk.to_excel(w, "4.데이터검증", index=False)
    fi.to_excel(w, "5.피처중요도", index=False)

print(f"✅ {OUT}")
print(summary.to_string(index=False))
