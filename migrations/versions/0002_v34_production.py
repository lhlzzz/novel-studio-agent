"""Add first-class V3.4 production records and constraints."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002_v34_production"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None

JSONB = postgresql.JSONB


def upgrade() -> None:
    op.create_table(
        "campaigns",
        sa.Column("campaign_id", sa.String(255), primary_key=True),
        sa.Column("brand_id", sa.String(255), nullable=False, server_default=""),
        sa.Column("creator_id", sa.String(255), nullable=False, server_default=""),
        sa.Column("objective", sa.Text(), nullable=False),
        sa.Column("audience", sa.Text(), nullable=False, server_default=""),
        sa.Column("strategy_id", sa.String(255)),
        sa.Column("start_at", sa.DateTime()),
        sa.Column("end_at", sa.DateTime()),
        sa.Column("success_metrics", JSONB, nullable=False, server_default="[]"),
        sa.Column("status", sa.String(40), nullable=False, server_default="draft"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_table(
        "content_packages",
        sa.Column("package_id", sa.String(255), primary_key=True),
        sa.Column("brand_id", sa.String(255)),
        sa.Column("creator_id", sa.String(255)),
        sa.Column("campaign_id", sa.String(255), sa.ForeignKey("campaigns.campaign_id", ondelete="SET NULL")),
        sa.Column("topic", sa.Text(), nullable=False, server_default=""),
        sa.Column("content_pillar", sa.String(255), nullable=False, server_default=""),
        sa.Column("hook", sa.Text(), nullable=False, server_default=""),
        sa.Column("format", sa.String(80), nullable=False, server_default="post"),
        sa.Column("audience", sa.Text(), nullable=False, server_default=""),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("caption", sa.Text(), nullable=False, server_default=""),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("evidence_ids", JSONB, nullable=False, server_default="[]"),
        sa.Column("media_assets", JSONB, nullable=False, server_default="[]"),
        sa.Column("commerce_intent", sa.String(120), nullable=False, server_default="none"),
        sa.Column("variants", JSONB, nullable=False, server_default="[]"),
        sa.Column("metadata", JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_table(
        "content_variants",
        sa.Column("variant_id", sa.String(255), primary_key=True),
        sa.Column("package_id", sa.String(255), sa.ForeignKey("content_packages.package_id", ondelete="CASCADE"), nullable=False),
        sa.Column("integration_id", sa.String(255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False, server_default=""),
        sa.Column("title", sa.Text(), nullable=False, server_default=""),
        sa.Column("caption", sa.Text(), nullable=False, server_default=""),
        sa.Column("media", JSONB, nullable=False, server_default="[]"),
        sa.Column("settings", JSONB, nullable=False, server_default="{}"),
        sa.Column("platform_metadata", JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint("package_id", "integration_id", name="uq_meiti_content_variant_target"),
    )
    op.create_index("idx_meiti_content_variants_package", "content_variants", ["package_id"])
    op.create_table(
        "integrations",
        sa.Column("integration_id", sa.String(255), primary_key=True),
        sa.Column("provider", sa.String(120), nullable=False),
        sa.Column("platform", sa.String(120), nullable=False, server_default=""),
        sa.Column("account_id", sa.String(255), nullable=False, server_default=""),
        sa.Column("account_name", sa.Text(), nullable=False, server_default=""),
        sa.Column("region", sa.String(80), nullable=False, server_default="global"),
        sa.Column("state", sa.String(40), nullable=False, server_default="REGISTERED"),
        sa.Column("enabled", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("capabilities", JSONB, nullable=False, server_default="{}"),
        sa.Column("verified_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.CheckConstraint("enabled IN (0, 1)", name="ck_meiti_integrations_enabled"),
    )
    op.create_index("idx_meiti_integrations_provider", "integrations", ["provider"])
    op.create_index("idx_meiti_integrations_state", "integrations", ["state"])
    op.create_table(
        "distribution_jobs",
        sa.Column("job_id", sa.String(255), primary_key=True),
        sa.Column("content_package_id", sa.String(255), sa.ForeignKey("content_packages.package_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("integration_id", sa.String(255), sa.ForeignKey("integrations.integration_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("action", sa.String(40), nullable=False, server_default="publish"),
        sa.Column("status", sa.String(40), nullable=False, server_default="DRAFT"),
        sa.Column("idempotency_key", sa.String(255), nullable=False, unique=True),
        sa.Column("variant", JSONB, nullable=False, server_default="{}"),
        sa.Column("scheduled_at", sa.DateTime()),
        sa.Column("last_attempt_at", sa.DateTime()),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_code", sa.String(120)),
        sa.Column("error_message", sa.Text()),
        sa.Column("provider_response", JSONB),
        sa.Column("brand_id", sa.String(255)),
        sa.Column("creator_id", sa.String(255)),
        sa.Column("campaign_id", sa.String(255)),
        sa.Column("request_id", sa.String(255), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.CheckConstraint("status IN ('DRAFT','VALIDATING','BLOCKED','READY','SUBMITTING','SUBMITTED','SCHEDULED','PUBLISHING','PUBLISHED','FAILED','RETRYING','CANCELLED','UNKNOWN','FAILED_PERMANENT')", name="ck_meiti_distribution_job_status"),
    )
    op.create_index("idx_meiti_distribution_jobs_status", "distribution_jobs", ["status"])
    op.create_index("idx_meiti_distribution_jobs_schedule", "distribution_jobs", ["scheduled_at"])
    op.create_table(
        "distribution_attempts",
        sa.Column("attempt_id", sa.String(255), primary_key=True),
        sa.Column("distribution_job_id", sa.String(255), sa.ForeignKey("distribution_jobs.job_id", ondelete="CASCADE"), nullable=False),
        sa.Column("attempt_no", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(120), nullable=False, server_default=""),
        sa.Column("integration_id", sa.String(255), nullable=False, server_default=""),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime()),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("error_code", sa.String(120)),
        sa.Column("error_message", sa.Text()),
        sa.Column("provider_request_id", sa.String(255)),
        sa.Column("response_summary", JSONB),
        sa.Column("request_id", sa.String(255), nullable=False, server_default=""),
        sa.UniqueConstraint("distribution_job_id", "attempt_no", name="uq_meiti_distribution_attempt_no"),
    )
    op.create_index("idx_meiti_distribution_attempts_job", "distribution_attempts", ["distribution_job_id"])
    op.create_table(
        "publications",
        sa.Column("publication_id", sa.String(255), primary_key=True),
        sa.Column("distribution_job_id", sa.String(255), sa.ForeignKey("distribution_jobs.job_id", ondelete="RESTRICT"), nullable=False, unique=True),
        sa.Column("integration_id", sa.String(255), sa.ForeignKey("integrations.integration_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("provider", sa.String(120), nullable=False),
        sa.Column("provider_post_id", sa.String(255), nullable=False),
        sa.Column("platform_object_id", sa.String(255)),
        sa.Column("external_url", sa.Text()),
        sa.Column("status", sa.String(40), nullable=False, server_default="UNKNOWN"),
        sa.Column("published_at", sa.DateTime()),
        sa.Column("content_package_id", sa.String(255), nullable=False),
        sa.Column("request_id", sa.String(255), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint("provider", "provider_post_id", name="uq_meiti_publication_provider_post"),
    )
    op.create_index("idx_meiti_publications_integration", "publications", ["integration_id"])
    op.create_index("idx_meiti_publications_status", "publications", ["status"])
    op.create_table(
        "media_uploads",
        sa.Column("source_hash", sa.String(64), primary_key=True),
        sa.Column("source_path", sa.Text(), nullable=False),
        sa.Column("mime_type", sa.String(120), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(120), nullable=False),
        sa.Column("integration_id", sa.String(255), nullable=False, server_default=""),
        sa.Column("remote_media_id", sa.String(255), nullable=False),
        sa.Column("remote_media_path", sa.Text(), nullable=False),
        sa.Column("status", sa.String(40), nullable=False, server_default="uploaded"),
        sa.Column("uploaded_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("idx_meiti_media_uploads_provider", "media_uploads", ["provider"])
    op.create_index("idx_meiti_media_uploads_status", "media_uploads", ["status"])
    op.create_table(
        "metric_snapshots",
        sa.Column("snapshot_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("publication_id", sa.String(255), sa.ForeignKey("publications.publication_id", ondelete="CASCADE"), nullable=False),
        sa.Column("metric_name", sa.String(120), nullable=False),
        sa.Column("value", sa.Numeric(18, 6)),
        sa.Column("observed_at", sa.DateTime(), nullable=False),
        sa.Column("source", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint("publication_id", "metric_name", "observed_at", "source", name="uq_meiti_metric_snapshot"),
    )
    op.create_index("idx_meiti_metric_snapshots_publication", "metric_snapshots", ["publication_id"])
    op.create_index("idx_meiti_metric_snapshots_observed", "metric_snapshots", ["observed_at"])
    op.execute("DROP TABLE IF EXISTS schema_migrations")


def downgrade() -> None:
    for table in ("metric_snapshots", "media_uploads", "publications", "distribution_attempts", "distribution_jobs", "integrations", "content_variants", "content_packages", "campaigns"):
        op.drop_table(table)
