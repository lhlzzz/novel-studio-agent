"""Database connection and helpers for meiti (PostgreSQL + pgvector)."""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(ROOT / ".env")

DATABASE_URL = (
    os.environ.get("MEITI_DATABASE_URL")
    or os.environ.get("DATABASE_URL")
    or "postgresql://meiti:meiti@localhost:5445/meiti"
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=5)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


@contextmanager
def get_db():
    """Context manager with commit-on-success and rollback-on-error."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_db_dependency():
    """Generator-style database dependency for API handlers."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def query_rows(sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Execute raw SQL and return rows as dictionaries."""
    with engine.connect() as conn:
        result = conn.execute(text(sql), params or {})
        return [dict(row) for row in result.mappings().all()]
