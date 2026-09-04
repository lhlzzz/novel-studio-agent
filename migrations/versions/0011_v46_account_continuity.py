"""V4.6 account world, series, continuity, lineage, and layered memory."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0011_v46_account_continuity"
down_revision = "0010_v45_production_activation"
branch_labels = None
depends_on = None

JSONB = postgresql.JSONB


def upgrade() -> None:
    op.execute("ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS account_id VARCHAR(255)")
    op.execute("ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS platform VARCHAR(120) NOT NULL DEFAULT ''")
    op.execute("ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS parent_campaign_id VARCHAR(255)")
    op.execute("ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS series_id VARCHAR(255)")
    op.execute("ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS world_id VARCHAR(255)")
    op.execute("ALTER TABLE content_packages ADD COLUMN IF NOT EXISTS account_id VARCHAR(255)")
    op.execute("ALTER TABLE content_packages ADD COLUMN IF NOT EXISTS series_id VARCHAR(255)")
    op.execute("ALTER TABLE content_packages ADD COLUMN IF NOT EXISTS episode_id VARCHAR(255)")
    op.execute("ALTER TABLE content_packages ADD COLUMN IF NOT EXISTS platform VARCHAR(120) NOT NULL DEFAULT ''")
    op.execute("ALTER TABLE content_packages ADD COLUMN IF NOT EXISTS status VARCHAR(40) NOT NULL DEFAULT 'DRAFT'")
    op.execute("ALTER TABLE content_packages ADD COLUMN IF NOT EXISTS character_id VARCHAR(255)")
    op.execute("ALTER TABLE content_packages ADD COLUMN IF NOT EXISTS world_id VARCHAR(255)")
    op.execute("ALTER TABLE content_packages ADD COLUMN IF NOT EXISTS creative_context_id VARCHAR(255)")
    op.execute("ALTER TABLE content_packages ADD COLUMN IF NOT EXISTS revision INTEGER NOT NULL DEFAULT 1")
    op.execute("ALTER TABLE media_assets ADD COLUMN IF NOT EXISTS account_id VARCHAR(255)")
    op.execute("ALTER TABLE media_assets ADD COLUMN IF NOT EXISTS series_id VARCHAR(255)")
    op.execute("ALTER TABLE media_assets ADD COLUMN IF NOT EXISTS episode_id VARCHAR(255)")
    op.execute("ALTER TABLE media_assets ADD COLUMN IF NOT EXISTS content_package_id VARCHAR(255)")
    op.execute("ALTER TABLE media_assets ADD COLUMN IF NOT EXISTS creative_context_id VARCHAR(255)")
    op.execute("ALTER TABLE media_assets ADD COLUMN IF NOT EXISTS world_id VARCHAR(255)")
    op.execute("ALTER TABLE media_assets ADD COLUMN IF NOT EXISTS provider VARCHAR(120) NOT NULL DEFAULT ''")
    op.execute("ALTER TABLE media_assets ADD COLUMN IF NOT EXISTS provider_task_id VARCHAR(255) NOT NULL DEFAULT ''")
    op.execute("ALTER TABLE media_assets ADD COLUMN IF NOT EXISTS model VARCHAR(120) NOT NULL DEFAULT ''")
    op.execute("CREATE INDEX IF NOT EXISTS idx_media_assets_account ON media_assets (account_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_media_assets_episode ON media_assets (episode_id)")

    op.create_table(
        "platform_accounts",
        sa.Column("account_id", sa.String(255), primary_key=True),
        sa.Column("platform", sa.String(120), nullable=False),
        sa.Column("external_account_id", sa.String(255), nullable=False, server_default=""),
        sa.Column("display_name", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(40), nullable=False, server_default="DRAFT"),
        sa.Column("credential_ref", sa.String(255), nullable=False, server_default=""),
        sa.Column("character_id", sa.String(255)),
        sa.Column("world_id", sa.String(255)),
        sa.Column("default_style_profile_id", sa.String(255)),
        sa.Column("social_account_id", sa.String(255)),
        sa.Column("activated_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.CheckConstraint("platform IN ('xiaohongshu','douyin','kuaishou','weixin_video','xianyu')", name="ck_meiti_platform_account_platform"),
        sa.CheckConstraint("status IN ('DRAFT','ACTIVE','PAUSED','ARCHIVED')", name="ck_meiti_platform_account_status"),
    )
    op.create_index("idx_meiti_platform_accounts_platform", "platform_accounts", ["platform"])
    op.create_index("idx_meiti_platform_accounts_status", "platform_accounts", ["status"])
    op.create_table(
        "virtual_characters",
        sa.Column("character_id", sa.String(255), primary_key=True),
        sa.Column("account_id", sa.String(255), sa.ForeignKey("platform_accounts.account_id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("gender", sa.String(40), nullable=False, server_default=""),
        sa.Column("age_range", sa.String(40), nullable=False, server_default=""),
        sa.Column("appearance_profile", JSONB, nullable=False, server_default="{}"),
        sa.Column("body_profile", JSONB, nullable=False, server_default="{}"),
        sa.Column("face_profile", JSONB, nullable=False, server_default="{}"),
        sa.Column("hair_profile", JSONB, nullable=False, server_default="{}"),
        sa.Column("skin_profile", JSONB, nullable=False, server_default="{}"),
        sa.Column("clothing_profile", JSONB, nullable=False, server_default="{}"),
        sa.Column("personality_profile", JSONB, nullable=False, server_default="{}"),
        sa.Column("background_story", sa.Text(), nullable=False, server_default=""),
        sa.Column("speaking_style", sa.Text(), nullable=False, server_default=""),
        sa.Column("behavioral_traits", JSONB, nullable=False, server_default="[]"),
        sa.Column("visual_identity_rules", JSONB, nullable=False, server_default="{}"),
        sa.Column("forbidden_changes", JSONB, nullable=False, server_default="[]"),
        sa.Column("reference_asset_ids", JSONB, nullable=False, server_default="[]"),
        sa.Column("status", sa.String(40), nullable=False, server_default="ACTIVE"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("idx_meiti_virtual_characters_account", "virtual_characters", ["account_id"])
    op.create_table(
        "account_worlds",
        sa.Column("world_id", sa.String(255), primary_key=True),
        sa.Column("account_id", sa.String(255), sa.ForeignKey("platform_accounts.account_id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("world_description", sa.Text(), nullable=False, server_default=""),
        sa.Column("core_theme", sa.Text(), nullable=False, server_default=""),
        sa.Column("values", JSONB, nullable=False, server_default="[]"),
        sa.Column("tone", sa.Text(), nullable=False, server_default=""),
        sa.Column("visual_language", JSONB, nullable=False, server_default="{}"),
        sa.Column("locations", JSONB, nullable=False, server_default="[]"),
        sa.Column("daily_life_rules", JSONB, nullable=False, server_default="[]"),
        sa.Column("story_rules", JSONB, nullable=False, server_default="[]"),
        sa.Column("audience", sa.Text(), nullable=False, server_default=""),
        sa.Column("taboos", JSONB, nullable=False, server_default="[]"),
        sa.Column("brand_rules", JSONB, nullable=False, server_default="[]"),
        sa.Column("status", sa.String(40), nullable=False, server_default="ACTIVE"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("idx_meiti_account_worlds_account", "account_worlds", ["account_id"])
    op.create_table(
        "content_series",
        sa.Column("series_id", sa.String(255), primary_key=True),
        sa.Column("account_id", sa.String(255), sa.ForeignKey("platform_accounts.account_id", ondelete="CASCADE"), nullable=False),
        sa.Column("world_id", sa.String(255), sa.ForeignKey("account_worlds.world_id", ondelete="SET NULL")),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("series_type", sa.String(80), nullable=False, server_default="serial"),
        sa.Column("content_rules", JSONB, nullable=False, server_default="{}"),
        sa.Column("continuity_rules", JSONB, nullable=False, server_default="{}"),
        sa.Column("status", sa.String(40), nullable=False, server_default="ACTIVE"),
        sa.Column("start_date", sa.String(40)),
        sa.Column("end_date", sa.String(40)),
        sa.Column("current_episode_no", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("idx_meiti_content_series_account", "content_series", ["account_id"])
    op.create_table(
        "episodes",
        sa.Column("episode_id", sa.String(255), primary_key=True),
        sa.Column("series_id", sa.String(255), sa.ForeignKey("content_series.series_id", ondelete="CASCADE"), nullable=False),
        sa.Column("account_id", sa.String(255), sa.ForeignKey("platform_accounts.account_id", ondelete="CASCADE"), nullable=False),
        sa.Column("episode_no", sa.Integer(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False, server_default=""),
        sa.Column("brief", sa.Text(), nullable=False, server_default=""),
        sa.Column("previous_episode_id", sa.String(255)),
        sa.Column("next_episode_id", sa.String(255)),
        sa.Column("continuity_context", JSONB, nullable=False, server_default="{}"),
        sa.Column("character_state", JSONB, nullable=False, server_default="{}"),
        sa.Column("world_state", JSONB, nullable=False, server_default="{}"),
        sa.Column("location_state", JSONB, nullable=False, server_default="{}"),
        sa.Column("visual_state", JSONB, nullable=False, server_default="{}"),
        sa.Column("story_state", JSONB, nullable=False, server_default="{}"),
        sa.Column("content_status", sa.String(40), nullable=False, server_default="IDEA"),
        sa.Column("campaign_id", sa.String(255)),
        sa.Column("content_package_id", sa.String(255)),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint("series_id", "episode_no", name="uq_meiti_episode_no"),
        sa.CheckConstraint(
            "content_status IN ('IDEA','BRIEFED','GENERATING','GENERATED','QA_PASSED','DRAFT','APPROVED','READY_TO_PUBLISH','PUBLISHED','FAILED','ARCHIVED')",
            name="ck_meiti_episode_status",
        ),
    )
    op.create_index("idx_meiti_episodes_series", "episodes", ["series_id"])
    op.create_index("idx_meiti_episodes_account", "episodes", ["account_id"])
    op.create_table(
        "creative_contexts",
        sa.Column("context_id", sa.String(255), primary_key=True),
        sa.Column("account_id", sa.String(255), sa.ForeignKey("platform_accounts.account_id", ondelete="CASCADE"), nullable=False),
        sa.Column("platform", sa.String(120), nullable=False),
        sa.Column("character_id", sa.String(255)),
        sa.Column("world_id", sa.String(255)),
        sa.Column("series_id", sa.String(255)),
        sa.Column("episode_id", sa.String(255)),
        sa.Column("campaign_id", sa.String(255)),
        sa.Column("user_request", sa.Text(), nullable=False, server_default=""),
        sa.Column("creative_request", sa.Text(), nullable=False, server_default=""),
        sa.Column("normalized_prompt", sa.Text(), nullable=False, server_default=""),
        sa.Column("system_constraints", JSONB, nullable=False, server_default="{}"),
        sa.Column("character_context", JSONB, nullable=False, server_default="{}"),
        sa.Column("world_context", JSONB, nullable=False, server_default="{}"),
        sa.Column("continuity_context", JSONB, nullable=False, server_default="{}"),
        sa.Column("platform_context", JSONB, nullable=False, server_default="{}"),
        sa.Column("generation_parameters", JSONB, nullable=False, server_default="{}"),
        sa.Column("provider", sa.String(120), nullable=False, server_default=""),
        sa.Column("model", sa.String(120), nullable=False, server_default=""),
        sa.Column("provider_task_id", sa.String(255), nullable=False, server_default=""),
        sa.Column("resolved_target", JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("idx_meiti_creative_contexts_account", "creative_contexts", ["account_id"])
    op.create_index("idx_meiti_creative_contexts_episode", "creative_contexts", ["episode_id"])
    op.create_table(
        "content_revisions",
        sa.Column("revision_id", sa.String(255), primary_key=True),
        sa.Column("content_package_id", sa.String(255), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("parent_revision_id", sa.String(255)),
        sa.Column("change_summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("snapshot", JSONB, nullable=False, server_default="{}"),
        sa.Column("created_by", sa.String(120), nullable=False, server_default="meiti"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint("content_package_id", "version", name="uq_meiti_content_revision"),
    )
    op.create_index("idx_meiti_content_revisions_package", "content_revisions", ["content_package_id"])
    for table, index in (
        ("account_memories", "idx_meiti_account_memories_account"),
        ("character_memories", "idx_meiti_character_memories_account"),
        ("world_memories", "idx_meiti_world_memories_account"),
        ("series_memories", "idx_meiti_series_memories_account"),
        ("episode_memories", "idx_meiti_episode_memories_account"),
    ):
        op.create_table(
            table,
            sa.Column("memory_id", sa.String(255), primary_key=True),
            sa.Column("kind", sa.String(40), nullable=False, server_default=table.split("_")[0]),
            sa.Column("account_id", sa.String(255), sa.ForeignKey("platform_accounts.account_id", ondelete="CASCADE"), nullable=False),
            sa.Column("subject_id", sa.String(255), nullable=False),
            sa.Column("key", sa.String(120), nullable=False),
            sa.Column("value", JSONB, nullable=False, server_default="{}"),
            sa.Column("source", sa.String(120), nullable=False, server_default="continuity"),
            sa.Column("namespace", sa.String(80), nullable=False, server_default=table),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        )
        op.create_index(index, table, ["account_id"])
    op.create_table(
        "performance_feedback",
        sa.Column("feedback_id", sa.String(255), primary_key=True),
        sa.Column("account_id", sa.String(255), sa.ForeignKey("platform_accounts.account_id", ondelete="CASCADE"), nullable=False),
        sa.Column("platform", sa.String(120), nullable=False),
        sa.Column("content_package_id", sa.String(255), nullable=False, server_default=""),
        sa.Column("episode_id", sa.String(255)),
        sa.Column("topic", sa.Text(), nullable=False, server_default=""),
        sa.Column("hook", sa.Text(), nullable=False, server_default=""),
        sa.Column("visual_style", sa.Text(), nullable=False, server_default=""),
        sa.Column("caption_style", sa.Text(), nullable=False, server_default=""),
        sa.Column("duration", sa.Numeric(18, 6)),
        sa.Column("scene", sa.Text(), nullable=False, server_default=""),
        sa.Column("action", sa.Text(), nullable=False, server_default=""),
        sa.Column("audio", sa.Text(), nullable=False, server_default=""),
        sa.Column("engagement", JSONB, nullable=False, server_default="{}"),
        sa.Column("retention", JSONB, nullable=False, server_default="{}"),
        sa.Column("publication_id", sa.String(255), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("idx_meiti_performance_feedback_account", "performance_feedback", ["account_id"])
    op.create_index("idx_meiti_performance_feedback_platform", "performance_feedback", ["platform"])
    op.create_table(
        "asset_lineage",
        sa.Column("lineage_id", sa.String(255), primary_key=True),
        sa.Column("asset_id", sa.String(255), nullable=False),
        sa.Column("account_id", sa.String(255), sa.ForeignKey("platform_accounts.account_id", ondelete="CASCADE"), nullable=False),
        sa.Column("series_id", sa.String(255)),
        sa.Column("episode_id", sa.String(255)),
        sa.Column("content_package_id", sa.String(255)),
        sa.Column("creative_context_id", sa.String(255)),
        sa.Column("character_id", sa.String(255)),
        sa.Column("world_id", sa.String(255)),
        sa.Column("user_request", sa.Text(), nullable=False, server_default=""),
        sa.Column("generation_request", JSONB, nullable=False, server_default="{}"),
        sa.Column("provider", sa.String(120), nullable=False, server_default=""),
        sa.Column("provider_task_id", sa.String(255), nullable=False, server_default=""),
        sa.Column("model", sa.String(120), nullable=False, server_default=""),
        sa.Column("attempt_no", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("parent_asset_id", sa.String(255)),
        sa.Column("qa_decision", sa.String(40), nullable=False, server_default=""),
        sa.Column("published", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("idx_meiti_asset_lineage_asset", "asset_lineage", ["asset_id"])
    op.create_index("idx_meiti_asset_lineage_account", "asset_lineage", ["account_id"])
    op.create_index("idx_meiti_asset_lineage_episode", "asset_lineage", ["episode_id"])


def downgrade() -> None:
    op.drop_table("asset_lineage")
    op.drop_table("performance_feedback")
    for table in ("episode_memories", "series_memories", "world_memories", "character_memories", "account_memories"):
        op.drop_table(table)
    op.drop_table("content_revisions")
    op.drop_table("creative_contexts")
    op.drop_table("episodes")
    op.drop_table("content_series")
    op.drop_table("account_worlds")
    op.drop_table("virtual_characters")
    op.drop_table("platform_accounts")
    op.execute("ALTER TABLE media_assets DROP COLUMN IF EXISTS model")
    op.execute("ALTER TABLE media_assets DROP COLUMN IF EXISTS provider_task_id")
    op.execute("ALTER TABLE media_assets DROP COLUMN IF EXISTS provider")
    op.execute("ALTER TABLE media_assets DROP COLUMN IF EXISTS world_id")
    op.execute("ALTER TABLE media_assets DROP COLUMN IF EXISTS creative_context_id")
    op.execute("ALTER TABLE media_assets DROP COLUMN IF EXISTS content_package_id")
    op.execute("ALTER TABLE media_assets DROP COLUMN IF EXISTS episode_id")
    op.execute("ALTER TABLE media_assets DROP COLUMN IF EXISTS series_id")
    op.execute("ALTER TABLE media_assets DROP COLUMN IF EXISTS account_id")
    op.execute("ALTER TABLE content_packages DROP COLUMN IF EXISTS revision")
    op.execute("ALTER TABLE content_packages DROP COLUMN IF EXISTS creative_context_id")
    op.execute("ALTER TABLE content_packages DROP COLUMN IF EXISTS world_id")
    op.execute("ALTER TABLE content_packages DROP COLUMN IF EXISTS character_id")
    op.execute("ALTER TABLE content_packages DROP COLUMN IF EXISTS status")
    op.execute("ALTER TABLE content_packages DROP COLUMN IF EXISTS platform")
    op.execute("ALTER TABLE content_packages DROP COLUMN IF EXISTS episode_id")
    op.execute("ALTER TABLE content_packages DROP COLUMN IF EXISTS series_id")
    op.execute("ALTER TABLE content_packages DROP COLUMN IF EXISTS account_id")
    op.execute("ALTER TABLE campaigns DROP COLUMN IF EXISTS world_id")
    op.execute("ALTER TABLE campaigns DROP COLUMN IF EXISTS series_id")
    op.execute("ALTER TABLE campaigns DROP COLUMN IF EXISTS parent_campaign_id")
    op.execute("ALTER TABLE campaigns DROP COLUMN IF EXISTS platform")
    op.execute("ALTER TABLE campaigns DROP COLUMN IF EXISTS account_id")
