"""ORM models for xiaoping agent persistence."""

from __future__ import annotations

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

from scripts.db.engine import Base


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
    source = Column(Text, nullable=False, default="xiaoping")
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
        UniqueConstraint("run_key", name="uq_xiaoping_agent_runs_run_key"),
        Index("idx_xiaoping_agent_runs_status", "status"),
        Index("idx_xiaoping_agent_runs_started_at", "started_at"),
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
        UniqueConstraint("task_key", name="uq_xiaoping_agent_tasks_task_key"),
        Index("idx_xiaoping_agent_tasks_status", "status"),
        Index("idx_xiaoping_agent_tasks_run_id", "run_id"),
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
    source = Column(Text, nullable=False, default="xiaoping")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("decision_key", name="uq_xiaoping_agent_decisions_decision_key"),
        Index("idx_xiaoping_agent_decisions_run_id", "run_id"),
        Index("idx_xiaoping_agent_decisions_task_id", "task_id"),
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
        UniqueConstraint("artifact_key", name="uq_xiaoping_agent_artifacts_artifact_key"),
        Index("idx_xiaoping_agent_artifacts_run_id", "run_id"),
        Index("idx_xiaoping_agent_artifacts_task_id", "task_id"),
        Index("idx_xiaoping_agent_artifacts_type", "artifact_type"),
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
        UniqueConstraint("metric_key", name="uq_xiaoping_agent_metrics_metric_key"),
        Index("idx_xiaoping_agent_metrics_run_id", "run_id"),
        Index("idx_xiaoping_agent_metrics_name", "metric_name"),
    )


class AgentRecord(Base):
    """Generic structured record for project-specific payloads."""

    __tablename__ = "agent_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    record_key = Column(String(255), nullable=False)
    record_type = Column(String(80), nullable=False, default="runtime")
    payload = Column(JSONB, nullable=False, default=dict)
    source = Column(Text, nullable=False, default="xiaoping")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    __table_args__ = (
        UniqueConstraint("record_key", name="uq_xiaoping_agent_records_record_key"),
        Index("idx_xiaoping_agent_records_type", "record_type"),
    )
