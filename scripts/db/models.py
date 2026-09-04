"""ORM models for meiti: agent audit + content embeddings + content KG."""

from __future__ import annotations

import os
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy import JSON as SA_JSON
from sqlalchemy.dialects.postgresql import JSONB

JSONType = SA_JSON().with_variant(JSONB(), "postgresql")
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

    def load_dialect_impl(self, dialect):
        if dialect.name == "sqlite":
            return dialect.type_descriptor(Text())
        return super().load_dialect_impl(dialect)

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
    inputs = Column(JSONType, nullable=False, default=dict)
    outputs = Column(JSONType, nullable=False, default=dict)
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
    payload = Column(JSONType, nullable=False, default=dict)
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
    alternatives = Column(JSONType, nullable=False, default=list)
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
    metadata_json = Column("metadata", JSONType, nullable=False, default=dict)
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
    dimensions = Column(JSONType, nullable=False, default=dict)
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
    payload = Column(JSONType, nullable=False, default=dict)
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
    metadata_json = Column("metadata", JSONType, nullable=False, default=dict)
    account_id = Column(String(255))
    scope_type = Column(String(40))
    scope_id = Column(String(255))
    character_id = Column(String(255))
    world_id = Column(String(255))
    series_id = Column(String(255))
    episode_id = Column(String(255))
    publication_id = Column(String(255))
    source_document_id = Column(String(255))
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
        Index("idx_meiti_content_embeddings_account", "account_id"),
        Index("idx_meiti_content_embeddings_scope", "scope_type", "scope_id"),
        Index("idx_meiti_content_embeddings_document", "source_document_id"),
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
    properties = Column(JSONType, nullable=False, default=dict)
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
    properties = Column(JSONType, nullable=False, default=dict)
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
    checks = Column(JSONType, nullable=False, default=dict)
    evidence = Column(JSONType, nullable=False, default=dict)
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


class CampaignRecord(Base):
    """First-class content campaign owned by Meiti."""

    __tablename__ = "campaigns"

    campaign_id = Column(String(255), primary_key=True)
    brand_id = Column(String(255), nullable=False, default="")
    creator_id = Column(String(255), nullable=False, default="")
    objective = Column(Text, nullable=False)
    audience = Column(Text, nullable=False, default="")
    strategy_id = Column(String(255))
    start_at = Column(DateTime)
    end_at = Column(DateTime)
    success_metrics = Column(JSONType, nullable=False, default=list)
    status = Column(String(40), nullable=False, default="draft")
    account_id = Column(String(255))
    platform = Column(String(120), nullable=False, default="")
    parent_campaign_id = Column(String(255))
    series_id = Column(String(255))
    world_id = Column(String(255))
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class ContentPackageRecord(Base):
    """Durable content package; platform variants remain separate records."""

    __tablename__ = "content_packages"

    package_id = Column(String(255), primary_key=True)
    brand_id = Column(String(255))
    creator_id = Column(String(255))
    campaign_id = Column(String(255), ForeignKey("campaigns.campaign_id", ondelete="SET NULL"))
    topic = Column(Text, nullable=False, default="")
    content_pillar = Column(String(255), nullable=False, default="")
    hook = Column(Text, nullable=False, default="")
    format = Column(String(80), nullable=False, default="post")
    audience = Column(Text, nullable=False, default="")
    title = Column(Text, nullable=False)
    caption = Column(Text, nullable=False, default="")
    body = Column(Text, nullable=False)
    evidence_ids = Column(JSONType, nullable=False, default=list)
    media_assets = Column(JSONType, nullable=False, default=list)
    commerce_intent = Column(String(120), nullable=False, default="none")
    variants = Column(JSONType, nullable=False, default=list)
    metadata_json = Column("metadata", JSONType, nullable=False, default=dict)
    account_id = Column(String(255))
    series_id = Column(String(255))
    episode_id = Column(String(255))
    platform = Column(String(120), nullable=False, default="")
    status = Column(String(40), nullable=False, default="DRAFT")
    character_id = Column(String(255))
    world_id = Column(String(255))
    creative_context_id = Column(String(255))
    revision = Column(Integer, nullable=False, default=1)
    current_revision = Column(String(255))
    reference_assets = Column(JSONType, nullable=False, default=list)
    primary_assets = Column(JSONType, nullable=False, default=list)
    published_assets = Column(JSONType, nullable=False, default=list)
    prompt_id = Column(String(255))
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class ContentVariantRecord(Base):
    """A platform-specific rendering of a provider-neutral content package."""

    __tablename__ = "content_variants"

    variant_id = Column(String(255), primary_key=True)
    package_id = Column(String(255), ForeignKey("content_packages.package_id", ondelete="CASCADE"), nullable=False)
    integration_id = Column(String(255), nullable=False)
    body = Column(Text, nullable=False, default="")
    title = Column(Text, nullable=False, default="")
    caption = Column(Text, nullable=False, default="")
    media = Column(JSONType, nullable=False, default=list)
    settings = Column(JSONType, nullable=False, default=dict)
    platform_metadata = Column(JSONType, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("package_id", "integration_id", name="uq_meiti_content_variant_target"),
        Index("idx_meiti_content_variants_package", "package_id"),
    )



class SocialAccountRecord(Base):
    """Native social account metadata. Tokens live in the runtime secret store."""

    __tablename__ = "social_accounts"

    account_id = Column(String(255), primary_key=True)
    provider = Column(String(120), nullable=False)
    platform = Column(String(120), nullable=False)
    username = Column(Text, nullable=False, default="")
    display_name = Column(Text, nullable=False, default="")
    avatar_url = Column(Text, nullable=False, default="")
    status = Column(String(40), nullable=False, default="PENDING")
    capabilities = Column(JSONType, nullable=False, default=dict)
    credential_ref = Column(String(255), nullable=False, default="")
    provider_account_id = Column(String(255), nullable=False, default="")
    region = Column(String(80), nullable=False, default="global")
    last_verified_at = Column(DateTime)
    blocked_reason = Column(Text)
    revoke_attempted = Column(Integer, nullable=False, default=0)
    remote_revoked = Column(Integer, nullable=False, default=0)
    remote_revoke_supported = Column(Integer)
    revoke_error = Column(Text)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING','AUTHENTICATING','AUTHENTICATED','VERIFYING','VERIFIED','ENABLED','DEGRADED','EXPIRED','REVOKED','BLOCKED','TARGET_ONLY','HANDOFF_READY','IDENTITY_UNVERIFIED','REFRESHING')",
            name="ck_meiti_social_account_status",
        ),
        Index("idx_meiti_social_accounts_provider", "provider"),
        Index("idx_meiti_social_accounts_status", "status"),
    )


class SocialHandoffRecord(Base):
    """XHS handoff is not a Publication."""

    __tablename__ = "social_handoffs"

    handoff_id = Column(String(255), primary_key=True)
    provider = Column(String(120), nullable=False, default="xiaohongshu")
    platform = Column(String(120), nullable=False, default="xiaohongshu")
    account_id = Column(String(255), nullable=False)
    content_package_id = Column(String(255), nullable=False, default="")
    status = Column(String(40), nullable=False, default="READY_FOR_XHS")
    export_path = Column(Text, nullable=False, default="")
    export_status = Column(String(40), nullable=False, default="PENDING")
    distribution_job_id = Column(String(255), nullable=False, default="")
    package = Column(JSONType, nullable=False, default=dict)
    expires_at = Column(DateTime)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        CheckConstraint(
            "status IN ('READY_FOR_XHS','OPENED','SUBMITTED','PUBLISHED','EXPIRED','CANCELLED')",
            name="ck_meiti_social_handoff_status",
        ),
        Index("idx_meiti_social_handoffs_account", "account_id"),
        Index("uq_meiti_social_handoffs_job", "distribution_job_id", unique=True, postgresql_where=text("distribution_job_id <> ''")),
        CheckConstraint("export_status IN ('PENDING','READY','FAILED')", name="ck_meiti_social_handoff_export_status"),
    )


class DerivedAssetRecord(Base):
    """Platform-specific derived media. Original MediaAsset is immutable."""

    __tablename__ = "derived_assets"

    derived_asset_id = Column(String(255), primary_key=True)
    source_asset_id = Column(String(255), nullable=False)
    target_platform = Column(String(80), nullable=False)
    transformation = Column(Text, nullable=False, default="")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_meiti_derived_assets_source", "source_asset_id"),
        Index("idx_meiti_derived_assets_platform", "target_platform"),
    )


class IntegrationRecord(Base):
    """Runtime-verified provider account, distinct from provider registration."""

    __tablename__ = "integrations"

    integration_id = Column(String(255), primary_key=True)
    provider = Column(String(120), nullable=False)
    platform = Column(String(120), nullable=False, default="")
    account_id = Column(String(255), nullable=False, default="")
    account_name = Column(Text, nullable=False, default="")
    region = Column(String(80), nullable=False, default="global")
    state = Column(String(40), nullable=False, default="REGISTERED")
    enabled = Column(Integer, nullable=False, default=0)
    capabilities = Column(JSONType, nullable=False, default=dict)
    verified_at = Column(DateTime)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        CheckConstraint("enabled IN (0, 1)", name="ck_meiti_integrations_enabled"),
        Index("idx_meiti_integrations_provider", "provider"),
        Index("idx_meiti_integrations_state", "state"),
    )


class DistributionJobRecord(Base):
    """Durable job identity and lifecycle state for external actions."""

    __tablename__ = "distribution_jobs"

    job_id = Column(String(255), primary_key=True)
    content_package_id = Column(String(255), ForeignKey("content_packages.package_id", ondelete="RESTRICT"), nullable=False)
    integration_id = Column(String(255), ForeignKey("integrations.integration_id", ondelete="RESTRICT"), nullable=False)
    action = Column(String(40), nullable=False, default="publish")
    status = Column(String(40), nullable=False, default="DRAFT")
    idempotency_key = Column(String(255), nullable=False, unique=True)
    variant = Column(JSONType, nullable=False, default=dict)
    scheduled_at = Column(DateTime)
    last_attempt_at = Column(DateTime)
    attempt_count = Column(Integer, nullable=False, default=0)
    error_code = Column(String(120))
    error_message = Column(Text)
    provider_response = Column(JSONType)
    brand_id = Column(String(255))
    creator_id = Column(String(255))
    campaign_id = Column(String(255))
    request_id = Column(String(255), nullable=False, default="")
    account_id = Column(String(255), nullable=False, default="")
    lease_until = Column(DateTime)
    worker_id = Column(String(255))
    claimed_at = Column(DateTime)
    provider = Column(String(120), nullable=False, default="")
    platform = Column(String(120), nullable=False, default="")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        CheckConstraint(
            "status IN ('DRAFT','VALIDATING','BLOCKED','READY','SUBMITTING','SUBMITTED','SCHEDULED','PUBLISHING','PUBLISHED','FAILED','RETRYING','CANCELLED','UNKNOWN','FAILED_PERMANENT','RECONCILING','PROCESSING')",
            name="ck_meiti_distribution_job_status",
        ),
        Index("idx_meiti_distribution_jobs_status", "status"),
        Index("idx_meiti_distribution_jobs_schedule", "scheduled_at"),
    )


class DistributionAttemptRecord(Base):
    """Immutable attempt audit row for each provider submission."""

    __tablename__ = "distribution_attempts"

    attempt_id = Column(String(255), primary_key=True)
    distribution_job_id = Column(String(255), ForeignKey("distribution_jobs.job_id", ondelete="CASCADE"), nullable=False)
    attempt_no = Column(Integer, nullable=False)
    provider = Column(String(120), nullable=False, default="")
    integration_id = Column(String(255), nullable=False, default="")
    started_at = Column(DateTime, nullable=False)
    finished_at = Column(DateTime)
    status = Column(String(40), nullable=False)
    error_code = Column(String(120))
    error_message = Column(Text)
    provider_request_id = Column(String(255))
    provider_object_id = Column(String(255))
    response_summary = Column(JSONType)
    request_id = Column(String(255), nullable=False, default="")

    __table_args__ = (
        UniqueConstraint("distribution_job_id", "attempt_no", name="uq_meiti_distribution_attempt_no"),
        Index("idx_meiti_distribution_attempts_job", "distribution_job_id"),
    )


class PublicationRecord(Base):
    """Durable mapping between Meiti job and provider/platform identifiers."""

    __tablename__ = "publications"

    publication_id = Column(String(255), primary_key=True)
    distribution_job_id = Column(String(255), ForeignKey("distribution_jobs.job_id", ondelete="RESTRICT"), nullable=False, unique=True)
    integration_id = Column(String(255), ForeignKey("integrations.integration_id", ondelete="RESTRICT"), nullable=False)
    provider = Column(String(120), nullable=False)
    provider_post_id = Column(String(255), nullable=False)
    platform_object_id = Column(String(255))
    external_url = Column(Text)
    status = Column(String(40), nullable=False, default="UNKNOWN")
    published_at = Column(DateTime)
    content_package_id = Column(String(255), nullable=False)
    request_id = Column(String(255), nullable=False, default="")
    platform = Column(String(120), nullable=False, default="")
    account_id = Column(String(255), nullable=False, default="")
    provider_object_type = Column(String(40), nullable=False, default="")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("provider", "provider_post_id", name="uq_meiti_publication_provider_post"),
        Index("idx_meiti_publications_integration", "integration_id"),
        Index("idx_meiti_publications_status", "status"),
    )


class MediaUploadRecord(Base):
    """Provider media upload cache keyed by source SHA-256."""

    __tablename__ = "media_uploads"

    source_hash = Column(String(64), primary_key=True)
    source_path = Column(Text, nullable=False)
    mime_type = Column(String(120), nullable=False)
    size = Column(Integer, nullable=False)
    provider = Column(String(120), primary_key=True)
    account_id = Column(String(255), primary_key=True, default="")
    integration_id = Column(String(255), nullable=False, default="")
    remote_media_id = Column(String(255), nullable=False)
    remote_media_path = Column(Text, nullable=False)
    status = Column(String(40), nullable=False, default="UPLOADED")
    uploaded_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    platform = Column(String(120), nullable=False, default="")
    source_asset_id = Column(String(255), nullable=False, default="")
    media_type = Column(String(40), nullable=False, default="")
    provider_request_id = Column(String(255))
    checksum = Column(String(64), nullable=False, default="")
    completed_at = Column(DateTime)
    error_code = Column(String(120))
    error_message = Column(Text)

    __table_args__ = (
        Index("idx_meiti_media_uploads_provider", "provider"),
        Index("idx_meiti_media_uploads_status", "status"),
    )




class XianyuListingRecord(Base):
    """Commerce listing identity. Not a social post."""

    __tablename__ = "xianyu_listings"

    listing_id = Column(String(255), primary_key=True)
    account_id = Column(String(255), nullable=False)
    provider_item_id = Column(String(255), nullable=False, default="")
    title = Column(Text, nullable=False, default="")
    description = Column(Text, nullable=False, default="")
    price = Column(String(40), nullable=False, default="")
    category_id = Column(String(255), nullable=False, default="")
    media_assets = Column(JSONType, nullable=False, default=list)
    status = Column(String(40), nullable=False, default="DRAFT")
    provider_response = Column(JSONType, nullable=False, default=dict)
    quantity = Column(Integer, nullable=False, default=1)
    content_package_id = Column(String(255), nullable=False, default="")
    distribution_job_id = Column(String(255), nullable=False, default="")
    condition = Column(String(40), nullable=False, default="new")
    location = Column(Text, nullable=False, default="")
    shipping = Column(JSONType, nullable=False, default=dict)
    attributes = Column(JSONType, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        CheckConstraint(
            "status IN ('DRAFT','SUBMITTED','PUBLISHED','OFF_SHELF','FAILED','UNKNOWN')",
            name="ck_meiti_xianyu_listing_status",
        ),
        Index("uq_meiti_xianyu_listings_job", "distribution_job_id", unique=True, postgresql_where=text("distribution_job_id <> ''")),
        Index("idx_meiti_xianyu_listings_account", "account_id"),
        Index("idx_meiti_xianyu_listings_status", "status"),
        Index("idx_meiti_xianyu_listings_item", "provider_item_id"),
    )

class MetricSnapshotRecord(Base):
    """Append-only metric observation; collection never overwrites history."""

    __tablename__ = "metric_snapshots"

    snapshot_id = Column(Integer, primary_key=True, autoincrement=True)
    publication_id = Column(String(255), ForeignKey("publications.publication_id", ondelete="CASCADE"), nullable=False)
    metric_name = Column(String(120), nullable=False)
    value = Column(Numeric(18, 6))
    observed_at = Column(DateTime, nullable=False)
    source = Column(String(255), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("publication_id", "metric_name", "observed_at", "source", name="uq_meiti_metric_snapshot"),
        Index("idx_meiti_metric_snapshots_publication", "publication_id"),
        Index("idx_meiti_metric_snapshots_observed", "observed_at"),
    )


CREATIVE_TABLE_NAMES = (
    "creative_workflows",
    "creative_runs",
    "creative_tasks",
    "creative_node_outputs",
    "media_assets",
    "characters",
    "prompt_assets",
    "generation_usage",
    "workflow_performance",
    "judge_results",
    "creative_events",
)


class CreativeWorkflowRecord(Base):
    """Immutable workflow version snapshot. This is WorkflowVersion."""

    __tablename__ = "creative_workflows"

    workflow_id = Column(String(255), primary_key=True)
    version = Column(String(80), primary_key=True)
    name = Column(Text, nullable=False, default="")
    description = Column(Text, nullable=False, default="")
    category = Column(String(80), nullable=False, default="video")
    inputs = Column(JSONType, nullable=False, default=dict)
    nodes = Column(JSONType, nullable=False, default=list)
    edges = Column(JSONType, nullable=False, default=list)
    variables = Column(JSONType, nullable=False, default=dict)
    quality_policy = Column(JSONType, nullable=False, default=dict)
    outputs = Column(JSONType, nullable=False, default=dict)
    snapshot = Column(JSONType, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)


WorkflowVersionRecord = CreativeWorkflowRecord


class CreativeRunRecord(Base):
    __tablename__ = "creative_runs"

    run_id = Column(String(255), primary_key=True)
    workflow_id = Column(String(255), nullable=False)
    workflow_version = Column(String(80), nullable=False)
    status = Column(String(40), nullable=False, default="DRAFT")
    inputs = Column(JSONType, nullable=False, default=dict)
    outputs = Column(JSONType, nullable=False, default=dict)
    estimated_cost = Column(Numeric(18, 6), nullable=False, default=0)
    actual_cost = Column(Numeric(18, 6), nullable=False, default=0)
    budget = Column(Numeric(18, 6))
    idempotency_key = Column(String(255), unique=True)
    replay_of = Column(String(255))
    cursor = Column(Integer, nullable=False, default=0)
    node_outputs = Column(JSONType, nullable=False, default=dict)
    judge_results = Column(JSONType, nullable=False, default=list)
    quality = Column(JSONType, nullable=False, default=dict)
    error = Column(Text)
    error_code = Column(String(80))
    workflow_snapshot = Column(JSONType, nullable=False, default=dict)
    asset_ids = Column(JSONType, nullable=False, default=list)
    task_ids = Column(JSONType, nullable=False, default=list)
    selected_asset_id = Column(String(255))
    selection_reason = Column(Text)
    selection_score = Column(Numeric(18, 6))
    worker_id = Column(String(255))
    lease_until = Column(DateTime)
    heartbeat_at = Column(DateTime)
    request_id = Column(String(255), nullable=False, default="")
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    blocked_reason = Column(String(80))
    blocked_message = Column(Text)
    blocked_at = Column(DateTime)
    retryable = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_creative_runs_status", "status"),
        Index("idx_creative_runs_workflow", "workflow_id", "workflow_version"),
        Index("idx_creative_runs_lease", "lease_until"),
    )


class CreativeTaskRecord(Base):
    __tablename__ = "creative_tasks"

    task_id = Column(String(255), primary_key=True)
    run_id = Column(String(255), ForeignKey("creative_runs.run_id", ondelete="CASCADE"), nullable=False)
    node_id = Column(String(255), nullable=False)
    provider = Column(String(120), nullable=False)
    provider_task_id = Column(String(255), nullable=False, default="")
    kind = Column(String(80), nullable=False, default="")
    status = Column(String(40), nullable=False, default="QUEUED")
    payload = Column(JSONType, nullable=False, default=dict)
    result = Column(JSONType, nullable=False, default=dict)
    poll_count = Column(Integer, nullable=False, default=0)
    attempt = Column(Integer, nullable=False, default=0)
    execution_key = Column(String(255), nullable=False, default="")
    error = Column(Text)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    timeout_at = Column(DateTime)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("execution_key", name="uq_creative_task_execution"),
        Index("idx_creative_tasks_run", "run_id"),
        Index("idx_creative_tasks_status", "status"),
        Index("idx_creative_tasks_provider_task", "provider_task_id"),
    )


class CreativeNodeOutputRecord(Base):
    __tablename__ = "creative_node_outputs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(255), ForeignKey("creative_runs.run_id", ondelete="CASCADE"), nullable=False)
    node_id = Column(String(255), nullable=False)
    output = Column(JSONType, nullable=False, default=dict)
    assets = Column(JSONType, nullable=False, default=list)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("run_id", "node_id", name="uq_creative_node_output"),
        Index("idx_creative_node_outputs_run", "run_id"),
    )


class MediaAssetRecord(Base):
    __tablename__ = "media_assets"

    asset_id = Column(String(255), primary_key=True)
    sha256 = Column(String(64), nullable=False, unique=True)
    type = Column(String(40), nullable=False)
    path = Column(Text, nullable=False)
    mime_type = Column(String(120), nullable=False, default="")
    size = Column(Integer, nullable=False, default=0)
    width = Column(Integer)
    height = Column(Integer)
    duration = Column(Numeric(18, 6))
    fps = Column(Numeric(18, 6))
    workflow_id = Column(String(255))
    workflow_version = Column(String(80))
    creative_run_id = Column(String(255))
    prompt_id = Column(String(255))
    character_id = Column(String(255))
    metadata_json = Column("metadata", JSONType, nullable=False, default=dict)
    technical_score = Column(Numeric(18, 6))
    visual_score = Column(Numeric(18, 6))
    content_score = Column(Numeric(18, 6))
    platform_score = Column(Numeric(18, 6))
    overall_score = Column(Numeric(18, 6))
    account_id = Column(String(255))
    series_id = Column(String(255))
    episode_id = Column(String(255))
    content_package_id = Column(String(255))
    creative_context_id = Column(String(255))
    world_id = Column(String(255))
    provider = Column(String(120), nullable=False, default="")
    provider_task_id = Column(String(255), nullable=False, default="")
    model = Column(String(120), nullable=False, default="")
    platform = Column(String(120), nullable=False, default="")
    scope_type = Column(String(40), nullable=False, default="PLATFORM_ACCOUNT")
    asset_role = Column(String(40), nullable=False, default="")
    lifecycle = Column(String(40), nullable=False, default="DRAFT")
    pool_id = Column(String(255))
    parent_asset_id = Column(String(255))
    source_asset_id = Column(String(255))
    generation_mode = Column(String(80), nullable=False, default="")
    tool = Column(String(80), nullable=False, default="")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_media_assets_run", "creative_run_id"),
        Index("idx_media_assets_type", "type"),
        Index("idx_media_assets_account", "account_id"),
        Index("idx_media_assets_episode", "episode_id"),
        Index("idx_media_assets_platform", "platform"),
        Index("idx_media_assets_role", "asset_role"),
        Index("idx_media_assets_pool", "pool_id"),
    )


class CharacterRecord(Base):
    __tablename__ = "characters"

    character_id = Column(String(255), primary_key=True)
    name = Column(Text, nullable=False)
    visual_dna = Column(JSONType, nullable=False, default=dict)
    behavior_dna = Column(Text, nullable=False, default="")
    style_dna = Column(Text, nullable=False, default="")
    reference_assets = Column(JSONType, nullable=False, default=list)
    voice_assets = Column(JSONType, nullable=False, default=list)
    notes = Column(Text, nullable=False, default="")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class PromptAssetRecord(Base):
    __tablename__ = "prompt_assets"

    prompt_id = Column(String(255), primary_key=True)
    version = Column(String(80), nullable=False, default="v1")
    family_id = Column(String(255), nullable=False, default="")
    prompt = Column(Text, nullable=False)
    negative_prompt = Column(Text, nullable=False, default="")
    references = Column(JSONType, nullable=False, default=list)
    model = Column(String(120), nullable=False, default="")
    provider = Column(String(120), nullable=False, default="")
    parameters = Column(JSONType, nullable=False, default=dict)
    workflow_id = Column(String(255), nullable=False, default="")
    workflow_version = Column(String(80), nullable=False, default="")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_prompt_assets_family", "family_id"),
        Index("idx_prompt_assets_workflow", "workflow_id", "workflow_version"),
    )


class GenerationUsageRecord(Base):
    __tablename__ = "generation_usage"

    usage_id = Column(String(255), primary_key=True)
    provider = Column(String(120), nullable=False)
    model = Column(String(120), nullable=False, default="")
    task = Column(String(80), nullable=False)
    input = Column(JSONType, nullable=False, default=dict)
    output = Column(JSONType, nullable=False, default=dict)
    credits_estimated = Column(Numeric(18, 6), nullable=False, default=0)
    credits_actual = Column(Numeric(18, 6), nullable=False, default=0)
    status = Column(String(40), nullable=False, default="")
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    run_id = Column(String(255), nullable=False, default="")
    node_id = Column(String(255), nullable=False, default="")
    input_units = Column(Numeric(18, 6), nullable=False, default=0)
    output_units = Column(Numeric(18, 6), nullable=False, default=0)
    duration_ms = Column(Numeric(18, 6), nullable=False, default=0)
    estimated_cost = Column(Numeric(18, 6), nullable=False, default=0)
    actual_cost = Column(Numeric(18, 6), nullable=False, default=0)

    __table_args__ = (
        Index("idx_generation_usage_run", "run_id"),
        Index("idx_generation_usage_provider", "provider"),
    )


class WorkflowPerformanceRecord(Base):
    __tablename__ = "workflow_performance"

    id = Column(Integer, primary_key=True, autoincrement=True)
    workflow_id = Column(String(255), nullable=False)
    version = Column(String(80), nullable=False)
    run_id = Column(String(255), nullable=False, default="")
    asset_id = Column(String(255), nullable=False, default="")
    publication_id = Column(String(255), nullable=False, default="")
    platform = Column(String(80), nullable=False, default="")
    provider = Column(String(120), nullable=False, default="")
    model = Column(String(120), nullable=False, default="")
    character = Column(String(255), nullable=False, default="")
    scene = Column(Text, nullable=False, default="")
    motion = Column(Text, nullable=False, default="")
    camera = Column(Text, nullable=False, default="")
    duration = Column(Numeric(18, 6))
    quality_score = Column(Numeric(18, 6))
    engagement = Column(Numeric(18, 6))
    conversion = Column(Numeric(18, 6))
    cost = Column(Numeric(18, 6))
    latency = Column(Numeric(18, 6))
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_workflow_performance_workflow", "workflow_id", "version"),
        Index("idx_workflow_performance_run", "run_id"),
    )


class JudgeResultRecord(Base):
    __tablename__ = "judge_results"

    judge_id = Column(String(255), primary_key=True)
    asset_id = Column(String(255))
    creative_run_id = Column(String(255), nullable=False, default="")
    judge_type = Column(String(80), nullable=False)
    judge_provider = Column(String(120), nullable=False, default="")
    judge_model = Column(String(120), nullable=False, default="")
    judge_version = Column(String(80), nullable=False, default="")
    score = Column(Numeric(18, 6), nullable=False, default=0)
    breakdown = Column(JSONType, nullable=False, default=dict)
    reasons = Column(JSONType, nullable=False, default=list)
    decision = Column(String(40), nullable=False)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_judge_results_run", "creative_run_id"),
        Index("idx_judge_results_asset", "asset_id"),
    )


class CreativeEventRecord(Base):
    __tablename__ = "creative_events"

    event_id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(255), nullable=False, default="")
    event_type = Column(String(80), nullable=False)
    payload = Column(JSONType, nullable=False, default=dict)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_creative_events_run", "run_id"),
        Index("idx_creative_events_type", "event_type"),
    )


class PlatformAccountRecord(Base):
    __tablename__ = "platform_accounts"

    account_id = Column(String(255), primary_key=True)
    platform = Column(String(120), nullable=False)
    external_account_id = Column(String(255), nullable=False, default="")
    display_name = Column(Text, nullable=False, default="")
    status = Column(String(40), nullable=False, default="DRAFT")
    credential_ref = Column(String(255), nullable=False, default="")
    character_id = Column(String(255))
    world_id = Column(String(255))
    series_id = Column(String(255))
    default_style_profile_id = Column(String(255))
    social_account_id = Column(String(255))
    activated_at = Column(DateTime)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        CheckConstraint("platform IN ('xiaohongshu','douyin','kuaishou','weixin_video','xianyu')", name="ck_meiti_platform_account_platform"),
        CheckConstraint("status IN ('DRAFT','ACTIVE','PAUSED','ARCHIVED')", name="ck_meiti_platform_account_status"),
        Index("idx_meiti_platform_accounts_platform", "platform"),
        Index("idx_meiti_platform_accounts_status", "status"),
    )


class VirtualCharacterRecord(Base):
    __tablename__ = "virtual_characters"

    character_id = Column(String(255), primary_key=True)
    account_id = Column(String(255), ForeignKey("platform_accounts.account_id", ondelete="CASCADE"), nullable=False)
    name = Column(Text, nullable=False)
    gender = Column(String(40), nullable=False, default="")
    age_range = Column(String(40), nullable=False, default="")
    appearance_profile = Column(JSONType, nullable=False, default=dict)
    body_profile = Column(JSONType, nullable=False, default=dict)
    face_profile = Column(JSONType, nullable=False, default=dict)
    hair_profile = Column(JSONType, nullable=False, default=dict)
    skin_profile = Column(JSONType, nullable=False, default=dict)
    clothing_profile = Column(JSONType, nullable=False, default=dict)
    personality_profile = Column(JSONType, nullable=False, default=dict)
    background_story = Column(Text, nullable=False, default="")
    speaking_style = Column(Text, nullable=False, default="")
    behavioral_traits = Column(JSONType, nullable=False, default=list)
    visual_identity_rules = Column(JSONType, nullable=False, default=dict)
    forbidden_changes = Column(JSONType, nullable=False, default=list)
    reference_asset_ids = Column(JSONType, nullable=False, default=list)
    derived_from_character_id = Column(String(255))
    occupation = Column(Text, nullable=False, default="")
    location = Column(Text, nullable=False, default="")
    values = Column(JSONType, nullable=False, default=list)
    behavior = Column(Text, nullable=False, default="")
    speech = Column(Text, nullable=False, default="")
    style = Column(JSONType, nullable=False, default=dict)
    accessories = Column(JSONType, nullable=False, default=list)
    photography = Column(Text, nullable=False, default="")
    lighting = Column(Text, nullable=False, default="")
    platform_personality = Column(Text, nullable=False, default="")
    content_behavior = Column(Text, nullable=False, default="")
    audience_relationship = Column(Text, nullable=False, default="")
    continuity_rules = Column(JSONType, nullable=False, default=dict)
    character_dna = Column(JSONType, nullable=False, default=dict)
    status = Column(String(40), nullable=False, default="ACTIVE")
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_meiti_virtual_characters_account", "account_id"),
    )


class AccountWorldRecord(Base):
    __tablename__ = "account_worlds"

    world_id = Column(String(255), primary_key=True)
    account_id = Column(String(255), ForeignKey("platform_accounts.account_id", ondelete="CASCADE"), nullable=False)
    name = Column(Text, nullable=False)
    world_description = Column(Text, nullable=False, default="")
    core_theme = Column(Text, nullable=False, default="")
    values = Column(JSONType, nullable=False, default=list)
    tone = Column(Text, nullable=False, default="")
    visual_language = Column(JSONType, nullable=False, default=dict)
    locations = Column(JSONType, nullable=False, default=list)
    daily_life_rules = Column(JSONType, nullable=False, default=list)
    story_rules = Column(JSONType, nullable=False, default=list)
    audience = Column(Text, nullable=False, default="")
    taboos = Column(JSONType, nullable=False, default=list)
    brand_rules = Column(JSONType, nullable=False, default=list)
    city = Column(Text, nullable=False, default="")
    season = Column(Text, nullable=False, default="")
    time_of_day = Column(Text, nullable=False, default="")
    lighting = Column(Text, nullable=False, default="")
    lifestyle = Column(Text, nullable=False, default="")
    social_relations = Column(JSONType, nullable=False, default=list)
    world_dna = Column(JSONType, nullable=False, default=dict)
    status = Column(String(40), nullable=False, default="ACTIVE")
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_meiti_account_worlds_account", "account_id"),
    )


class ContentSeriesRecord(Base):
    __tablename__ = "content_series"

    series_id = Column(String(255), primary_key=True)
    account_id = Column(String(255), ForeignKey("platform_accounts.account_id", ondelete="CASCADE"), nullable=False)
    world_id = Column(String(255), ForeignKey("account_worlds.world_id", ondelete="SET NULL"))
    name = Column(Text, nullable=False)
    description = Column(Text, nullable=False, default="")
    series_type = Column(String(80), nullable=False, default="serial")
    content_rules = Column(JSONType, nullable=False, default=dict)
    continuity_rules = Column(JSONType, nullable=False, default=dict)
    status = Column(String(40), nullable=False, default="ACTIVE")
    start_date = Column(String(40))
    end_date = Column(String(40))
    current_episode_no = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_meiti_content_series_account", "account_id"),
    )


class EpisodeRecord(Base):
    __tablename__ = "episodes"

    episode_id = Column(String(255), primary_key=True)
    series_id = Column(String(255), ForeignKey("content_series.series_id", ondelete="CASCADE"), nullable=False)
    account_id = Column(String(255), ForeignKey("platform_accounts.account_id", ondelete="CASCADE"), nullable=False)
    episode_no = Column(Integer, nullable=False)
    title = Column(Text, nullable=False, default="")
    brief = Column(Text, nullable=False, default="")
    previous_episode_id = Column(String(255))
    next_episode_id = Column(String(255))
    continuity_context = Column(JSONType, nullable=False, default=dict)
    character_state = Column(JSONType, nullable=False, default=dict)
    world_state = Column(JSONType, nullable=False, default=dict)
    location_state = Column(JSONType, nullable=False, default=dict)
    visual_state = Column(JSONType, nullable=False, default=dict)
    story_state = Column(JSONType, nullable=False, default=dict)
    content_status = Column(String(40), nullable=False, default="IDEA")
    campaign_id = Column(String(255))
    content_package_id = Column(String(255))
    primary_asset_id = Column(String(255))
    prompt_id = Column(String(255))
    character_revision = Column(Integer)
    world_revision = Column(Integer)
    production_run_id = Column(String(255))
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("series_id", "episode_no", name="uq_meiti_episode_no"),
        CheckConstraint(
            "content_status IN ('IDEA','BRIEFED','DRAFT','PROMPT_READY','AWAITING_CREATIVE','GENERATING','GENERATED','IMPORTED','QA_PASSED','QA_FAILED','PACKAGE_READY','HANDOFF_READY','READY_TO_PUBLISH','APPROVED','PUBLISHED','ANALYTICS_PENDING','LEARNED','FAILED','REJECTED','ARCHIVED')",
            name="ck_meiti_episode_status",
        ),
        Index("idx_meiti_episodes_series", "series_id"),
        Index("idx_meiti_episodes_account", "account_id"),
    )


class CreativeContextRecord(Base):
    __tablename__ = "creative_contexts"

    context_id = Column(String(255), primary_key=True)
    account_id = Column(String(255), ForeignKey("platform_accounts.account_id", ondelete="CASCADE"), nullable=False)
    platform = Column(String(120), nullable=False)
    character_id = Column(String(255))
    world_id = Column(String(255))
    series_id = Column(String(255))
    episode_id = Column(String(255))
    campaign_id = Column(String(255))
    user_request = Column(Text, nullable=False, default="")
    creative_request = Column(Text, nullable=False, default="")
    normalized_prompt = Column(Text, nullable=False, default="")
    system_constraints = Column(JSONType, nullable=False, default=dict)
    character_context = Column(JSONType, nullable=False, default=dict)
    world_context = Column(JSONType, nullable=False, default=dict)
    continuity_context = Column(JSONType, nullable=False, default=dict)
    platform_context = Column(JSONType, nullable=False, default=dict)
    generation_parameters = Column(JSONType, nullable=False, default=dict)
    provider = Column(String(120), nullable=False, default="")
    model = Column(String(120), nullable=False, default="")
    provider_task_id = Column(String(255), nullable=False, default="")
    resolved_target = Column(JSONType, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_meiti_creative_contexts_account", "account_id"),
        Index("idx_meiti_creative_contexts_episode", "episode_id"),
    )


class ContentRevisionRecord(Base):
    __tablename__ = "content_revisions"

    revision_id = Column(String(255), primary_key=True)
    content_package_id = Column(String(255), nullable=False)
    version = Column(Integer, nullable=False)
    parent_revision_id = Column(String(255))
    change_summary = Column(Text, nullable=False, default="")
    snapshot = Column(JSONType, nullable=False, default=dict)
    created_by = Column(String(120), nullable=False, default="meiti")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("content_package_id", "version", name="uq_meiti_content_revision"),
        Index("idx_meiti_content_revisions_package", "content_package_id"),
    )


class AccountMemoryRecord(Base):
    __tablename__ = "account_memories"

    memory_id = Column(String(255), primary_key=True)
    kind = Column(String(40), nullable=False, default="account")
    account_id = Column(String(255), ForeignKey("platform_accounts.account_id", ondelete="CASCADE"), nullable=False)
    subject_id = Column(String(255), nullable=False)
    key = Column(String(120), nullable=False)
    value = Column(JSONType, nullable=False, default=dict)
    source = Column(String(120), nullable=False, default="continuity")
    namespace = Column(String(80), nullable=False, default="account_memories")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (Index("idx_meiti_account_memories_account", "account_id"),)


class CharacterMemoryRecord(Base):
    __tablename__ = "character_memories"

    memory_id = Column(String(255), primary_key=True)
    kind = Column(String(40), nullable=False, default="character")
    account_id = Column(String(255), ForeignKey("platform_accounts.account_id", ondelete="CASCADE"), nullable=False)
    subject_id = Column(String(255), nullable=False)
    key = Column(String(120), nullable=False)
    value = Column(JSONType, nullable=False, default=dict)
    source = Column(String(120), nullable=False, default="continuity")
    namespace = Column(String(80), nullable=False, default="character_memories")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (Index("idx_meiti_character_memories_account", "account_id"),)


class WorldMemoryRecord(Base):
    __tablename__ = "world_memories"

    memory_id = Column(String(255), primary_key=True)
    kind = Column(String(40), nullable=False, default="world")
    account_id = Column(String(255), ForeignKey("platform_accounts.account_id", ondelete="CASCADE"), nullable=False)
    subject_id = Column(String(255), nullable=False)
    key = Column(String(120), nullable=False)
    value = Column(JSONType, nullable=False, default=dict)
    source = Column(String(120), nullable=False, default="continuity")
    namespace = Column(String(80), nullable=False, default="world_memories")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (Index("idx_meiti_world_memories_account", "account_id"),)


class SeriesMemoryRecord(Base):
    __tablename__ = "series_memories"

    memory_id = Column(String(255), primary_key=True)
    kind = Column(String(40), nullable=False, default="series")
    account_id = Column(String(255), ForeignKey("platform_accounts.account_id", ondelete="CASCADE"), nullable=False)
    subject_id = Column(String(255), nullable=False)
    key = Column(String(120), nullable=False)
    value = Column(JSONType, nullable=False, default=dict)
    source = Column(String(120), nullable=False, default="continuity")
    namespace = Column(String(80), nullable=False, default="series_memories")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (Index("idx_meiti_series_memories_account", "account_id"),)


class EpisodeMemoryRecord(Base):
    __tablename__ = "episode_memories"

    memory_id = Column(String(255), primary_key=True)
    kind = Column(String(40), nullable=False, default="episode")
    account_id = Column(String(255), ForeignKey("platform_accounts.account_id", ondelete="CASCADE"), nullable=False)
    subject_id = Column(String(255), nullable=False)
    key = Column(String(120), nullable=False)
    value = Column(JSONType, nullable=False, default=dict)
    source = Column(String(120), nullable=False, default="continuity")
    namespace = Column(String(80), nullable=False, default="episode_memories")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (Index("idx_meiti_episode_memories_account", "account_id"),)


ContinuityMemoryRecord = AccountMemoryRecord


class PerformanceFeedbackRecord(Base):
    __tablename__ = "performance_feedback"

    feedback_id = Column(String(255), primary_key=True)
    account_id = Column(String(255), ForeignKey("platform_accounts.account_id", ondelete="CASCADE"), nullable=False)
    platform = Column(String(120), nullable=False)
    content_package_id = Column(String(255), nullable=False, default="")
    episode_id = Column(String(255))
    topic = Column(Text, nullable=False, default="")
    hook = Column(Text, nullable=False, default="")
    visual_style = Column(Text, nullable=False, default="")
    caption_style = Column(Text, nullable=False, default="")
    duration = Column(Numeric(18, 6))
    scene = Column(Text, nullable=False, default="")
    action = Column(Text, nullable=False, default="")
    audio = Column(Text, nullable=False, default="")
    engagement = Column(JSONType, nullable=False, default=dict)
    retention = Column(JSONType, nullable=False, default=dict)
    publication_id = Column(String(255), nullable=False, default="")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_meiti_performance_feedback_account", "account_id"),
        Index("idx_meiti_performance_feedback_platform", "platform"),
    )


class AssetLineageRecord(Base):
    __tablename__ = "asset_lineage"

    lineage_id = Column(String(255), primary_key=True)
    asset_id = Column(String(255), nullable=False)
    account_id = Column(String(255), ForeignKey("platform_accounts.account_id", ondelete="CASCADE"), nullable=False)
    series_id = Column(String(255))
    episode_id = Column(String(255))
    content_package_id = Column(String(255))
    creative_context_id = Column(String(255))
    character_id = Column(String(255))
    world_id = Column(String(255))
    user_request = Column(Text, nullable=False, default="")
    generation_request = Column(JSONType, nullable=False, default=dict)
    provider = Column(String(120), nullable=False, default="")
    provider_task_id = Column(String(255), nullable=False, default="")
    model = Column(String(120), nullable=False, default="")
    attempt_no = Column(Integer, nullable=False, default=1)
    parent_asset_id = Column(String(255), nullable=False, default="")
    qa_decision = Column(String(40), nullable=False, default="")
    published = Column(Boolean, nullable=False, default=False)
    selected_for_package = Column(Boolean, nullable=False, default=False)
    source_asset_id = Column(String(255))
    workflow_id = Column(String(255))
    reference_asset_ids = Column(JSONType, nullable=False, default=list)
    origin_episode_id = Column(String(255))
    target_episode_id = Column(String(255))
    origin_platform = Column(String(120), nullable=False, default="")
    target_platform = Column(String(120), nullable=False, default="")
    reuse_mode = Column(String(40), nullable=False, default="NONE")
    generation_mode = Column(String(80), nullable=False, default="")
    tool = Column(String(80), nullable=False, default="")
    prompt_id = Column(String(255))
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("account_id", "episode_id", "parent_asset_id", "attempt_no", name="uq_meiti_lineage_attempt"),
        Index("idx_meiti_asset_lineage_asset", "asset_id"),
        Index("idx_meiti_asset_lineage_account", "account_id"),
        Index("idx_meiti_asset_lineage_episode", "episode_id"),
    )


class AccountSelectionRecord(Base):
    """Single current account selection. ACTIVE is not exclusive."""

    __tablename__ = "account_selections"

    selection_key = Column(String(80), primary_key=True)
    account_id = Column(String(255), ForeignKey("platform_accounts.account_id", ondelete="CASCADE"), nullable=False)
    platform = Column(String(120), nullable=False)
    reason = Column(String(80), nullable=False, default="explicit")
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_meiti_account_selections_account", "account_id"),
        Index("idx_meiti_account_selections_platform", "platform"),
    )


class KnowledgeDocumentRecord(Base):
    """PostgreSQL index for Obsidian knowledge documents. Not a second brain."""

    __tablename__ = "knowledge_documents"

    document_id = Column(String(255), primary_key=True)
    scope_type = Column(String(40), nullable=False)
    scope_id = Column(String(255))
    account_id = Column(String(255))
    platform = Column(String(120), nullable=False, default="")
    source_type = Column(String(80), nullable=False, default="obsidian")
    title = Column(Text, nullable=False)
    path = Column(Text, nullable=False, default="")
    content = Column(Text, nullable=False, default="")
    tags = Column(JSONType, nullable=False, default=list)
    version = Column(Integer, nullable=False, default=1)
    status = Column(String(40), nullable=False, default="ACTIVE")
    content_hash = Column(String(64), nullable=False)
    character_id = Column(String(255))
    world_id = Column(String(255))
    series_id = Column(String(255))
    episode_id = Column(String(255))
    publication_id = Column(String(255))
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_meiti_knowledge_documents_account", "account_id"),
        Index("idx_meiti_knowledge_documents_scope", "scope_type", "scope_id"),
        Index("idx_meiti_knowledge_documents_hash", "content_hash"),
        Index("idx_meiti_knowledge_documents_platform", "platform"),
    )


class PlatformAssetPoolRecord(Base):
    __tablename__ = "platform_asset_pools"

    pool_id = Column(String(255), primary_key=True)
    account_id = Column(String(255), ForeignKey("platform_accounts.account_id", ondelete="CASCADE"), nullable=False)
    platform = Column(String(120), nullable=False)
    character_id = Column(String(255))
    world_id = Column(String(255))
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("account_id", "platform", name="uq_meiti_platform_asset_pool"),
        Index("idx_meiti_platform_asset_pools_account", "account_id"),
        Index("idx_meiti_platform_asset_pools_platform", "platform"),
    )


class PlatformCreativeDNARecord(Base):
    __tablename__ = "platform_creative_dna"

    dna_id = Column(String(255), primary_key=True)
    account_id = Column(String(255), ForeignKey("platform_accounts.account_id", ondelete="CASCADE"), nullable=False)
    platform = Column(String(120), nullable=False)
    visual_style = Column(JSONType, nullable=False, default=dict)
    copy_style = Column(JSONType, nullable=False, default=dict)
    hook_style = Column(Text, nullable=False, default="")
    camera_style = Column(Text, nullable=False, default="")
    motion_style = Column(Text, nullable=False, default="")
    emotion_style = Column(Text, nullable=False, default="")
    audience_relationship = Column(Text, nullable=False, default="")
    cta_style = Column(Text, nullable=False, default="")
    content_frequency = Column(Text, nullable=False, default="")
    asset_freshness_policy = Column(String(80), nullable=False, default="NEW_PRIMARY_ASSET_REQUIRED")
    prompt_dna = Column(JSONType, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("account_id", "platform", name="uq_meiti_platform_creative_dna"),
        Index("idx_meiti_platform_creative_dna_account", "account_id"),
    )


class PromptPackageRecord(Base):
    __tablename__ = "prompt_packages"

    prompt_id = Column(String(255), primary_key=True)
    account_id = Column(String(255), ForeignKey("platform_accounts.account_id", ondelete="CASCADE"), nullable=False)
    platform = Column(String(120), nullable=False)
    kind = Column(String(40), nullable=False, default="IMAGE")
    character_id = Column(String(255))
    world_id = Column(String(255))
    series_id = Column(String(255))
    episode_id = Column(String(255))
    character_lock = Column(Text, nullable=False, default="")
    world_lock = Column(Text, nullable=False, default="")
    scene_prompt = Column(Text, nullable=False, default="")
    visual_style = Column(Text, nullable=False, default="")
    camera = Column(Text, nullable=False, default="")
    motion = Column(Text, nullable=False, default="")
    composition = Column(Text, nullable=False, default="")
    lighting = Column(Text, nullable=False, default="")
    negative_prompt = Column(Text, nullable=False, default="")
    lens = Column(Text, nullable=False, default="")
    material_texture = Column(Text, nullable=False, default="")
    authenticity = Column(Text, nullable=False, default="")
    shot_list = Column(JSONType, nullable=False, default=list)
    temporal_sequence = Column(Text, nullable=False, default="")
    camera_movement = Column(Text, nullable=False, default="")
    character_motion = Column(Text, nullable=False, default="")
    environment_motion = Column(Text, nullable=False, default="")
    start_state = Column(Text, nullable=False, default="")
    end_state = Column(Text, nullable=False, default="")
    duration = Column(Text, nullable=False, default="")
    aspect_ratio = Column(Text, nullable=False, default="")
    copy_ready = Column(Text, nullable=False, default="")
    reference_assets = Column(JSONType, nullable=False, default=list)
    source_assets = Column(JSONType, nullable=False, default=list)
    source_asset_id = Column(String(255))
    recommended_model = Column(Text, nullable=False, default="")
    recommended_size = Column(Text, nullable=False, default="")
    recommended_ratio = Column(Text, nullable=False, default="")
    recommended_duration = Column(Text, nullable=False, default="")
    learning_basis = Column(JSONType, nullable=False, default=list)
    prompt_patterns = Column(JSONType, nullable=False, default=list)
    lechuang_parameters = Column(JSONType, nullable=False, default=dict)
    prompt_hash = Column(String(64), nullable=False, default="")
    version = Column(Integer, nullable=False, default=1)
    parent_prompt_id = Column(String(255))
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_meiti_prompt_packages_account", "account_id"),
        Index("idx_meiti_prompt_packages_episode", "episode_id"),
        Index("idx_meiti_prompt_packages_platform", "platform"),
    )


class PromptPatternRecord(Base):
    __tablename__ = "prompt_patterns"

    pattern_id = Column(String(255), primary_key=True)
    platform = Column(String(120), nullable=False)
    account_id = Column(String(255))
    category = Column(String(120), nullable=False, default="")
    prompt_fragment = Column(Text, nullable=False, default="")
    positive_count = Column(Integer, nullable=False, default=0)
    negative_count = Column(Integer, nullable=False, default=0)
    confidence = Column(Numeric(18, 6), nullable=False, default=0)
    source_episode_ids = Column(JSONType, nullable=False, default=list)
    global_pattern = Column(Boolean, nullable=False, default=False)
    promotion_status = Column(String(40), nullable=False, default="PLATFORM")
    sample_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_meiti_prompt_patterns_platform", "platform"),
        Index("idx_meiti_prompt_patterns_account", "account_id"),
    )


class PlatformLearningProfileRecord(Base):
    __tablename__ = "platform_learning_profiles"

    profile_id = Column(String(255), primary_key=True)
    account_id = Column(String(255), ForeignKey("platform_accounts.account_id", ondelete="CASCADE"), nullable=False)
    platform = Column(String(120), nullable=False)
    successful_patterns = Column(JSONType, nullable=False, default=list)
    failed_patterns = Column(JSONType, nullable=False, default=list)
    high_performance_topics = Column(JSONType, nullable=False, default=list)
    high_performance_hooks = Column(JSONType, nullable=False, default=list)
    high_performance_visuals = Column(JSONType, nullable=False, default=list)
    audience_preferences = Column(JSONType, nullable=False, default=list)
    avoid_patterns = Column(JSONType, nullable=False, default=list)
    prompt_patterns = Column(JSONType, nullable=False, default=list)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("account_id", "platform", name="uq_meiti_platform_learning_profile"),
        Index("idx_meiti_platform_learning_profiles_account", "account_id"),
        Index("idx_meiti_platform_learning_profiles_platform", "platform"),
    )


class ContentPackageAssetRecord(Base):
    __tablename__ = "content_package_assets"

    mapping_id = Column(String(255), primary_key=True)
    package_id = Column(String(255), nullable=False)
    asset_id = Column(String(255), nullable=False)
    role = Column(String(40), nullable=False, default="PRIMARY")
    selected = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("package_id", "asset_id", "role", name="uq_meiti_package_asset_role"),
        Index("idx_meiti_content_package_assets_package", "package_id"),
        Index("idx_meiti_content_package_assets_asset", "asset_id"),
        CheckConstraint("role IN ('PRIMARY','COVER','THUMBNAIL','REFERENCE')", name="ck_meiti_package_asset_role"),
    )


class ProductionRunRecord(Base):
    __tablename__ = "production_runs"

    run_id = Column(String(255), primary_key=True)
    account_id = Column(String(255), ForeignKey("platform_accounts.account_id", ondelete="CASCADE"), nullable=False)
    platform = Column(String(120), nullable=False)
    episode_id = Column(String(255))
    prompt_id = Column(String(255))
    asset_id = Column(String(255))
    package_id = Column(String(255))
    handoff_id = Column(String(255))
    publication_id = Column(String(255))
    analytics_id = Column(String(255))
    learning_id = Column(String(255))
    task_id = Column(String(255))
    status = Column(String(40), nullable=False, default="CREATED")
    request = Column(Text, nullable=False, default="")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_meiti_production_runs_account", "account_id"),
        Index("idx_meiti_production_runs_episode", "episode_id"),
        CheckConstraint(
            "status IN ("
            "'CREATED','PROMPT_READY','CREATIVE_EXECUTION','ASSET_IMPORTED','QA_PASSED',"
            "'PACKAGE_READY','HANDED_OFF','PUBLISHED','ANALYTICS_CAPTURED','LEARNING_VERIFIED',"
            "'CLOSED','BLOCKED','OPEN','AWAITING_CREATIVE','IMPORTED','PACKAGED','LEARNED'"
            ")",
            name="ck_meiti_production_run_status",
        ),
    )


class ProductionEvidenceRecord(Base):
    __tablename__ = "production_evidence"

    evidence_id = Column(String(255), primary_key=True)
    kind = Column(String(80), nullable=False)
    account_id = Column(String(255), ForeignKey("platform_accounts.account_id", ondelete="CASCADE"), nullable=False)
    platform = Column(String(120), nullable=False)
    status = Column(String(40), nullable=False, default="PASS")
    episode_id = Column(String(255))
    prompt_id = Column(String(255))
    asset_id = Column(String(255))
    package_id = Column(String(255))
    handoff_id = Column(String(255))
    publication_id = Column(String(255))
    analytics_id = Column(String(255))
    learning_id = Column(String(255))
    production_run_id = Column(String(255))
    source = Column(String(40), nullable=False, default="operator")
    detail = Column(JSONType, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_meiti_production_evidence_account", "account_id"),
        Index("idx_meiti_production_evidence_episode", "episode_id"),
        Index("idx_meiti_production_evidence_kind", "kind"),
        Index("idx_meiti_production_evidence_run", "production_run_id"),
    )


class AnalyticsRecordRow(Base):
    __tablename__ = "analytics_records"

    analytics_id = Column(String(255), primary_key=True)
    account_id = Column(String(255), ForeignKey("platform_accounts.account_id", ondelete="CASCADE"), nullable=False)
    platform = Column(String(120), nullable=False)
    episode_id = Column(String(255))
    package_id = Column(String(255))
    handoff_id = Column(String(255))
    publication_id = Column(String(255))
    impressions = Column(Integer)
    likes = Column(Integer)
    favorites = Column(Integer)
    comments = Column(Integer)
    shares = Column(Integer)
    clicks = Column(Integer)
    followers_gained = Column(Integer)
    followers_delta = Column(Integer)
    published_at = Column(String(80))
    observed_at = Column(String(80))
    topic = Column(Text, nullable=False, default="")
    cover = Column(Text, nullable=False, default="")
    prompt_pattern = Column(Text, nullable=False, default="")
    source = Column(String(40), nullable=False, default="manual")
    origin = Column(String(40), nullable=False, default="MANUAL")
    verification_status = Column(String(40), nullable=False, default="UNVERIFIED")
    provider = Column(String(120), nullable=False, default="")
    provider_payload = Column(JSONType, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_meiti_analytics_records_account", "account_id"),
        Index("idx_meiti_analytics_records_episode", "episode_id"),
        Index("uq_meiti_analytics_observation", "publication_id", "observed_at", unique=True),
        CheckConstraint("origin IN ('MANUAL','PROVIDER')", name="ck_meiti_analytics_origin"),
        CheckConstraint("verification_status IN ('VERIFIED','UNVERIFIED')", name="ck_meiti_analytics_verification"),
    )


class LearningRecordRow(Base):
    __tablename__ = "learning_records"

    learning_id = Column(String(255), primary_key=True)
    account_id = Column(String(255), ForeignKey("platform_accounts.account_id", ondelete="CASCADE"), nullable=False)
    platform = Column(String(120), nullable=False)
    episode_id = Column(String(255))
    analytics_id = Column(String(255))
    prompt_id = Column(String(255))
    asset_id = Column(String(255))
    pattern_ids = Column(JSONType, nullable=False, default=list)
    what_worked = Column(Text, nullable=False, default="")
    what_failed = Column(Text, nullable=False, default="")
    visual_learning = Column(Text, nullable=False, default="")
    content_learning = Column(Text, nullable=False, default="")
    prompt_learning = Column(Text, nullable=False, default="")
    audience_learning = Column(Text, nullable=False, default="")
    next_recommendation = Column(Text, nullable=False, default="")
    reason = Column(Text, nullable=False, default="")
    source_episode_ids = Column(JSONType, nullable=False, default=list)
    evidence_status = Column(String(40), nullable=False, default="NOT_VERIFIED")
    failure_type = Column(Text, nullable=False, default="")
    diagnosis = Column(Text, nullable=False, default="")
    root_cause = Column(Text, nullable=False, default="")
    evidence_gap = Column(Text, nullable=False, default="")
    outcome = Column(Text, nullable=False, default="")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_meiti_learning_records_account", "account_id"),
        Index("idx_meiti_learning_records_platform", "platform"),
        CheckConstraint(
            "evidence_status IN ('VERIFIED','NOT_ENOUGH_EVIDENCE','NOT_VERIFIED')",
            name="ck_meiti_learning_evidence_status",
        ),
    )


class CreativeExecutionReceiptRecord(Base):
    __tablename__ = "creative_execution_receipts"

    receipt_id = Column(String(255), primary_key=True)
    asset_id = Column(String(255), nullable=False)
    prompt_id = Column(String(255))
    tool = Column(String(80), nullable=False, default="lechuang")
    model = Column(String(120), nullable=False, default="UNKNOWN")
    generated_at = Column(DateTime)
    operator = Column(String(120), nullable=False, default="operator")
    source_asset_id = Column(String(255))
    generation_mode = Column(String(80), nullable=False, default="MANUAL_CREATIVE_TOOL")
    production_run_id = Column(String(255))
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_meiti_creative_receipts_asset", "asset_id"),
        Index("idx_meiti_creative_receipts_prompt", "prompt_id"),
        Index("idx_meiti_creative_receipts_run", "production_run_id"),
    )


class CharacterRevisionRecord(Base):
    __tablename__ = "character_revisions"

    revision_id = Column(String(255), primary_key=True)
    character_id = Column(String(255), nullable=False)
    account_id = Column(String(255), ForeignKey("platform_accounts.account_id", ondelete="CASCADE"), nullable=False)
    version = Column(Integer, nullable=False)
    snapshot = Column(JSONType, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("character_id", "version", name="uq_meiti_character_revision"),
        Index("idx_meiti_character_revisions_character", "character_id"),
    )


class WorldRevisionRecord(Base):
    __tablename__ = "world_revisions"

    revision_id = Column(String(255), primary_key=True)
    world_id = Column(String(255), nullable=False)
    account_id = Column(String(255), ForeignKey("platform_accounts.account_id", ondelete="CASCADE"), nullable=False)
    version = Column(Integer, nullable=False)
    snapshot = Column(JSONType, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("world_id", "version", name="uq_meiti_world_revision"),
        Index("idx_meiti_world_revisions_world", "world_id"),
    )


class AssetReferenceSnapshotRecord(Base):
    __tablename__ = "asset_reference_snapshots"

    snapshot_id = Column(String(255), primary_key=True)
    prompt_id = Column(String(255), nullable=False)
    asset_id = Column(String(255), nullable=False)
    role = Column(String(40), nullable=False, default="SCENE_REFERENCE")
    reason = Column(Text, nullable=False, default="")
    prompt_influence = Column(Text, nullable=False, default="")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_meiti_asset_reference_snapshots_prompt", "prompt_id"),
        Index("idx_meiti_asset_reference_snapshots_asset", "asset_id"),
        UniqueConstraint("prompt_id", "asset_id", "role", name="uq_meiti_asset_reference_snapshot"),
    )


class PatternPromotionRecord(Base):
    __tablename__ = "pattern_promotions"

    promotion_id = Column(String(255), primary_key=True)
    pattern_id = Column(String(255), nullable=False)
    platform = Column(String(120), nullable=False)
    status = Column(String(40), nullable=False, default="PLATFORM")
    sample_count = Column(Integer, nullable=False, default=0)
    cross_platform_evidence = Column(JSONType, nullable=False, default=list)
    confidence = Column(Numeric(18, 6), nullable=False, default=0)
    reason = Column(Text, nullable=False, default="")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_meiti_pattern_promotions_pattern", "pattern_id"),
        Index("idx_meiti_pattern_promotions_platform", "platform"),
    )


class LifecycleTransitionRecord(Base):
    __tablename__ = "lifecycle_transitions"

    transition_id = Column(String(255), primary_key=True)
    episode_id = Column(String(255), nullable=False)
    account_id = Column(String(255), ForeignKey("platform_accounts.account_id", ondelete="CASCADE"), nullable=False)
    from_status = Column(String(40), nullable=False)
    to_status = Column(String(40), nullable=False)
    owner = Column(String(80), nullable=False)
    evidence_id = Column(String(255))
    task_id = Column(String(255))
    reason = Column(Text, nullable=False, default="")
    operator = Column(String(120), nullable=False, default="")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_meiti_lifecycle_transitions_episode", "episode_id"),
        Index("idx_meiti_lifecycle_transitions_account", "account_id"),
        Index("idx_meiti_lifecycle_transitions_task", "task_id"),
    )


class AccountProfileRecord(Base):
    __tablename__ = "account_profiles"

    account_id = Column(String(255), ForeignKey("platform_accounts.account_id", ondelete="CASCADE"), primary_key=True)
    platform = Column(String(120), nullable=False)
    display_name = Column(Text, nullable=False, default="")
    external_account_id = Column(String(255), nullable=False, default="")
    status = Column(String(40), nullable=False, default="DRAFT")
    character_id = Column(String(255))
    world_id = Column(String(255))
    series_id = Column(String(255))
    account_objective = Column(JSONType, nullable=False, default=dict)
    target_audience = Column(JSONType, nullable=False, default=dict)
    positioning = Column(JSONType, nullable=False, default=dict)
    content_pillars = Column(JSONType, nullable=False, default=dict)
    brand_voice = Column(JSONType, nullable=False, default=dict)
    visual_style = Column(JSONType, nullable=False, default=dict)
    content_frequency = Column(JSONType, nullable=False, default=dict)
    preferred_publish_windows = Column(JSONType, nullable=False, default=dict)
    content_formats = Column(JSONType, nullable=False, default=dict)
    operating_rules = Column(JSONType, nullable=False, default=dict)
    forbidden_rules = Column(JSONType, nullable=False, default=dict)
    manual_notes = Column(JSONType, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_meiti_account_profiles_platform", "platform"),
    )


class AccountOperatingStateRecord(Base):
    __tablename__ = "account_operating_states"

    account_id = Column(String(255), ForeignKey("platform_accounts.account_id", ondelete="CASCADE"), primary_key=True)
    platform = Column(String(120), nullable=False)
    current_objective = Column(Text, nullable=False, default="")
    current_priority = Column(String(20), nullable=False, default="NORMAL")
    current_series = Column(String(255))
    current_episode = Column(String(255))
    current_task = Column(String(255))
    current_campaign = Column(String(255))
    current_strategy = Column(Text, nullable=False, default="")
    current_content_status = Column(String(40), nullable=False, default="IDEA")
    last_published_episode = Column(String(255))
    last_generated_asset = Column(String(255))
    last_learning = Column(String(255))
    learning_summary = Column(Text, nullable=False, default="")
    next_action = Column(Text, nullable=False, default="")
    next_due_at = Column(String(80))
    paused_until = Column(String(80))
    operator_notes = Column(Text, nullable=False, default="")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_meiti_account_operating_states_platform", "platform"),
        Index("idx_meiti_account_operating_states_task", "current_task"),
    )


class ManualOverrideRecord(Base):
    __tablename__ = "manual_overrides"

    override_id = Column(String(255), primary_key=True)
    account_id = Column(String(255), ForeignKey("platform_accounts.account_id", ondelete="CASCADE"), nullable=False)
    platform = Column(String(120), nullable=False)
    target_kind = Column(String(40), nullable=False)
    target_id = Column(String(255), nullable=False)
    field_name = Column(String(80), nullable=False)
    old_value = Column(JSONType, nullable=False, default=dict)
    new_value = Column(JSONType, nullable=False, default=dict)
    changed_by = Column(String(120), nullable=False, default="operator")
    reason = Column(Text, nullable=False, default="")
    source = Column(String(40), nullable=False, default="USER_OVERRIDE")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_meiti_manual_overrides_account", "account_id"),
        Index("idx_meiti_manual_overrides_target", "target_kind", "target_id"),
    )


class CreatorTaskRecord(Base):
    __tablename__ = "creator_tasks"

    task_id = Column(String(255), primary_key=True)
    account_id = Column(String(255), ForeignKey("platform_accounts.account_id", ondelete="CASCADE"), nullable=False)
    platform = Column(String(120), nullable=False)
    task_type = Column(String(40), nullable=False)
    title = Column(Text, nullable=False)
    description = Column(Text, nullable=False, default="")
    priority = Column(String(20), nullable=False, default="NORMAL")
    status = Column(String(40), nullable=False, default="TODO")
    due_at = Column(String(80))
    episode_id = Column(String(255))
    series_id = Column(String(255))
    prompt_id = Column(String(255))
    asset_id = Column(String(255))
    package_id = Column(String(255))
    production_run_id = Column(String(255))
    parent_task_id = Column(String(255))
    next_task_id = Column(String(255))
    next_task_type = Column(String(40))
    dependencies = Column(JSONType, nullable=False, default=list)
    operator_notes = Column(Text, nullable=False, default="")
    blocked_reason = Column(Text, nullable=False, default="")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime)

    __table_args__ = (
        CheckConstraint(
            "task_type IN ('ACCOUNT_SETUP','ACCOUNT_MAINTENANCE','CONTENT_IDEA','CONTENT_PLAN','PROMPT_GENERATION','CREATIVE_EXECUTION','ASSET_IMPORT','QA','PACKAGE','HANDOFF','PUBLISH','ANALYTICS','LEARNING','RESEARCH','REVIEW')",
            name="ck_meiti_creator_task_type",
        ),
        CheckConstraint(
            "status IN ('TODO','READY','IN_PROGRESS','WAITING_OPERATOR','WAITING_EXTERNAL','BLOCKED','DONE','CANCELLED')",
            name="ck_meiti_creator_task_status",
        ),
        CheckConstraint("priority IN ('CRITICAL','HIGH','NORMAL','LOW')", name="ck_meiti_creator_task_priority"),
        Index("idx_meiti_creator_tasks_account", "account_id"),
        Index("idx_meiti_creator_tasks_status", "status"),
        Index("idx_meiti_creator_tasks_due", "due_at"),
        Index("idx_meiti_creator_tasks_episode", "episode_id"),
    )


class ContentCalendarRecord(Base):
    __tablename__ = "content_calendar"

    calendar_id = Column(String(255), primary_key=True)
    account_id = Column(String(255), ForeignKey("platform_accounts.account_id", ondelete="CASCADE"), nullable=False)
    platform = Column(String(120), nullable=False)
    date = Column(String(40), nullable=False)
    slot = Column(String(40), nullable=False, default="default")
    episode_id = Column(String(255))
    task_id = Column(String(255))
    status = Column(String(40), nullable=False, default="PLANNED")
    topic = Column(Text, nullable=False, default="")
    format = Column(String(40), nullable=False, default="image")
    priority = Column(String(20), nullable=False, default="NORMAL")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("account_id", "date", "slot", name="uq_meiti_content_calendar_slot"),
        CheckConstraint(
            "status IN ('PLANNED','READY','PRODUCING','READY_TO_PUBLISH','PUBLISHED','MISSED','CANCELLED')",
            name="ck_meiti_content_calendar_status",
        ),
        Index("idx_meiti_content_calendar_account", "account_id"),
        Index("idx_meiti_content_calendar_date", "date"),
    )


class ProductionReadinessRecordRow(Base):
    __tablename__ = "production_readiness_records"

    record_id = Column(String(255), primary_key=True)
    account_id = Column(String(255))
    platform = Column(String(120), nullable=False, default="")
    core_production = Column(String(40), nullable=False, default="NOT_CONFIGURED")
    post_production = Column(String(40), nullable=False, default="NOT_VERIFIED")
    full_loop = Column(String(40), nullable=False, default="NOT_VERIFIED")
    checks = Column(JSONType, nullable=False, default=dict)
    detail = Column(JSONType, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_meiti_production_readiness_account", "account_id"),
    )

