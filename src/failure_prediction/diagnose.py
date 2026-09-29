"""실행: python -m src.failure_prediction.diagnose
comp3·comp4 가 '언제'를 맞히는지 '누구'를 맞히는지 확인한다."""
import pandas as pd
from src.common.paths import PROCESSED
from src.common.contract import *

imp = pd.read_csv(PROCESSED / "feature_importance.csv")
print("[1] 결정시한에서 모델이 가장 많이 본 것 Top5\n")
for c in COMPONENTS:
    h = DECISION_HORIZON[c]
    t = imp[(imp[COL_COMP] == c) & (imp[COL_H] == h)].nlargest(5, "gain")
    print(f"  {c} ({h}일): " + ", ".join(t["feature"].tolist()))

cur = pd.read_csv(PROCESSED / "risk_curve.csv", parse_dates=[COL_ASOF])
print("\n[2] 매주 위험 상위 20위가 얼마나 그대로인가")
print("    (80% 넘으면 '누구'를 보는 것, 50% 아래면 '언제'를 보는 것)\n")
for c in COMPONENTS:
    s = cur[cur[COL_COMP] == c]
    tops = [set(d.nlargest(20, "p_at_decision_horizon")[COL_MACHINE])
            for _, d in s.groupby(COL_ASOF)]
    if len(tops) < 2:
        continue
    ov = [len(a & b) / 20 for a, b in zip(tops[:-1], tops[1:])]
    print(f"  {c}: {sum(ov)/len(ov):.0%}")
