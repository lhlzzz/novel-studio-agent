"""Native social accounts and provider-neutral publication identifiers."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0006_v44_native_social"
down_revision = "0005_v42_hardening"
branch_labels = None
depends_on = None

JSONB = postgresql.JSONB


def upgrade() -> None:
    op.create_table(
        "social_accounts",
        sa.Column("account_id", sa.String(255), primary_key=True),
        sa.Column("provider", sa.String(120), nullable=False),
        sa.Column("platform", sa.String(120), nullable=False),
        sa.Column("username", sa.Text(), nullable=False, server_default=""),
        sa.Column("display_name", sa.Text(), nullable=False, server_default=""),
        sa.Column("avatar_url", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(40), nullable=False, server_default="PENDING"),
        sa.Column("capabilities", JSONB, nullable=False, server_default="{}"),
        sa.Column("credential_ref", sa.String(255), nullable=False, server_default=""),
        sa.Column("provider_account_id", sa.String(255), nullable=False, server_default=""),
        sa.Column("region", sa.String(80), nullable=False, server_default="global"),
        sa.Column("last_verified_at", sa.DateTime()),
        sa.Column("blocked_reason", sa.Text()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.CheckConstraint(
            "status IN ('PENDING','AUTHENTICATING','AUTHENTICATED','VERIFIED','ENABLED','DEGRADED','EXPIRED','REVOKED','BLOCKED')",
            name="ck_meiti_social_account_status",
        ),
    )
    op.create_index("idx_meiti_social_accounts_provider", "social_accounts", ["provider"])
    op.create_index("idx_meiti_social_accounts_status", "social_accounts", ["status"])
    op.execute(
        """
        INSERT INTO social_accounts (
            account_id, provider, platform, username, display_name, status, capabilities,
            provider_account_id, region, last_verified_at, created_at, updated_at
        )
        SELECT
            integration_id,
            provider,
            COALESCE(NULLIF(platform, ''), provider),
            COALESCE(account_name, ''),
            COALESCE(account_name, ''),
            CASE
                WHEN enabled = 1 THEN 'ENABLED'
                WHEN state IN ('VERIFIED','ENABLED','AUTHENTICATED','BLOCKED','DEGRADED') THEN state
                ELSE 'PENDING'
            END,
            capabilities,
            COALESCE(NULLIF(account_id, ''), integration_id),
            region,
            verified_at,
            created_at,
            updated_at
        FROM integrations
        ON CONFLICT (account_id) DO NOTHING
        """
    )
    op.create_table(
        "derived_assets",
        sa.Column("derived_asset_id", sa.String(255), primary_key=True),
        sa.Column("source_asset_id", sa.String(255), nullable=False),
        sa.Column("target_platform", sa.String(80), nullable=False),
        sa.Column("transformation", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("idx_meiti_derived_assets_source", "derived_assets", ["source_asset_id"])
    op.create_index("idx_meiti_derived_assets_platform", "derived_assets", ["target_platform"])
    op.add_column("publications", sa.Column("platform", sa.String(120), nullable=False, server_default=""))
    op.add_column("publications", sa.Column("account_id", sa.String(255), nullable=False, server_default=""))
    op.execute("UPDATE publications SET account_id = integration_id WHERE account_id = ''")
    op.execute("UPDATE publications SET platform = provider WHERE platform = ''")
    op.add_column("distribution_jobs", sa.Column("account_id", sa.String(255), nullable=False, server_default=""))
    op.execute("UPDATE distribution_jobs SET account_id = integration_id WHERE account_id = ''")


def downgrade() -> None:
    op.drop_column("distribution_jobs", "account_id")
    op.drop_column("publications", "account_id")
    op.drop_column("publications", "platform")
    op.drop_table("derived_assets")
    op.drop_table("social_accounts")
