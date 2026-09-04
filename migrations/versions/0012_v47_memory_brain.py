"""V4.7 knowledge brain, account selection, embeddings scope, lineage uniqueness."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0012_v47_memory_brain"
down_revision = "0011_v46_account_continuity"
branch_labels = None
depends_on = None

JSONB = postgresql.JSONB


def upgrade() -> None:
    op.execute("ALTER TABLE content_packages ADD COLUMN IF NOT EXISTS current_revision VARCHAR(255)")
    op.execute("ALTER TABLE content_embeddings ADD COLUMN IF NOT EXISTS account_id VARCHAR(255)")
    op.execute("ALTER TABLE content_embeddings ADD COLUMN IF NOT EXISTS scope_type VARCHAR(40)")
    op.execute("ALTER TABLE content_embeddings ADD COLUMN IF NOT EXISTS scope_id VARCHAR(255)")
    op.execute("ALTER TABLE content_embeddings ADD COLUMN IF NOT EXISTS character_id VARCHAR(255)")
    op.execute("ALTER TABLE content_embeddings ADD COLUMN IF NOT EXISTS world_id VARCHAR(255)")
    op.execute("ALTER TABLE content_embeddings ADD COLUMN IF NOT EXISTS series_id VARCHAR(255)")
    op.execute("ALTER TABLE content_embeddings ADD COLUMN IF NOT EXISTS episode_id VARCHAR(255)")
    op.execute("ALTER TABLE content_embeddings ADD COLUMN IF NOT EXISTS publication_id VARCHAR(255)")
    op.execute("ALTER TABLE content_embeddings ADD COLUMN IF NOT EXISTS source_document_id VARCHAR(255)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_meiti_content_embeddings_account ON content_embeddings (account_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_meiti_content_embeddings_scope ON content_embeddings (scope_type, scope_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_meiti_content_embeddings_document ON content_embeddings (source_document_id)")

    op.execute("ALTER TABLE asset_lineage ADD COLUMN IF NOT EXISTS selected_for_package BOOLEAN NOT NULL DEFAULT false")
    op.execute("ALTER TABLE asset_lineage ADD COLUMN IF NOT EXISTS source_asset_id VARCHAR(255)")
    op.execute("ALTER TABLE asset_lineage ADD COLUMN IF NOT EXISTS workflow_id VARCHAR(255)")
    op.execute("UPDATE asset_lineage SET parent_asset_id = '' WHERE parent_asset_id IS NULL")
    op.execute("ALTER TABLE asset_lineage ALTER COLUMN parent_asset_id SET DEFAULT ''")
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_meiti_lineage_attempt ON asset_lineage (account_id, episode_id, parent_asset_id, attempt_no)"
    )

    op.create_table(
        "account_selections",
        sa.Column("selection_key", sa.String(80), primary_key=True),
        sa.Column("account_id", sa.String(255), sa.ForeignKey("platform_accounts.account_id", ondelete="CASCADE"), nullable=False),
        sa.Column("platform", sa.String(120), nullable=False),
        sa.Column("reason", sa.String(80), nullable=False, server_default="explicit"),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("idx_meiti_account_selections_account", "account_selections", ["account_id"])
    op.create_index("idx_meiti_account_selections_platform", "account_selections", ["platform"])

    op.create_table(
        "knowledge_documents",
        sa.Column("document_id", sa.String(255), primary_key=True),
        sa.Column("scope_type", sa.String(40), nullable=False),
        sa.Column("scope_id", sa.String(255)),
        sa.Column("account_id", sa.String(255)),
        sa.Column("platform", sa.String(120), nullable=False, server_default=""),
        sa.Column("source_type", sa.String(80), nullable=False, server_default="obsidian"),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("path", sa.Text(), nullable=False, server_default=""),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("tags", JSONB, nullable=False, server_default="[]"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(40), nullable=False, server_default="ACTIVE"),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("character_id", sa.String(255)),
        sa.Column("world_id", sa.String(255)),
        sa.Column("series_id", sa.String(255)),
        sa.Column("episode_id", sa.String(255)),
        sa.Column("publication_id", sa.String(255)),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("idx_meiti_knowledge_documents_account", "knowledge_documents", ["account_id"])
    op.create_index("idx_meiti_knowledge_documents_scope", "knowledge_documents", ["scope_type", "scope_id"])
    op.create_index("idx_meiti_knowledge_documents_hash", "knowledge_documents", ["content_hash"])
    op.create_index("idx_meiti_knowledge_documents_platform", "knowledge_documents", ["platform"])


def downgrade() -> None:
    op.drop_table("knowledge_documents")
    op.drop_table("account_selections")
    op.execute("DROP INDEX IF EXISTS uq_meiti_lineage_attempt")
    op.execute("ALTER TABLE asset_lineage DROP COLUMN IF EXISTS selected_for_package")
    op.execute("ALTER TABLE asset_lineage DROP COLUMN IF EXISTS source_asset_id")
    op.execute("ALTER TABLE asset_lineage DROP COLUMN IF EXISTS workflow_id")
    op.execute("ALTER TABLE content_packages DROP COLUMN IF EXISTS current_revision")
    op.execute("ALTER TABLE content_embeddings DROP COLUMN IF EXISTS source_document_id")
    op.execute("ALTER TABLE content_embeddings DROP COLUMN IF EXISTS publication_id")
    op.execute("ALTER TABLE content_embeddings DROP COLUMN IF EXISTS episode_id")
    op.execute("ALTER TABLE content_embeddings DROP COLUMN IF EXISTS series_id")
    op.execute("ALTER TABLE content_embeddings DROP COLUMN IF EXISTS world_id")
    op.execute("ALTER TABLE content_embeddings DROP COLUMN IF EXISTS character_id")
    op.execute("ALTER TABLE content_embeddings DROP COLUMN IF EXISTS scope_id")
    op.execute("ALTER TABLE content_embeddings DROP COLUMN IF EXISTS scope_type")
    op.execute("ALTER TABLE content_embeddings DROP COLUMN IF EXISTS account_id")
