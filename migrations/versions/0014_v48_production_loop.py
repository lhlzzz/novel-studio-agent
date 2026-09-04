"""V4.8 real creator production loop: evidence, analytics, learning, immutability."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0014_v48_production_loop"
down_revision = "0013_v471_platform_asset_dna"
branch_labels = None
depends_on = None

JSONB = postgresql.JSONB

EPISODE_STATUSES = (
    "IDEA","BRIEFED","DRAFT","PROMPT_READY","AWAITING_CREATIVE","GENERATING","GENERATED",
    "IMPORTED","QA_PASSED","QA_FAILED","PACKAGE_READY","HANDOFF_READY","READY_TO_PUBLISH",
    "APPROVED","PUBLISHED","ANALYTICS_PENDING","LEARNED","FAILED","REJECTED","ARCHIVED",
)


def upgrade() -> None:
    op.execute("ALTER TABLE episodes ADD COLUMN IF NOT EXISTS character_revision INTEGER")
    op.execute("ALTER TABLE episodes ADD COLUMN IF NOT EXISTS world_revision INTEGER")
    op.execute("ALTER TABLE episodes ADD COLUMN IF NOT EXISTS production_run_id VARCHAR(255)")
    op.execute("ALTER TABLE prompt_packages ADD COLUMN IF NOT EXISTS prompt_hash VARCHAR(64) NOT NULL DEFAULT ''")
    op.execute("ALTER TABLE prompt_packages ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1")
    op.execute("ALTER TABLE prompt_packages ADD COLUMN IF NOT EXISTS parent_prompt_id VARCHAR(255)")
    op.execute("ALTER TABLE prompt_patterns ADD COLUMN IF NOT EXISTS promotion_status VARCHAR(40) NOT NULL DEFAULT 'PLATFORM'")
    op.execute("ALTER TABLE prompt_patterns ADD COLUMN IF NOT EXISTS sample_count INTEGER NOT NULL DEFAULT 0")

    op.execute("ALTER TABLE episodes DROP CONSTRAINT IF EXISTS ck_meiti_episode_status")
    op.create_check_constraint(
        "ck_meiti_episode_status",
        "episodes",
        "content_status IN (" + ",".join(f"'{item}'" for item in EPISODE_STATUSES) + ")",
    )

    op.create_table(
        "production_runs",
        sa.Column("run_id", sa.String(255), primary_key=True),
        sa.Column("account_id", sa.String(255), sa.ForeignKey("platform_accounts.account_id", ondelete="CASCADE"), nullable=False),
        sa.Column("platform", sa.String(120), nullable=False),
        sa.Column("episode_id", sa.String(255)),
        sa.Column("prompt_id", sa.String(255)),
        sa.Column("asset_id", sa.String(255)),
        sa.Column("package_id", sa.String(255)),
        sa.Column("handoff_id", sa.String(255)),
        sa.Column("publication_id", sa.String(255)),
        sa.Column("analytics_id", sa.String(255)),
        sa.Column("learning_id", sa.String(255)),
        sa.Column("status", sa.String(40), nullable=False, server_default="OPEN"),
        sa.Column("request", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("idx_meiti_production_runs_account", "production_runs", ["account_id"])
    op.create_index("idx_meiti_production_runs_episode", "production_runs", ["episode_id"])

    op.create_table(
        "production_evidence",
        sa.Column("evidence_id", sa.String(255), primary_key=True),
        sa.Column("kind", sa.String(80), nullable=False),
        sa.Column("account_id", sa.String(255), sa.ForeignKey("platform_accounts.account_id", ondelete="CASCADE"), nullable=False),
        sa.Column("platform", sa.String(120), nullable=False),
        sa.Column("status", sa.String(40), nullable=False, server_default="PASS"),
        sa.Column("episode_id", sa.String(255)),
        sa.Column("prompt_id", sa.String(255)),
        sa.Column("asset_id", sa.String(255)),
        sa.Column("package_id", sa.String(255)),
        sa.Column("handoff_id", sa.String(255)),
        sa.Column("publication_id", sa.String(255)),
        sa.Column("analytics_id", sa.String(255)),
        sa.Column("learning_id", sa.String(255)),
        sa.Column("production_run_id", sa.String(255)),
        sa.Column("source", sa.String(40), nullable=False, server_default="operator"),
        sa.Column("detail", JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("idx_meiti_production_evidence_account", "production_evidence", ["account_id"])
    op.create_index("idx_meiti_production_evidence_episode", "production_evidence", ["episode_id"])
    op.create_index("idx_meiti_production_evidence_kind", "production_evidence", ["kind"])

    op.create_table(
        "analytics_records",
        sa.Column("analytics_id", sa.String(255), primary_key=True),
        sa.Column("account_id", sa.String(255), sa.ForeignKey("platform_accounts.account_id", ondelete="CASCADE"), nullable=False),
        sa.Column("platform", sa.String(120), nullable=False),
        sa.Column("episode_id", sa.String(255)),
        sa.Column("package_id", sa.String(255)),
        sa.Column("handoff_id", sa.String(255)),
        sa.Column("publication_id", sa.String(255)),
        sa.Column("impressions", sa.Integer()),
        sa.Column("likes", sa.Integer()),
        sa.Column("favorites", sa.Integer()),
        sa.Column("comments", sa.Integer()),
        sa.Column("shares", sa.Integer()),
        sa.Column("followers_gained", sa.Integer()),
        sa.Column("published_at", sa.String(80)),
        sa.Column("topic", sa.Text(), nullable=False, server_default=""),
        sa.Column("cover", sa.Text(), nullable=False, server_default=""),
        sa.Column("prompt_pattern", sa.Text(), nullable=False, server_default=""),
        sa.Column("source", sa.String(40), nullable=False, server_default="manual"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("idx_meiti_analytics_records_account", "analytics_records", ["account_id"])
    op.create_index("idx_meiti_analytics_records_episode", "analytics_records", ["episode_id"])

    op.create_table(
        "learning_records",
        sa.Column("learning_id", sa.String(255), primary_key=True),
        sa.Column("account_id", sa.String(255), sa.ForeignKey("platform_accounts.account_id", ondelete="CASCADE"), nullable=False),
        sa.Column("platform", sa.String(120), nullable=False),
        sa.Column("episode_id", sa.String(255)),
        sa.Column("analytics_id", sa.String(255)),
        sa.Column("pattern_ids", JSONB, nullable=False, server_default="[]"),
        sa.Column("what_worked", sa.Text(), nullable=False, server_default=""),
        sa.Column("what_failed", sa.Text(), nullable=False, server_default=""),
        sa.Column("visual_learning", sa.Text(), nullable=False, server_default=""),
        sa.Column("content_learning", sa.Text(), nullable=False, server_default=""),
        sa.Column("prompt_learning", sa.Text(), nullable=False, server_default=""),
        sa.Column("audience_learning", sa.Text(), nullable=False, server_default=""),
        sa.Column("next_recommendation", sa.Text(), nullable=False, server_default=""),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("source_episode_ids", JSONB, nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("idx_meiti_learning_records_account", "learning_records", ["account_id"])
    op.create_index("idx_meiti_learning_records_platform", "learning_records", ["platform"])

    op.create_table(
        "creative_execution_receipts",
        sa.Column("receipt_id", sa.String(255), primary_key=True),
        sa.Column("asset_id", sa.String(255), nullable=False),
        sa.Column("prompt_id", sa.String(255)),
        sa.Column("tool", sa.String(80), nullable=False, server_default="lechuang"),
        sa.Column("model", sa.String(120), nullable=False, server_default="UNKNOWN"),
        sa.Column("generated_at", sa.DateTime()),
        sa.Column("operator", sa.String(120), nullable=False, server_default="operator"),
        sa.Column("source_asset_id", sa.String(255)),
        sa.Column("generation_mode", sa.String(80), nullable=False, server_default="MANUAL_CREATIVE_TOOL"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("idx_meiti_creative_receipts_asset", "creative_execution_receipts", ["asset_id"])
    op.create_index("idx_meiti_creative_receipts_prompt", "creative_execution_receipts", ["prompt_id"])

    op.create_table(
        "character_revisions",
        sa.Column("revision_id", sa.String(255), primary_key=True),
        sa.Column("character_id", sa.String(255), nullable=False),
        sa.Column("account_id", sa.String(255), sa.ForeignKey("platform_accounts.account_id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("snapshot", JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint("character_id", "version", name="uq_meiti_character_revision"),
    )
    op.create_index("idx_meiti_character_revisions_character", "character_revisions", ["character_id"])

    op.create_table(
        "world_revisions",
        sa.Column("revision_id", sa.String(255), primary_key=True),
        sa.Column("world_id", sa.String(255), nullable=False),
        sa.Column("account_id", sa.String(255), sa.ForeignKey("platform_accounts.account_id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("snapshot", JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint("world_id", "version", name="uq_meiti_world_revision"),
    )
    op.create_index("idx_meiti_world_revisions_world", "world_revisions", ["world_id"])

    op.create_table(
        "asset_reference_snapshots",
        sa.Column("snapshot_id", sa.String(255), primary_key=True),
        sa.Column("prompt_id", sa.String(255), nullable=False),
        sa.Column("asset_id", sa.String(255), nullable=False),
        sa.Column("role", sa.String(40), nullable=False, server_default="SCENE_REFERENCE"),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("prompt_influence", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("idx_meiti_asset_reference_snapshots_prompt", "asset_reference_snapshots", ["prompt_id"])

    op.create_table(
        "pattern_promotions",
        sa.Column("promotion_id", sa.String(255), primary_key=True),
        sa.Column("pattern_id", sa.String(255), nullable=False),
        sa.Column("platform", sa.String(120), nullable=False),
        sa.Column("status", sa.String(40), nullable=False, server_default="PLATFORM"),
        sa.Column("sample_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cross_platform_evidence", JSONB, nullable=False, server_default="[]"),
        sa.Column("confidence", sa.Numeric(18, 6), nullable=False, server_default="0"),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("idx_meiti_pattern_promotions_pattern", "pattern_promotions", ["pattern_id"])
    op.create_index("idx_meiti_pattern_promotions_platform", "pattern_promotions", ["platform"])

    op.create_table(
        "lifecycle_transitions",
        sa.Column("transition_id", sa.String(255), primary_key=True),
        sa.Column("episode_id", sa.String(255), nullable=False),
        sa.Column("account_id", sa.String(255), sa.ForeignKey("platform_accounts.account_id", ondelete="CASCADE"), nullable=False),
        sa.Column("from_status", sa.String(40), nullable=False),
        sa.Column("to_status", sa.String(40), nullable=False),
        sa.Column("owner", sa.String(80), nullable=False),
        sa.Column("evidence_id", sa.String(255)),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("idx_meiti_lifecycle_transitions_episode", "lifecycle_transitions", ["episode_id"])
    op.create_index("idx_meiti_lifecycle_transitions_account", "lifecycle_transitions", ["account_id"])


def downgrade() -> None:
    for table in (
        "lifecycle_transitions",
        "pattern_promotions",
        "asset_reference_snapshots",
        "world_revisions",
        "character_revisions",
        "creative_execution_receipts",
        "learning_records",
        "analytics_records",
        "production_evidence",
        "production_runs",
    ):
        op.drop_table(table)
