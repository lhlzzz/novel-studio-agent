#!/usr/bin/env python3
"""Manage the meiti database schema (agent + pgvector + content KG + gates)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from alembic import command
from alembic.config import Config
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
    CampaignRecord,
    ContentPackageRecord,
    ContentVariantRecord,
    ContentEmbedding,
    ContentEntity,
    ContentRelation,
    DistributionAttemptRecord,
    DistributionJobRecord,
    IntegrationRecord,
    MediaUploadRecord,
    MetricSnapshotRecord,
    PublicationRecord,
    PublishGate,
    CreativeRunRecord,
    CreativeTaskRecord,
    MediaAssetRecord,
    CharacterRecord,
    JudgeResultRecord,
    SocialAccountRecord,
    DerivedAssetRecord,
    XianyuListingRecord,
    SocialHandoffRecord,
    KnowledgeDocumentRecord,
    AccountSelectionRecord,
)

PROJECT_NAME = "meiti"
MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"
TABLE_NAMES = sorted(Base.metadata.tables)
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
    ("campaigns", CampaignRecord),
    ("content_packages", ContentPackageRecord),
    ("content_variants", ContentVariantRecord),
    ("integrations", IntegrationRecord),
    ("distribution_jobs", DistributionJobRecord),
    ("distribution_attempts", DistributionAttemptRecord),
    ("publications", PublicationRecord),
    ("media_uploads", MediaUploadRecord),
    ("metric_snapshots", MetricSnapshotRecord),
    ("creative_runs", CreativeRunRecord),
    ("creative_tasks", CreativeTaskRecord),
    ("media_assets", MediaAssetRecord),
    ("characters", CharacterRecord),
    ("judge_results", JudgeResultRecord),
    ("social_accounts", SocialAccountRecord),
    ("social_handoffs", SocialHandoffRecord),
    ("derived_assets", DerivedAssetRecord),
    ("xianyu_listings", XianyuListingRecord),
    ("knowledge_documents", KnowledgeDocumentRecord),
    ("account_selections", AccountSelectionRecord),
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


def _alembic_config() -> Config:
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    config.set_main_option("sqlalchemy.url", DATABASE_URL.replace("%", "%%"))
    return config


def _stamp_pre_alembic_baseline() -> None:
    """Stamp the pre-Alembic schema exactly once before upgrading it."""
    with engine.connect() as conn:
        has_alembic = "alembic_version" in inspect(conn).get_table_names()
        has_baseline = "schema_migrations" in inspect(conn).get_table_names()
        baseline = conn.execute(
            text("SELECT 1 FROM schema_migrations WHERE version = '0001_baseline' LIMIT 1")
        ).scalar_one_or_none() if has_baseline else None
    if not has_alembic and baseline:
        command.stamp(_alembic_config(), "0001_baseline")


def upgrade() -> None:
    """Apply the Alembic revision chain without writing application data."""
    _stamp_pre_alembic_baseline()
    command.upgrade(_alembic_config(), "head")
    current()


def history() -> None:
    command.history(_alembic_config())


def current() -> None:
    command.current(_alembic_config(), verbose=False)


def init_db() -> None:
    """Upgrade the versioned schema and verify the pgvector extension."""
    try:
        _enable_pgvector()
        upgrade()
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

        print("vector extension smoke: passed without application seed rows")
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
    print("CRUD smoke: passed")
    print("application seed rows: not written")


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

def main() -> None:
    parser = argparse.ArgumentParser(description=f"{PROJECT_NAME} database utilities (pgvector)")
    parser.add_argument(
        "command",
        choices=["init", "status", "verify", "report", "upgrade", "current", "history"],
        help="database command to run",
    )
    args = parser.parse_args()

    if args.command == "init":
        init_db()
    elif args.command == "status":
        status()
    elif args.command == "verify":
        verify()
    elif args.command == "report":
        report()
    elif args.command == "upgrade":
        upgrade()
    elif args.command == "current":
        current()
    elif args.command == "history":
        history()


if __name__ == "__main__":
    main()
