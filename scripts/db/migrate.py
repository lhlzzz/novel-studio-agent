#!/usr/bin/env python3
"""Manage the meiti database schema (agent + pgvector + content KG + gates)."""

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
    DEFAULT_EMBEDDING_DIM,
    AgentArtifact,
    AgentDecision,
    AgentMetric,
    AgentRecord,
    AgentRun,
    AgentTask,
    ContentEmbedding,
    ContentEntity,
    ContentRelation,
    PublishGate,
)

PROJECT_NAME = "meiti"
TABLE_NAMES = sorted(Base.metadata.tables)
SEED_PREFIX = f"{PROJECT_NAME}-demo"
VERIFY_RECORD_KEY = f"{PROJECT_NAME}-verify-record"
VERIFY_EMBEDDING_KEY = f"{PROJECT_NAME}-verify-embedding"
BASE_TABLE_MODELS = (
    ("agent_runs", AgentRun),
    ("agent_tasks", AgentTask),
    ("agent_decisions", AgentDecision),
    ("agent_artifacts", AgentArtifact),
    ("agent_metrics", AgentMetric),
    ("agent_records", AgentRecord),
    ("content_embeddings", ContentEmbedding),
    ("content_entities", ContentEntity),
    ("content_relations", ContentRelation),
    ("publish_gates", PublishGate),
)
DEMO_KEY_CHECKS = (
    ("run", AgentRun, AgentRun.run_key, f"{SEED_PREFIX}-run"),
    ("task", AgentTask, AgentTask.task_key, f"{SEED_PREFIX}-task"),
    ("decision", AgentDecision, AgentDecision.decision_key, f"{SEED_PREFIX}-decision"),
    ("artifact", AgentArtifact, AgentArtifact.artifact_key, f"{SEED_PREFIX}-artifact"),
    ("metric", AgentMetric, AgentMetric.metric_key, f"{SEED_PREFIX}-metric"),
    ("record", AgentRecord, AgentRecord.record_key, f"{SEED_PREFIX}-record"),
    ("embedding", ContentEmbedding, ContentEmbedding.embedding_key, f"{SEED_PREFIX}-embedding"),
    ("entity", ContentEntity, ContentEntity.entity_key, f"{SEED_PREFIX}-entity-topic"),
    ("relation", ContentRelation, ContentRelation.relation_key, f"{SEED_PREFIX}-rel-topic-platform"),
    ("gate", PublishGate, PublishGate.gate_key, f"{SEED_PREFIX}-gate"),
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


def _enable_pgvector() -> None:
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))


def init_db() -> None:
    """Enable pgvector and create all ORM-managed tables."""
    try:
        _enable_pgvector()
        Base.metadata.create_all(bind=engine)
        with engine.connect() as conn:
            ext = conn.execute(
                text("SELECT extname FROM pg_extension WHERE extname = 'vector'")
            ).scalar_one_or_none()
        if ext != "vector":
            raise RuntimeError("pgvector extension 'vector' not installed in database")
    except SQLAlchemyError as exc:
        _die_db_error("init", exc)
    _print_table_names("DB tables ready:", TABLE_NAMES)
    print("pgvector extension: OK")
    print(f"default embedding dim: {DEFAULT_EMBEDDING_DIM}")


def status() -> None:
    """Check database connectivity, pgvector, and list visible tables."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            tables = sorted(inspect(conn).get_table_names())
            ext = conn.execute(
                text("SELECT extname FROM pg_extension WHERE extname = 'vector'")
            ).scalar_one_or_none()
    except SQLAlchemyError as exc:
        _die_db_error("status", exc)
    print(f"DB connection OK: {_masked_database_url()}")
    print(f"pgvector extension: {'OK' if ext == 'vector' else 'MISSING'}")
    if tables:
        _print_table_names("Visible tables:", tables)
    else:
        print("Visible tables: none")


def seed() -> None:
    """Insert or refresh minimal demo data including vector + KG + gate."""
    zero_vec = [0.0] * DEFAULT_EMBEDDING_DIM
    try:
        with SessionLocal() as session:
            run, _ = _upsert_model(
                session,
                AgentRun,
                "run_key",
                f"{SEED_PREFIX}-run",
                run_type="bootstrap",
                status="completed",
                model="bootstrap",
                prompt_summary=f"{PROJECT_NAME} bootstrap demo run",
                inputs={"project": PROJECT_NAME, "mode": "bootstrap"},
                outputs={"status": "ok", "kind": "demo"},
                source=PROJECT_NAME,
            )
            task, _ = _upsert_model(
                session,
                AgentTask,
                "task_key",
                f"{SEED_PREFIX}-task",
                run_id=run.id,
                title=f"Bootstrap {PROJECT_NAME} agent + vector + content KG",
                status="completed",
                priority="normal",
                owner_model="bootstrap",
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
                summary=f"Initialized {PROJECT_NAME} PostgreSQL + pgvector + content KG",
                rationale="Unified media content vectors, relations, gates, agent audit.",
                alternatives=["Keep only sub-line DBs 5443/5444"],
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
                    "pgvector": True,
                    "port": 5445,
                },
                source=PROJECT_NAME,
            )
            _upsert_model(
                session,
                ContentEmbedding,
                "embedding_key",
                f"{SEED_PREFIX}-embedding",
                content_type="demo",
                source_line="shared",
                title="meiti bootstrap embedding",
                body="Demo zero vector for pgvector smoke test.",
                uri=None,
                path=None,
                platform=None,
                language="zh",
                model="zero-vector",
                dim=DEFAULT_EMBEDDING_DIM,
                embedding=zero_vec,
                metadata_json={"project": PROJECT_NAME, "kind": "demo"},
            )
            topic, _ = _upsert_model(
                session,
                ContentEntity,
                "entity_key",
                f"{SEED_PREFIX}-entity-topic",
                entity_type="topic",
                name="AI efficiency templates for small business",
                description="Bootstrap topic node",
                source_line="shared",
                properties={"demo": True},
            )
            platform, _ = _upsert_model(
                session,
                ContentEntity,
                "entity_key",
                f"{SEED_PREFIX}-entity-platform",
                entity_type="platform",
                name="xiaohongshu",
                description="Bootstrap platform node",
                source_line="xiaoping",
                properties={"demo": True},
            )
            _upsert_model(
                session,
                ContentRelation,
                "relation_key",
                f"{SEED_PREFIX}-rel-topic-platform",
                relation_type="adapts_to",
                from_entity_id=topic.id,
                to_entity_id=platform.id,
                weight=1.0,
                properties={"demo": True},
            )
            _upsert_model(
                session,
                PublishGate,
                "gate_key",
                f"{SEED_PREFIX}-gate",
                action="publish",
                platform="xiaohongshu",
                package_key=f"{SEED_PREFIX}-package",
                status="locked",
                requested_by="bootstrap",
                rationale="Default locked; external publish requires boss approval.",
                checks={"ai_feel": "pending", "marketing_risk": "pending"},
                evidence={},
            )
            session.commit()
    except SQLAlchemyError as exc:
        _die_db_error("seed", exc)
    print(f"Seed data ready for {PROJECT_NAME} (agent + embeddings + KG + gates).")


def verify() -> None:
    """Connectivity, schema, pgvector, CRUD, cosine distance, KG, gate smoke."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            inspector = inspect(conn)
            tables = sorted(inspector.get_table_names())
            ext = conn.execute(
                text("SELECT extname FROM pg_extension WHERE extname = 'vector'")
            ).scalar_one_or_none()
        if ext != "vector":
            raise SystemExit("pgvector extension missing; run init against pgvector-enabled PG")
        missing = [table for table in TABLE_NAMES if table not in tables]
        if missing:
            raise SystemExit(f"Missing tables: {', '.join(missing)}")

        with SessionLocal() as session:
            run = session.execute(
                select(AgentRun).where(AgentRun.run_key == f"{SEED_PREFIX}-run")
            ).scalar_one_or_none()
            emb = session.execute(
                select(ContentEmbedding).where(
                    ContentEmbedding.embedding_key == f"{SEED_PREFIX}-embedding"
                )
            ).scalar_one_or_none()
            ent = session.execute(
                select(ContentEntity).where(
                    ContentEntity.entity_key == f"{SEED_PREFIX}-entity-topic"
                )
            ).scalar_one_or_none()
            gate = session.execute(
                select(PublishGate).where(PublishGate.gate_key == f"{SEED_PREFIX}-gate")
            ).scalar_one_or_none()
            if run is None or emb is None or ent is None or gate is None:
                raise SystemExit(
                    "Seed data missing; run 'python scripts/db/migrate.py seed' first."
                )
            if gate.status != "locked":
                raise SystemExit(f"Demo gate must be locked, got {gate.status}")

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

            half = [0.0] * DEFAULT_EMBEDDING_DIM
            half[0] = 1.0
            verify_emb, _ = _upsert_model(
                session,
                ContentEmbedding,
                "embedding_key",
                VERIFY_EMBEDDING_KEY,
                content_type="verify",
                source_line="shared",
                title="verify",
                body="temporary",
                model="zero-vector",
                dim=DEFAULT_EMBEDDING_DIM,
                embedding=half,
                metadata_json={"check": "vector-crud"},
            )
            session.flush()
            session.delete(verify_emb)
            session.commit()

        with engine.connect() as conn:
            dist = conn.execute(
                text(
                    """
                    SELECT embedding <=> CAST(:q AS vector) AS dist
                    FROM content_embeddings
                    WHERE embedding_key = :k
                    """
                ),
                {
                    "k": f"{SEED_PREFIX}-embedding",
                    "q": "[" + ",".join(["0"] * DEFAULT_EMBEDDING_DIM) + "]",
                },
            ).scalar_one()
        print(f"vector distance smoke (demo vs zero): {dist}")
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
    print("pgvector: OK")
    print("content KG tables: OK")
    print("publish_gates default locked: OK")
    print(f"Demo run key: {SEED_PREFIX}-run")
    print(f"Demo embedding key: {SEED_PREFIX}-embedding")
    print("CRUD smoke: passed")


def report() -> None:
    """Print a read-only summary of the current database state."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            tables = sorted(inspect(conn).get_table_names())
            ext = conn.execute(
                text("SELECT extname FROM pg_extension WHERE extname = 'vector'")
            ).scalar_one_or_none()
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
                if (
                    session.execute(select(orm_model.id).where(column == expected_key)).scalar_one_or_none()
                    is not None
                ):
                    found_demo_keys.append((label, expected_key))
    except SQLAlchemyError as exc:
        _die_db_error("report", exc)

    print(f"DB report for {PROJECT_NAME}")
    print(f"DATABASE_URL: {_masked_database_url()}")
    print(f"pgvector: {'OK' if ext == 'vector' else 'MISSING'}")
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
        print("Demo/bootstrap keys: missing (run seed)")


def bootstrap() -> None:
    """Create tables, seed demo data, and verify the result."""
    init_db()
    seed()
    verify()


def main() -> None:
    parser = argparse.ArgumentParser(description=f"{PROJECT_NAME} database utilities (pgvector)")
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
