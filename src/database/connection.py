"""SQLAlchemy engine and session configuration.

Credentials are read from the local ``.env`` file or process environment.  The
application can still run from CSV files when ``DB_ENABLED`` is false.
"""

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


def database_enabled() -> bool:
    return os.getenv("DB_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}


def database_url(database: str | None = None) -> URL:
    return URL.create(
        drivername="mysql+pymysql",
        username=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=int(os.getenv("DB_PORT", "3306")),
        database=database if database is not None else os.getenv("DB_NAME", "maintenance_dashboard"),
        query={"charset": "utf8mb4"},
    )


engine = create_engine(
    database_url(),
    pool_pre_ping=True,
    pool_recycle=3600,
)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
