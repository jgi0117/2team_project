from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import DeclarativeBase, sessionmaker


ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")


class Base(DeclarativeBase):
    pass


def enabled() -> bool:
    return os.getenv("DB_ENABLED", "true").lower() in {"1", "true", "yes", "on"}


def url(database: str | None = None) -> URL:
    return URL.create(
        "mysql+pymysql",
        username=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=int(os.getenv("DB_PORT", "3306")),
        database=database if database is not None else os.getenv("DB_NAME", "ge_dashboard"),
        query={"charset": "utf8mb4"},
    )


engine = create_engine(
    url(), pool_pre_ping=True, pool_recycle=3600, pool_timeout=5,
    connect_args={"connect_timeout": 3, "read_timeout": 5, "write_timeout": 5},
)
SessionLocal = sessionmaker(engine, expire_on_commit=False)
