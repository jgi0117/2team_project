"""Import the actual GE CSV columns, values and row order into MySQL."""
from __future__ import annotations

import hashlib
import json
import logging
import re
from functools import lru_cache
from pathlib import Path

import pandas as pd
from sqlalchemy import text
from sqlalchemy.dialects.mysql import DOUBLE

from .connection import ROOT, SessionLocal, enabled, engine
from .models import Dataset

logger = logging.getLogger(__name__)


def table_name(relative):
    stem = re.sub(r"[^a-z0-9_]+", "_", str(relative).lower().removesuffix(".csv"))
    return "data_" + stem[:46] + "_" + hashlib.sha256(str(relative).encode()).hexdigest()[:8]


def digest(path):
    with Path(path).open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def import_csv(path):
    path = Path(path)
    relative = path.relative_to(ROOT).as_posix()
    sha256 = digest(path)
    frame = pd.read_csv(path)
    table = table_name(relative)
    with SessionLocal() as db:
        existing = db.get(Dataset, relative)
        if existing and existing.sha256 == sha256:
            return existing.row_count
    # DOUBLE preserves GE's float64 prediction scores (MySQL FLOAT would round).
    float_types = {name: DOUBLE() for name in frame.select_dtypes(include="floating").columns}
    with engine.begin() as db:
        frame.to_sql(table, db, if_exists="replace", index=True, index_label="_ge_row_no",
                     dtype=float_types, chunksize=2000, method="multi")
        count = db.execute(text(f"SELECT COUNT(*) FROM `{table}`")).scalar_one()
        if count != len(frame):
            raise RuntimeError(f"Dataset row count mismatch: {relative}")
    with SessionLocal.begin() as db:
        db.merge(Dataset(source_path=relative, table_name=table, row_count=count,
                         dtypes_json=json.dumps({key: str(value) for key, value in frame.dtypes.items()}),
                         sha256=sha256))
    _load.cache_clear()
    return count


@lru_cache(maxsize=48)
def _load(relative, size, modified_ns):
    with SessionLocal() as db:
        dataset = db.get(Dataset, relative)
        if dataset is None:
            return None
        if dataset.sha256 != digest(ROOT / relative):
            logger.warning("GE source changed; using CSV until reimport: %s", relative)
            return None
        if dataset.table_name != table_name(relative):
            raise ValueError("Unexpected dataset table name")
        frame = pd.read_sql_query(text(f"SELECT * FROM `{dataset.table_name}` ORDER BY `_ge_row_no`"), engine)
        frame = frame.drop(columns="_ge_row_no").astype(json.loads(dataset.dtypes_json))
        if len(frame) != dataset.row_count:
            raise ValueError("Incomplete database dataset")
        return frame


def read_csv(path, **kwargs):
    """Return a GE-compatible frame; custom paths/options retain pandas behavior."""
    if not enabled() or set(kwargs) - {"usecols", "parse_dates"}:
        return None
    path = Path(path).resolve()
    try:
        relative = path.relative_to(ROOT).as_posix()
    except ValueError:
        return None
    try:
        stat = path.stat()
        frame = _load(relative, stat.st_size, stat.st_mtime_ns)
        if frame is None:
            return None
        frame = frame.copy()
        if kwargs.get("usecols") is not None:
            frame = frame.loc[:, kwargs["usecols"]]
        for name in kwargs.get("parse_dates", []):
            frame[name] = pd.to_datetime(frame[name])
        return frame
    except Exception as exc:
        logger.error("GE dataset unavailable (%s), using CSV: %s", type(exc).__name__, relative)
        return None
