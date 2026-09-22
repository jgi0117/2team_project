"""실행: python -m src.data_pipeline.step0_check"""
import pandas as pd
from src.common.paths import RAW_PDM, OPS, find, pick
from src.common.contract import *
from src.common import labels

print("=" * 66)
print("[1] 파일 확인")
files = {}
for k, kw in [("telemetry", "telemetry"), ("errors", "error"), ("maint", "maint"),
              ("failures", "failure"), ("machines", "machine")]:
    try:
        files[k] = find(RAW_PDM, kw)
        print(f"  ✅ {k:10s} {files[k].name}")
    except FileNotFoundError as e:
        print(f"  ❌ {k:10s} {e}")

print("\n[2] 컬럼 확인")
need = {"telemetry": ["datetime", "machineID"] + SENSORS,
        "errors":    ["datetime", "machineID", "errorID"],
        "maint":     ["datetime", "machineID", "comp"],
        "failures":  ["datetime", "machineID", "failure"],
        "machines":  ["machineID", "model", "age"]}
bad = False
for k, cols in need.items():
    if k not in files:
        continue
    df = pd.read_csv(files[k], nrows=2000)
    miss = [c for c in cols if c not in df.columns]
    bad |= bool(miss)
    print(f"  {'❌' if miss else '✅'} {k:10s} {list(df.columns)}"
          + (f"  없음:{miss}" if miss else ""))

print("\n[3] 규모")
tel = pd.read_csv(files["telemetry"], parse_dates=["datetime"],
                  usecols=["datetime", "machineID"])
nm = tel.machineID.nunique()
print(f"  센서 {len(tel):,}행 / 설비 {nm}대 / {tel.datetime.min()} ~ {tel.datetime.max()}")
print(f"  시간당 1행 가정 대비 {len(tel)/(nm*8761):.1%}")

print("\n[4] 라벨 ★")
ev = labels.export_events()
f = labels.load_failures()
matched = int(ev.is_emergency.sum())
print(f"\n  failures 원본 {len(f)}건 중 maint 와 매칭 {matched}건 "
      f"(미매칭 {len(f)-matched}건)")
if len(f) - matched > 40:
    print("  ⚠️ 미매칭이 많음 → 날짜 어긋남 의심. 알려주세요.")

print("\n[5] 부품별 결정 시한 (part_master 기준)")
for c in COMPONENTS:
    print(f"  {c}: {DECISION_HORIZON.get(c, '?')}일")
print(f"  학습할 기간 격자: {HORIZONS}")

print("\n[6] 시험구간 고장 건수 전망")
q4 = f[f.date >= TEST_START]
print(q4.groupby("component").size().to_string())
print("  ⬆ 30건 미만이면 그 부품 결과는 흔들릴 수 있음")

print("\n" + ("❌ 위 ❌ 항목 알려주세요." if bad else "✅ 통과 → step1"))
