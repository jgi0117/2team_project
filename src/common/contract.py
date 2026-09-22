"""
docs/DATA_CONTRACT.md 의 규약을 코드로 고정한다.
컬럼 이름을 바꾸려면 여기만 고치고 다른 담당자와 합의한다.
"""
import pandas as pd
from src.common.paths import OPS, find, pick

# ── 계약서가 정한 컬럼 이름 ──────────────────────────────────
COL_MACHINE = "machineID"
COL_COMP    = "component"
COL_ASOF    = "as_of"
COL_H       = "horizon_days"
COL_Y       = "failure_within_horizon"
COL_OK      = "observation_complete"
COL_P       = "failure_probability"
COL_VER     = "model_version"

COMPONENTS = ["comp1", "comp2", "comp3", "comp4"]
ERRORS     = ["error1", "error2", "error3", "error4", "error5"]
SENSORS    = ["volt", "rotate", "pressure", "vibration"]

DATA_START  = pd.Timestamp("2015-01-01")
DATA_END    = pd.Timestamp("2016-01-01")
WARMUP_DAYS = 30
TRAIN_END   = pd.Timestamp("2015-09-30")
TEST_START  = pd.Timestamp("2015-10-01")

LOOKBACK      = 30          # 딥러닝이 되돌아볼 일수
EXPORT_FREQ   = "W-MON"     # 결과 내보내기 주기 (주 1회 판단)
MODEL_VERSION = "fp_v1"
SEED          = 42

_FALLBACK = {"comp1": 8, "comp2": 42, "comp3": 16, "comp4": 24}


def load_decision_horizon() -> dict:
    """part_master.csv 에서 부품별 결정 시한(조달+준비)을 읽는다."""
    try:
        pm = pd.read_csv(find(OPS, "part_master"))
        c  = pick(pm, "component", "comp")
        lt = pick(pm, "lead_time_days", "lead_time")
        pr = pick(pm, "preparation_days", "prep_days")
        return {str(r[c]).strip(): int(r[lt] + r[pr]) for _, r in pm.iterrows()}
    except Exception as e:
        print(f"⚠️ part_master 읽기 실패({e}) → 기본값 사용")
        return dict(_FALLBACK)


DECISION_HORIZON = load_decision_horizon()

# 곡선을 그리기 위한 격자 + 실제 결정 시한을 합친 것
_GRID   = [7, 14, 21, 28, 35, 42]
HORIZONS = sorted(set(_GRID) | set(DECISION_HORIZON.values()))
