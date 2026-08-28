"""ORM models for meiti: agent audit + content embeddings + content KG."""

from __future__ import annotations

import os
from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import UserDefinedType

from scripts.db.engine import Base

DEFAULT_EMBEDDING_DIM = int(os.environ.get("MEITI_EMBEDDING_DIM", "1536"))


class Vector(UserDefinedType):
    """Minimal pgvector type without requiring the pgvector Python package."""

    cache_ok = True

    def __init__(self, dim: int = DEFAULT_EMBEDDING_DIM):
        self.dim = dim

    def get_col_spec(self, **_kw) -> str:
        return f"vector({self.dim})"

    def bind_processor(self, _dialect):
        def process(value):
            if value is None:
                return None
            if isinstance(value, str):
                return value
            return "[" + ",".join(str(float(x)) for x in value) + "]"

        return process

    def result_processor(self, _dialect, _coltype):
        def process(value):
            if value is None:
                return None
            if isinstance(value, list):
                return value
            s = str(value).strip()
            if s.startswith("[") and s.endswith("]"):
                inner = s[1:-1].strip()
                if not inner:
                    return []
                return [float(x) for x in inner.split(",")]
            return value

        return process


class AgentRun(Base):
    """One agent execution or workflow run."""

    __tablename__ = "agent_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_key = Column(String(255), nullable=False)
    run_type = Column(String(80), nullable=False, default="manual")
    status = Column(String(40), nullable=False, default="running")
    model = Column(String(120))
    prompt_summary = Column(Text)
    inputs = Column(JSONB, nullable=False, default=dict)
    outputs = Column(JSONB, nullable=False, default=dict)
    error_message = Column(Text)
    source = Column(Text, nullable=False, default="meiti")
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    finished_at = Column(DateTime)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    __table_args__ = (
        UniqueConstraint("run_key", name="uq_meiti_agent_runs_run_key"),
        Index("idx_meiti_agent_runs_status", "status"),
        Index("idx_meiti_agent_runs_started_at", "started_at"),
    )


class AgentTask(Base):
    """A durable task owned or processed by the project agent."""

    __tablename__ = "agent_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_key = Column(String(255), nullable=False)
    run_id = Column(Integer, ForeignKey("agent_runs.id", ondelete="SET NULL"))
    title = Column(Text, nullable=False)
    status = Column(String(40), nullable=False, default="pending")
    priority = Column(String(40), nullable=False, default="normal")
    owner_model = Column(String(120))
    payload = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
    completed_at = Column(DateTime)

    __table_args__ = (
        UniqueConstraint("task_key", name="uq_meiti_agent_tasks_task_key"),
        Index("idx_meiti_agent_tasks_status", "status"),
        Index("idx_meiti_agent_tasks_run_id", "run_id"),
    )


class AgentDecision(Base):
    """A persisted decision with rationale and alternatives."""

    __tablename__ = "agent_decisions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    decision_key = Column(String(255), nullable=False)
    run_id = Column(Integer, ForeignKey("agent_runs.id", ondelete="SET NULL"))
    task_id = Column(Integer, ForeignKey("agent_tasks.id", ondelete="SET NULL"))
    decision_type = Column(String(80), nullable=False, default="architecture")
    summary = Column(Text, nullable=False)
    rationale = Column(Text)
    alternatives = Column(JSONB, nullable=False, default=list)
    source = Column(Text, nullable=False, default="meiti")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("decision_key", name="uq_meiti_agent_decisions_decision_key"),
        Index("idx_meiti_agent_decisions_run_id", "run_id"),
        Index("idx_meiti_agent_decisions_task_id", "task_id"),
    )


class AgentArtifact(Base):
    """Evidence, generated output, or external artifact tracked by the agent."""

    __tablename__ = "agent_artifacts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    artifact_key = Column(String(255), nullable=False)
    run_id = Column(Integer, ForeignKey("agent_runs.id", ondelete="SET NULL"))
    task_id = Column(Integer, ForeignKey("agent_tasks.id", ondelete="SET NULL"))
    artifact_type = Column(String(80), nullable=False, default="evidence")
    path = Column(Text)
    uri = Column(Text)
    checksum = Column(String(128))
    metadata_json = Column("metadata", JSONB, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("artifact_key", name="uq_meiti_agent_artifacts_artifact_key"),
        Index("idx_meiti_agent_artifacts_run_id", "run_id"),
        Index("idx_meiti_agent_artifacts_task_id", "task_id"),
        Index("idx_meiti_agent_artifacts_type", "artifact_type"),
    )


class AgentMetric(Base):
    """Numeric measurement emitted by an agent run or validation step."""

    __tablename__ = "agent_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    metric_key = Column(String(255), nullable=False)
    run_id = Column(Integer, ForeignKey("agent_runs.id", ondelete="SET NULL"))
    metric_name = Column(String(120), nullable=False)
    metric_value = Column(Numeric(18, 6), nullable=False)
    unit = Column(String(40))
    dimensions = Column(JSONB, nullable=False, default=dict)
    observed_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("metric_key", name="uq_meiti_agent_metrics_metric_key"),
        Index("idx_meiti_agent_metrics_run_id", "run_id"),
        Index("idx_meiti_agent_metrics_name", "metric_name"),
    )


class AgentRecord(Base):
    """Generic structured record for project-specific payloads."""

    __tablename__ = "agent_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    record_key = Column(String(255), nullable=False)
    record_type = Column(String(80), nullable=False, default="runtime")
    payload = Column(JSONB, nullable=False, default=dict)
    source = Column(Text, nullable=False, default="meiti")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    __table_args__ = (
        UniqueConstraint("record_key", name="uq_meiti_agent_records_record_key"),
        Index("idx_meiti_agent_records_type", "record_type"),
    )


class ContentEmbedding(Base):
    """Content chunk + vector for semantic retrieval (pgvector)."""

    __tablename__ = "content_embeddings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    embedding_key = Column(String(255), nullable=False)
    content_type = Column(String(80), nullable=False, default="chunk")
    # novel | post | caption | research | note | package | other
    source_line = Column(String(40), nullable=False, default="shared")
    # xiaoshuo | xiaoping | shared
    title = Column(Text)
    body = Column(Text, nullable=False, default="")
    uri = Column(Text)
    path = Column(Text)
    platform = Column(String(80))
    language = Column(String(20), nullable=False, default="zh")
    model = Column(String(120), nullable=False, default="pending")
    dim = Column(Integer, nullable=False, default=DEFAULT_EMBEDDING_DIM)
    embedding = Column(Vector(DEFAULT_EMBEDDING_DIM))
    metadata_json = Column("metadata", JSONB, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    __table_args__ = (
        UniqueConstraint("embedding_key", name="uq_meiti_content_embeddings_key"),
        Index("idx_meiti_content_embeddings_type", "content_type"),
        Index("idx_meiti_content_embeddings_line", "source_line"),
        Index("idx_meiti_content_embeddings_platform", "platform"),
    )


class ContentEntity(Base):
    """Content knowledge-graph node: topic / platform / CTA / package / hook / etc."""

    __tablename__ = "content_entities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    entity_key = Column(String(255), nullable=False)
    entity_type = Column(String(80), nullable=False, default="topic")
    # topic | platform | cta | package | hook | offer | evidence | review | audience
    name = Column(Text, nullable=False)
    description = Column(Text)
    source_line = Column(String(40), nullable=False, default="shared")
    properties = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    __table_args__ = (
        UniqueConstraint("entity_key", name="uq_meiti_content_entities_key"),
        Index("idx_meiti_content_entities_type", "entity_type"),
        Index("idx_meiti_content_entities_line", "source_line"),
    )


class ContentRelation(Base):
    """Directed edge between content entities (选题–平台–CTA–复盘)."""

    __tablename__ = "content_relations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    relation_key = Column(String(255), nullable=False)
    relation_type = Column(String(80), nullable=False, default="related_to")
    # targets | adapts_to | uses_hook | has_cta | monetizes_via | reviewed_by | derived_from
    from_entity_id = Column(
        Integer, ForeignKey("content_entities.id", ondelete="CASCADE"), nullable=False
    )
    to_entity_id = Column(
        Integer, ForeignKey("content_entities.id", ondelete="CASCADE"), nullable=False
    )
    weight = Column(Numeric(12, 6), nullable=False, default=1.0)
    properties = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("relation_key", name="uq_meiti_content_relations_key"),
        Index("idx_meiti_content_relations_type", "relation_type"),
        Index("idx_meiti_content_relations_from", "from_entity_id"),
        Index("idx_meiti_content_relations_to", "to_entity_id"),
    )


class PublishGate(Base):
    """Persistent gate for a DistributionJob and registered Integration."""

    __tablename__ = "publish_gates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    gate_key = Column(String(255), nullable=False)
    action = Column(String(80), nullable=False, default="publish")
    # publish | login | dm | list | quote | collect | ads | automation
    integration_id = Column(String(255), index=True)
    distribution_job_id = Column(String(255), index=True)
    status = Column(String(40), nullable=False, default="locked")
    # locked | requested | approved | denied | expired | executed
    requested_by = Column(String(120), nullable=False, default="agent")
    approved_by = Column(String(120))
    rationale = Column(Text)
    checks = Column(JSONB, nullable=False, default=dict)
    evidence = Column(JSONB, nullable=False, default=dict)
    expires_at = Column(DateTime)
    decided_at = Column(DateTime)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    __table_args__ = (
        UniqueConstraint("gate_key", name="uq_meiti_publish_gates_key"),
        Index("idx_meiti_publish_gates_status", "status"),
        Index("idx_meiti_publish_gates_action", "action"),
        Index("idx_meiti_publish_gates_job", "distribution_job_id"),
    )
