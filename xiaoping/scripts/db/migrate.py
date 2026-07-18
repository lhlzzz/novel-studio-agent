#!/usr/bin/env python3
"""Manage the xiaoping agent database schema and demo bootstrap."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import func, inspect, select, text
from sqlalchemy.exc import SQLAlchemyError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts.db.engine import DATABASE_URL, Base, SessionLocal, engine
from scripts.db.models import (
    AgentArtifact,
    AgentDecision,
    AgentMetric,
    AgentRecord,
    AgentRun,
    AgentTask,
)

PROJECT_NAME = "xiaoping"
TABLE_NAMES = sorted(Base.metadata.tables)
SEED_PREFIX = f"{PROJECT_NAME}-demo"
VERIFY_RECORD_KEY = f"{PROJECT_NAME}-verify-record"
BASE_TABLE_MODELS = (
    ("agent_runs", AgentRun),
    ("agent_tasks", AgentTask),
    ("agent_decisions", AgentDecision),
    ("agent_artifacts", AgentArtifact),
    ("agent_metrics", AgentMetric),
    ("agent_records", AgentRecord),
)
DEMO_KEY_CHECKS = (
    ("run", AgentRun, AgentRun.run_key, f"{SEED_PREFIX}-run"),
    ("task", AgentTask, AgentTask.task_key, f"{SEED_PREFIX}-task"),
    ("decision", AgentDecision, AgentDecision.decision_key, f"{SEED_PREFIX}-decision"),
    ("artifact", AgentArtifact, AgentArtifact.artifact_key, f"{SEED_PREFIX}-artifact"),
    ("metric", AgentMetric, AgentMetric.metric_key, f"{SEED_PREFIX}-metric"),
    ("record", AgentRecord, AgentRecord.record_key, f"{SEED_PREFIX}-record"),
)


def _masked_database_url() -> str:
    parts = urlsplit(DATABASE_URL)
    if not parts.netloc or "@" not in parts.netloc:
        return DATABASE_URL
    host = parts.netloc.rsplit("@", 1)[1]
    return urlunsplit((parts.scheme, f"***:***@{host}", parts.path, parts.query, parts.fragment))


def _die_db_error(command: str, exc: Exception) -> None:
    print(f"DB {command} failed: {_masked_database_url()}", file=sys.stderr)
    print(f"Reason: {exc.__class__.__name__}: {exc}", file=sys.stderr)
    raise SystemExit(1) from exc


def _print_table_names(header: str, table_names: list[str]) -> None:
    print(header)
    for table_name in table_names:
        print(f"  - {table_name}")


def _upsert_model(session, orm_model, lookup_key: str, lookup_value: str, **fields):
    instance = session.execute(
        select(orm_model).where(getattr(orm_model, lookup_key) == lookup_value)
    ).scalar_one_or_none()
    if instance is None:
        instance = orm_model(**{lookup_key: lookup_value}, **fields)
        session.add(instance)
        session.flush()
        return instance, True
    for key, value in fields.items():
        setattr(instance, key, value)
    session.flush()
    return instance, False


def init_db() -> None:
    """Create all ORM-managed tables if they do not already exist."""
    try:
        Base.metadata.create_all(bind=engine)
    except SQLAlchemyError as exc:
        _die_db_error("init", exc)
    _print_table_names("DB tables ready:", TABLE_NAMES)


def status() -> None:
    """Check database connectivity and list visible tables."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            tables = sorted(inspect(conn).get_table_names())
    except SQLAlchemyError as exc:
        _die_db_error("status", exc)
    print(f"DB connection OK: {_masked_database_url()}")
    if tables:
        _print_table_names("Visible tables:", tables)
    else:
        print("Visible tables: none")


def seed() -> None:
    """Insert or refresh minimal demo data for the agent system tables."""
    try:
        with SessionLocal() as session:
            run, run_created = _upsert_model(
                session,
                AgentRun,
                "run_key",
                f"{SEED_PREFIX}-run",
                run_type="bootstrap",
                status="completed",
                model="claude-opus-4-8",
                prompt_summary=f"{PROJECT_NAME} bootstrap demo run",
                inputs={"project": PROJECT_NAME, "mode": "bootstrap"},
                outputs={"status": "ok", "kind": "demo"},
                source=PROJECT_NAME,
            )
            task, task_created = _upsert_model(
                session,
                AgentTask,
                "task_key",
                f"{SEED_PREFIX}-task",
                run_id=run.id,
                title=f"Bootstrap {PROJECT_NAME} agent system",
                status="completed",
                priority="normal",
                owner_model="claude-opus-4-8",
                payload={"project": PROJECT_NAME, "source": "seed"},
            )
            _upsert_model(
                session,
                AgentDecision,
                "decision_key",
                f"{SEED_PREFIX}-decision",
                run_id=run.id,
                task_id=task.id,
                decision_type="bootstrap",
                summary=f"Initialized {PROJECT_NAME} reusable agent database",
                rationale="Provide an out-of-the-box local starting point with demo records.",
                alternatives=["Leave tables empty"],
                source=PROJECT_NAME,
            )
            _upsert_model(
                session,
                AgentArtifact,
                "artifact_key",
                f"{SEED_PREFIX}-artifact",
                run_id=run.id,
                task_id=task.id,
                artifact_type="documentation",
                path="README.md",
                uri=None,
                checksum=None,
                metadata_json={"project": PROJECT_NAME, "kind": "demo-artifact"},
            )
            _upsert_model(
                session,
                AgentMetric,
                "metric_key",
                f"{SEED_PREFIX}-metric",
                run_id=run.id,
                metric_name="bootstrap_table_count",
                metric_value=len(TABLE_NAMES),
                unit="tables",
                dimensions={"project": PROJECT_NAME},
            )
            _upsert_model(
                session,
                AgentRecord,
                "record_key",
                f"{SEED_PREFIX}-record",
                record_type="bootstrap",
                payload={
                    "project": PROJECT_NAME,
                    "tables": TABLE_NAMES,
                    "run_key": run.run_key,
                    "task_key": task.task_key,
                },
                source=PROJECT_NAME,
            )
            session.commit()
    except SQLAlchemyError as exc:
        _die_db_error("seed", exc)
    print(f"Seed data ready for {PROJECT_NAME} (created/updated demo records).")


def verify() -> None:
    """Run a minimal connectivity, schema, and CRUD smoke test."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            inspector = inspect(conn)
            tables = sorted(inspector.get_table_names())
        missing = [table for table in TABLE_NAMES if table not in tables]
        if missing:
            raise SystemExit(f"Missing tables: {', '.join(missing)}")

        with SessionLocal() as session:
            run = session.execute(
                select(AgentRun).where(AgentRun.run_key == f"{SEED_PREFIX}-run")
            ).scalar_one_or_none()
            record = session.execute(
                select(AgentRecord).where(AgentRecord.record_key == f"{SEED_PREFIX}-record")
            ).scalar_one_or_none()
            if run is None or record is None:
                raise SystemExit("Seed data missing; run 'python scripts/db/migrate.py seed' first.")

            verify_record, _ = _upsert_model(
                session,
                AgentRecord,
                "record_key",
                VERIFY_RECORD_KEY,
                record_type="verify",
                payload={"project": PROJECT_NAME, "check": "crud-roundtrip"},
                source=PROJECT_NAME,
            )
            verify_record.payload = {
                "project": PROJECT_NAME,
                "check": "crud-roundtrip",
                "status": "updated",
            }
            session.flush()
            session.delete(verify_record)
            session.commit()
    except SQLAlchemyError as exc:
        _die_db_error("verify", exc)
    except SystemExit:
        raise
    except Exception as exc:
        print(f"DB verify failed: {_masked_database_url()}", file=sys.stderr)
        print(f"Reason: {exc.__class__.__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    print(f"DB verify OK: {_masked_database_url()}")
    _print_table_names("Verified tables:", TABLE_NAMES)
    print(f"Demo run key: {SEED_PREFIX}-run")
    print(f"Demo record key: {SEED_PREFIX}-record")
    print("CRUD smoke: passed")


def report() -> None:
    """Print a read-only summary of the current database state."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            tables = sorted(inspect(conn).get_table_names())
        visible_tables = set(tables)

        with SessionLocal() as session:
            row_counts = []
            for table_name, orm_model in BASE_TABLE_MODELS:
                if table_name not in visible_tables:
                    row_counts.append((table_name, "missing"))
                    continue
                count = session.execute(select(func.count()).select_from(orm_model)).scalar_one()
                row_counts.append((table_name, count))

            found_demo_keys = []
            for label, orm_model, column, expected_key in DEMO_KEY_CHECKS:
                if session.execute(select(orm_model.id).where(column == expected_key)).scalar_one_or_none() is not None:
                    found_demo_keys.append((label, expected_key))

            latest_run = session.execute(
                select(AgentRun)
                .order_by(AgentRun.started_at.desc(), AgentRun.created_at.desc(), AgentRun.id.desc())
                .limit(1)
            ).scalar_one_or_none()
    except SQLAlchemyError as exc:
        _die_db_error("report", exc)

    print(f"DB report for {PROJECT_NAME}")
    print(f"DATABASE_URL: {_masked_database_url()}")
    if tables:
        _print_table_names("Visible tables:", tables)
    else:
        print("Visible tables: none")

    print("Row counts:")
    for table_name, count in row_counts:
        print(f"  - {table_name}: {count}")

    if found_demo_keys:
        print("Demo/bootstrap keys:")
        for label, key in found_demo_keys:
            print(f"  - {label}: {key}")
    else:
        print(
            "Demo/bootstrap keys: missing "
            f"(expected {SEED_PREFIX}-run / {SEED_PREFIX}-record and related demo keys)"
        )

    if latest_run is None:
        print("Latest run: none")
    else:
        print("Latest run:")
        print(f"  - run_key: {latest_run.run_key}")
        print(f"  - status: {latest_run.status}")
        print(f"  - model: {latest_run.model or 'n/a'}")
        print(f"  - started_at: {latest_run.started_at}")
        print(f"  - finished_at: {latest_run.finished_at or 'n/a'}")


def bootstrap() -> None:
    """Create tables, seed demo data, and verify the result."""
    init_db()
    seed()
    verify()


def main() -> None:
    parser = argparse.ArgumentParser(description=f"{PROJECT_NAME} database utilities")
    parser.add_argument(
        "command",
        choices=["init", "status", "seed", "verify", "report", "bootstrap"],
        help="database command to run",
    )
    args = parser.parse_args()

    if args.command == "init":
        init_db()
    elif args.command == "status":
        status()
    elif args.command == "seed":
        seed()
    elif args.command == "verify":
        verify()
    elif args.command == "report":
        report()
    elif args.command == "bootstrap":
        bootstrap()


if __name__ == "__main__":
    main()
