"""프로젝트 경로. 어느 위치에서 실행해도 루트를 찾아간다."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

RAW_PDM   = ROOT / "data" / "raw" / "azure_pdm"
OPS       = ROOT / "data" / "operations"
PROCESSED = ROOT / "data" / "processed"
WORK      = PROCESSED / "_work"       # 중간 산출물 (언제든 재생성)
MODELS    = ROOT / "models"
DOCS      = ROOT / "docs"

for p in (PROCESSED, WORK, MODELS):
    p.mkdir(parents=True, exist_ok=True)


def find(folder: Path, *keywords) -> Path:
    """파일명이 조금 달라도 키워드로 찾는다."""
    for f in sorted(folder.glob("*.csv")):
        if all(k.lower() in f.name.lower() for k in keywords):
            return f
    raise FileNotFoundError(
        f"{folder} 에 {keywords} 포함 csv 없음. "
        f"있는 파일: {[f.name for f in folder.glob('*.csv')]}")


def pick(df, *cands) -> str:
    """컬럼명 후보 중 실제 존재하는 것을 고른다."""
    low = {c.lower().strip(): c for c in df.columns}
    for c in cands:
        if c.lower() in low:
            return low[c.lower()]
    raise KeyError(f"{cands} 중 없음. 실제 컬럼: {list(df.columns)}")
