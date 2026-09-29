"""
정답(라벨) 정의의 단일 소스.
고장예측 · 비용판단 · 평가 모두 이 파일만 사용한다.

정의
  긴급 교체 : PdM_failures 에 기록된 교체 (failures ⊂ maint)
  예방 교체 : maint 에는 있으나 failures 에 없는 교체
  정답 y    : as_of 부터 H일 안에 긴급 교체가 발생하면 1
"""
import numpy as np
import pandas as pd
from src.common.paths import RAW_PDM, PROCESSED, find, pick

LABEL_VERSION = "label_v1"
MATCH_TOLERANCE_DAYS = 1   # maint 06:00 / failures 03:00 → 날짜 어긋남 보정


def _norm(s):
    return pd.to_datetime(s).dt.normalize()


def load_maint() -> pd.DataFrame:
    m = pd.read_csv(find(RAW_PDM, "maint"))
    return pd.DataFrame({
        "machineID": m[pick(m, "machineID")].astype(int),
        "component": m[pick(m, "comp", "component")].astype(str).str.strip(),
        "date":      _norm(m[pick(m, "datetime", "date")]),
    }).drop_duplicates().sort_values("date").reset_index(drop=True)


def load_failures() -> pd.DataFrame:
    f = pd.read_csv(find(RAW_PDM, "failure"))
    return pd.DataFrame({
        "machineID": f[pick(f, "machineID")].astype(int),
        "component": f[pick(f, "failure", "comp", "component")].astype(str).str.strip(),
        "date":      _norm(f[pick(f, "datetime", "date")]),
    }).drop_duplicates().sort_values("date").reset_index(drop=True)


def load_events() -> pd.DataFrame:
    """교체 이벤트마다 긴급/예방 도장을 찍어 반환. ④비용계산이 그대로 쓴다."""
    m, f = load_maint(), load_failures()
    f2 = f.assign(fail_date=f["date"], is_emergency=1)

    ev = pd.merge_asof(
        m.sort_values("date"),
        f2.sort_values("date")[["machineID", "component", "date",
                                "fail_date", "is_emergency"]],
        on="date", by=["machineID", "component"], direction="nearest",
        tolerance=pd.Timedelta(days=MATCH_TOLERANCE_DAYS))

    ev["is_emergency"] = ev["is_emergency"].fillna(0).astype(int)
    ev["label_version"] = LABEL_VERSION
    return ev.sort_values(["date", "machineID", "component"]).reset_index(drop=True)


def failure_grid(machines, dates) -> dict:
    """(설비 × 날짜) 격자에 '그날 긴급 발생=1' 을 부품별로 찍은 배열."""
    grid = pd.MultiIndex.from_product([machines, dates],
                                      names=["machineID", "date"]).to_frame(index=False)
    f = load_failures()
    out = {}
    for c in sorted(f.component.unique()):
        sub = f[f.component == c][["machineID", "date"]].assign(v=1.0)
        out[c] = grid.merge(sub, on=["machineID", "date"],
                            how="left")["v"].fillna(0).values
    return grid, out


def forward_label(ind, machine_of_row, H) -> np.ndarray:
    """오늘 포함 H일 안에 1이 하나라도 있으면 1. 행이 (설비, 날짜) 순 정렬이어야 함."""
    s = pd.Series(np.asarray(ind, dtype=float))
    rev = s.groupby(np.asarray(machine_of_row)).transform(
        lambda x: x[::-1].rolling(H, min_periods=1).sum()[::-1])
    return (rev.values > 0).astype(int)


def export_events():
    ev = load_events()
    path = PROCESSED / f"events_labeled_{LABEL_VERSION}.csv"
    ev.to_csv(path, index=False)
    n, e = len(ev), int(ev.is_emergency.sum())
    print(f"[라벨] 교체 {n:,}건 / 긴급 {e:,}건 ({e/n:.1%}) → {path.name}")
    print(ev.groupby("component")["is_emergency"]
            .agg(전체="size", 긴급="sum", 긴급률="mean").round(3).to_string())
    return ev


if __name__ == "__main__":
    export_events()
