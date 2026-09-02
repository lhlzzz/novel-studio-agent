"""CN social production hardening: handoff, job identity, account states."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0008_v443_cn_hardening"
down_revision = "0007_v442_cn_social"
branch_labels = None
depends_on = None

JSONB = postgresql.JSONB


def upgrade() -> None:
    op.drop_constraint("ck_meiti_social_account_status", "social_accounts", type_="check")
    op.create_check_constraint(
        "ck_meiti_social_account_status",
        "social_accounts",
        "status IN ('PENDING','AUTHENTICATING','AUTHENTICATED','VERIFYING','VERIFIED','ENABLED','DEGRADED','EXPIRED','REVOKED','BLOCKED','TARGET_ONLY','HANDOFF_READY','IDENTITY_UNVERIFIED')",
    )
    op.execute("ALTER TABLE social_accounts ADD COLUMN IF NOT EXISTS revoke_attempted INTEGER NOT NULL DEFAULT 0")
    op.execute("ALTER TABLE social_accounts ADD COLUMN IF NOT EXISTS remote_revoked INTEGER NOT NULL DEFAULT 0")
    op.execute("ALTER TABLE social_accounts ADD COLUMN IF NOT EXISTS remote_revoke_supported INTEGER")
    op.execute("ALTER TABLE social_accounts ADD COLUMN IF NOT EXISTS revoke_error TEXT")
    op.execute("ALTER TABLE distribution_jobs ADD COLUMN IF NOT EXISTS provider VARCHAR(120) NOT NULL DEFAULT ''")
    op.execute("ALTER TABLE distribution_jobs ADD COLUMN IF NOT EXISTS platform VARCHAR(120) NOT NULL DEFAULT ''")
    op.execute("ALTER TABLE xianyu_listings ADD COLUMN IF NOT EXISTS quantity INTEGER NOT NULL DEFAULT 1")
    op.execute("ALTER TABLE xianyu_listings ADD COLUMN IF NOT EXISTS content_package_id VARCHAR(255) NOT NULL DEFAULT ''")
    op.create_table(
        "social_handoffs",
        sa.Column("handoff_id", sa.String(255), primary_key=True),
        sa.Column("provider", sa.String(120), nullable=False, server_default="xiaohongshu"),
        sa.Column("platform", sa.String(120), nullable=False, server_default="xiaohongshu"),
        sa.Column("account_id", sa.String(255), nullable=False),
        sa.Column("content_package_id", sa.String(255), nullable=False, server_default=""),
        sa.Column("status", sa.String(40), nullable=False, server_default="READY_FOR_XHS"),
        sa.Column("export_path", sa.Text(), nullable=False, server_default=""),
        sa.Column("distribution_job_id", sa.String(255), nullable=False, server_default=""),
        sa.Column("package", JSONB, nullable=False, server_default="{}"),
        sa.Column("expires_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.CheckConstraint(
            "status IN ('READY_FOR_XHS','OPENED','SUBMITTED','PUBLISHED','EXPIRED','CANCELLED')",
            name="ck_meiti_social_handoff_status",
        ),
    )
    op.create_index("idx_meiti_social_handoffs_account", "social_handoffs", ["account_id"])
    op.create_index("idx_meiti_social_handoffs_job", "social_handoffs", ["distribution_job_id"])


def downgrade() -> None:
    op.drop_table("social_handoffs")
