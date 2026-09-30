"""Create a fresh GE dashboard database and register GE source-file fingerprints."""

from __future__ import annotations

import argparse
import hashlib
import re
from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine, select, text

from .connection import Base, ROOT, SessionLocal, engine, url
from .models import SourceManifest


SOURCE_PATTERNS = (
    "data/raw/azure_pdm/*.csv",
    "data/operations/*.csv",
    "data/processed/*.csv",
    "outputs/model3/predictions.csv",
    "outputs/model3/evaluation/*.csv",
)
EXCLUDED = set()


def create_database() -> None:
    database = url().database
    if not database or not re.fullmatch(r"[A-Za-z0-9_]+", database):
        raise ValueError("DB_NAME에는 영문, 숫자, 밑줄만 사용할 수 있습니다.")
    admin_engine = create_engine(url(database=""), pool_pre_ping=True)
    with admin_engine.begin() as connection:
        connection.execute(text(
            f"CREATE DATABASE IF NOT EXISTS `{database}` "
            "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        ))
    admin_engine.dispose()


def drop_database() -> None:
    database = url().database
    if not database or not re.fullmatch(r"[A-Za-z0-9_]+", database):
        raise ValueError("DB_NAME에는 영문, 숫자, 밑줄만 사용할 수 있습니다.")
    engine.dispose()
    admin_engine = create_engine(url(database=""), pool_pre_ping=True)
    with admin_engine.begin() as connection:
        connection.execute(text(f"DROP DATABASE IF EXISTS `{database}`"))
    admin_engine.dispose()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _rows(path: Path) -> int | None:
    if path.suffix.lower() != ".csv":
        return None
    with path.open("rb") as source:
        return max(sum(chunk.count(b"\n") for chunk in iter(lambda: source.read(1024 * 1024), b"")) - 1, 0)


def refresh_manifest() -> int:
    paths = sorted({path for pattern in SOURCE_PATTERNS for path in ROOT.glob(pattern)
                    if path.name not in EXCLUDED})
    now = datetime.now()
    with SessionLocal.begin() as session:
        for path in paths:
            relative = path.relative_to(ROOT).as_posix()
            row = session.get(SourceManifest, relative)
            values = dict(sha256=_sha256(path), size_bytes=path.stat().st_size,
                          row_count=_rows(path), scanned_at=now)
            if row is None:
                session.add(SourceManifest(source_path=relative, **values))
            else:
                for key, value in values.items():
                    setattr(row, key, value)
    return len(paths)


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize the GE dashboard database")
    parser.add_argument("--rebuild", action="store_true", help="Drop and recreate DB_NAME")
    args = parser.parse_args()
    if args.rebuild:
        drop_database()
    create_database()
    Base.metadata.create_all(engine)
    from .datasets import import_csv
    for path in sorted({path for pattern in SOURCE_PATTERNS for path in ROOT.glob(pattern)}):
        rows = import_csv(path)
        print(f"Imported {path.relative_to(ROOT).as_posix()}: {rows:,} rows", flush=True)
    count = refresh_manifest()
    print(f"GE database ready: {url().database} (source files: {count})")


if __name__ == "__main__":
    main()
