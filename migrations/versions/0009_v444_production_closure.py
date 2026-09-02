"""V4.4.4 production closure: unique handoff/listing, media identity, listing lifecycle."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0009_v444_production_closure"
down_revision = "0008_v443_cn_hardening"
branch_labels = None
depends_on = None

JSONB = postgresql.JSONB


def upgrade() -> None:
    op.drop_constraint("ck_meiti_social_account_status", "social_accounts", type_="check")
    op.create_check_constraint(
        "ck_meiti_social_account_status",
        "social_accounts",
        "status IN ('PENDING','AUTHENTICATING','AUTHENTICATED','VERIFYING','REFRESHING','VERIFIED','ENABLED','DEGRADED','EXPIRED','REVOKED','BLOCKED','TARGET_ONLY','HANDOFF_READY','IDENTITY_UNVERIFIED')",
    )
    op.drop_constraint("ck_meiti_distribution_job_status", "distribution_jobs", type_="check")
    op.create_check_constraint(
        "ck_meiti_distribution_job_status",
        "distribution_jobs",
        "status IN ('DRAFT','VALIDATING','BLOCKED','READY','SUBMITTING','SUBMITTED','SCHEDULED','PUBLISHING','PROCESSING','PUBLISHED','FAILED','RETRYING','CANCELLED','UNKNOWN','FAILED_PERMANENT','RECONCILING')",
    )
    op.execute("ALTER TABLE social_handoffs ADD COLUMN IF NOT EXISTS export_status VARCHAR(40) NOT NULL DEFAULT 'PENDING'")
    op.drop_index("idx_meiti_social_handoffs_job", table_name="social_handoffs")
    op.create_index(
        "uq_meiti_social_handoffs_job",
        "social_handoffs",
        ["distribution_job_id"],
        unique=True,
        postgresql_where=sa.text("distribution_job_id <> ''"),
    )
    op.create_check_constraint(
        "ck_meiti_social_handoff_export_status",
        "social_handoffs",
        "export_status IN ('PENDING','READY','FAILED')",
    )
    op.execute("ALTER TABLE media_uploads ADD COLUMN IF NOT EXISTS account_id VARCHAR(255) NOT NULL DEFAULT ''")
    op.execute("ALTER TABLE media_uploads DROP CONSTRAINT IF EXISTS media_uploads_pkey")
    op.create_primary_key("pk_meiti_media_uploads", "media_uploads", ["source_hash", "provider", "account_id"])
    op.execute("ALTER TABLE xianyu_listings ADD COLUMN IF NOT EXISTS distribution_job_id VARCHAR(255) NOT NULL DEFAULT ''")
    op.execute("ALTER TABLE xianyu_listings ADD COLUMN IF NOT EXISTS condition VARCHAR(40) NOT NULL DEFAULT 'new'")
    op.execute("ALTER TABLE xianyu_listings ADD COLUMN IF NOT EXISTS location TEXT NOT NULL DEFAULT ''")
    op.execute("ALTER TABLE xianyu_listings ADD COLUMN IF NOT EXISTS shipping JSONB NOT NULL DEFAULT '{}'::jsonb")
    op.execute("ALTER TABLE xianyu_listings ADD COLUMN IF NOT EXISTS attributes JSONB NOT NULL DEFAULT '{}'::jsonb")
    op.create_index(
        "uq_meiti_xianyu_listings_job",
        "xianyu_listings",
        ["distribution_job_id"],
        unique=True,
        postgresql_where=sa.text("distribution_job_id <> ''"),
    )
    op.create_index("idx_meiti_xianyu_listings_item", "xianyu_listings", ["provider_item_id"])
    op.create_check_constraint(
        "ck_meiti_xianyu_listing_status",
        "xianyu_listings",
        "status IN ('DRAFT','SUBMITTING','PROCESSING','ONLINE','FAILED','REMOVED','UNKNOWN')",
    )
    op.execute("ALTER TABLE distribution_attempts ADD COLUMN IF NOT EXISTS provider_object_id VARCHAR(255)")


def downgrade() -> None:
    op.drop_constraint("ck_meiti_xianyu_listing_status", "xianyu_listings", type_="check")
    op.drop_index("idx_meiti_xianyu_listings_item", table_name="xianyu_listings")
    op.drop_index("uq_meiti_xianyu_listings_job", table_name="xianyu_listings")
    op.drop_constraint("ck_meiti_social_handoff_export_status", "social_handoffs", type_="check")
    op.drop_index("uq_meiti_social_handoffs_job", table_name="social_handoffs")
    op.create_index("idx_meiti_social_handoffs_job", "social_handoffs", ["distribution_job_id"])
    op.drop_constraint("pk_meiti_media_uploads", "media_uploads", type_="primary")
    op.create_primary_key("media_uploads_pkey", "media_uploads", ["source_hash"])
