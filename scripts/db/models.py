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
    success_metrics = Column(JSONB, nullable=False, default=list)
    status = Column(String(40), nullable=False, default="draft")
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
    evidence_ids = Column(JSONB, nullable=False, default=list)
    media_assets = Column(JSONB, nullable=False, default=list)
    commerce_intent = Column(String(120), nullable=False, default="none")
    variants = Column(JSONB, nullable=False, default=list)
    metadata_json = Column("metadata", JSONB, nullable=False, default=dict)
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
    media = Column(JSONB, nullable=False, default=list)
    settings = Column(JSONB, nullable=False, default=dict)
    platform_metadata = Column(JSONB, nullable=False, default=dict)
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
    capabilities = Column(JSONB, nullable=False, default=dict)
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
            "status IN ('PENDING','AUTHENTICATING','AUTHENTICATED','VERIFYING','VERIFIED','ENABLED','DEGRADED','EXPIRED','REVOKED','BLOCKED','TARGET_ONLY','HANDOFF_READY','IDENTITY_UNVERIFIED')",
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
    distribution_job_id = Column(String(255), nullable=False, default="")
    package = Column(JSONB, nullable=False, default=dict)
    expires_at = Column(DateTime)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        CheckConstraint(
            "status IN ('READY_FOR_XHS','OPENED','SUBMITTED','PUBLISHED','EXPIRED','CANCELLED')",
            name="ck_meiti_social_handoff_status",
        ),
        Index("idx_meiti_social_handoffs_account", "account_id"),
        Index("idx_meiti_social_handoffs_job", "distribution_job_id"),
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
    capabilities = Column(JSONB, nullable=False, default=dict)
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
    variant = Column(JSONB, nullable=False, default=dict)
    scheduled_at = Column(DateTime)
    last_attempt_at = Column(DateTime)
    attempt_count = Column(Integer, nullable=False, default=0)
    error_code = Column(String(120))
    error_message = Column(Text)
    provider_response = Column(JSONB)
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
            "status IN ('DRAFT','VALIDATING','BLOCKED','READY','SUBMITTING','SUBMITTED','SCHEDULED','PUBLISHING','PUBLISHED','FAILED','RETRYING','CANCELLED','UNKNOWN','FAILED_PERMANENT','RECONCILING')",
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
    response_summary = Column(JSONB)
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
    provider = Column(String(120), nullable=False)
    integration_id = Column(String(255), nullable=False, default="")
    remote_media_id = Column(String(255), nullable=False)
    remote_media_path = Column(Text, nullable=False)
    status = Column(String(40), nullable=False, default="uploaded")
    uploaded_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

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
    media_assets = Column(JSONB, nullable=False, default=list)
    status = Column(String(40), nullable=False, default="DRAFT")
    provider_response = Column(JSONB, nullable=False, default=dict)
    quantity = Column(Integer, nullable=False, default=1)
    content_package_id = Column(String(255), nullable=False, default="")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_meiti_xianyu_listings_account", "account_id"),
        Index("idx_meiti_xianyu_listings_status", "status"),
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
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_media_assets_run", "creative_run_id"),
        Index("idx_media_assets_type", "type"),
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

