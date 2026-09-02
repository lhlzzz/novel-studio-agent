"""CN social runtime: VERIFYING, leases, listings, object types."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0007_v442_cn_social"
down_revision = "0006_v44_native_social"
branch_labels = None
depends_on = None

JSONB = postgresql.JSONB


def upgrade() -> None:
    op.drop_constraint("ck_meiti_social_account_status", "social_accounts", type_="check")
    op.create_check_constraint(
        "ck_meiti_social_account_status",
        "social_accounts",
        "status IN ('PENDING','AUTHENTICATING','AUTHENTICATED','VERIFYING','VERIFIED','ENABLED','DEGRADED','EXPIRED','REVOKED','BLOCKED')",
    )
    op.execute("ALTER TABLE distribution_jobs ADD COLUMN IF NOT EXISTS account_id VARCHAR(255) NOT NULL DEFAULT ''")
    op.execute("ALTER TABLE distribution_jobs ADD COLUMN IF NOT EXISTS lease_until TIMESTAMP")
    op.execute("ALTER TABLE distribution_jobs ADD COLUMN IF NOT EXISTS worker_id VARCHAR(255)")
    op.execute("ALTER TABLE distribution_jobs ADD COLUMN IF NOT EXISTS claimed_at TIMESTAMP")
    op.execute("ALTER TABLE publications ADD COLUMN IF NOT EXISTS provider_object_type VARCHAR(40) NOT NULL DEFAULT ''")
    try:
        op.drop_constraint("ck_meiti_distribution_job_status", "distribution_jobs", type_="check")
    except Exception:
        pass
    op.create_check_constraint(
        "ck_meiti_distribution_job_status",
        "distribution_jobs",
        "status IN ('DRAFT','VALIDATING','BLOCKED','READY','SUBMITTING','SUBMITTED','SCHEDULED','PUBLISHING','PUBLISHED','FAILED','RETRYING','CANCELLED','UNKNOWN','FAILED_PERMANENT','RECONCILING')",
    )
    op.create_table(
        "xianyu_listings",
        sa.Column("listing_id", sa.String(255), primary_key=True),
        sa.Column("account_id", sa.String(255), nullable=False),
        sa.Column("provider_item_id", sa.String(255), nullable=False, server_default=""),
        sa.Column("title", sa.Text(), nullable=False, server_default=""),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("price", sa.String(40), nullable=False, server_default=""),
        sa.Column("category_id", sa.String(255), nullable=False, server_default=""),
        sa.Column("media_assets", JSONB, nullable=False, server_default="[]"),
        sa.Column("status", sa.String(40), nullable=False, server_default="DRAFT"),
        sa.Column("provider_response", JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("idx_meiti_xianyu_listings_account", "xianyu_listings", ["account_id"])
    op.create_index("idx_meiti_xianyu_listings_status", "xianyu_listings", ["status"])
    op.execute("ALTER TABLE derived_assets ADD COLUMN IF NOT EXISTS derived_asset_id VARCHAR(255)")


def downgrade() -> None:
    op.drop_table("xianyu_listings")
