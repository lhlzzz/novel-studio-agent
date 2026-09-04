"""V4.7.1 platform asset DNA, prompt packages, and learning isolation."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0013_v471_platform_asset_dna"
down_revision = "0012_v47_memory_brain"
branch_labels = None
depends_on = None

JSONB = postgresql.JSONB


def upgrade() -> None:
    op.execute("ALTER TABLE media_assets ADD COLUMN IF NOT EXISTS platform VARCHAR(120) NOT NULL DEFAULT ''")
    op.execute("ALTER TABLE media_assets ADD COLUMN IF NOT EXISTS scope_type VARCHAR(40) NOT NULL DEFAULT 'PLATFORM_ACCOUNT'")
    op.execute("ALTER TABLE media_assets ADD COLUMN IF NOT EXISTS asset_role VARCHAR(40) NOT NULL DEFAULT ''")
    op.execute("ALTER TABLE media_assets ADD COLUMN IF NOT EXISTS lifecycle VARCHAR(40) NOT NULL DEFAULT 'DRAFT'")
    op.execute("ALTER TABLE media_assets ADD COLUMN IF NOT EXISTS pool_id VARCHAR(255)")
    op.execute("ALTER TABLE media_assets ADD COLUMN IF NOT EXISTS parent_asset_id VARCHAR(255)")
    op.execute("ALTER TABLE media_assets ADD COLUMN IF NOT EXISTS source_asset_id VARCHAR(255)")
    op.execute("ALTER TABLE media_assets ADD COLUMN IF NOT EXISTS generation_mode VARCHAR(80) NOT NULL DEFAULT ''")
    op.execute("ALTER TABLE media_assets ADD COLUMN IF NOT EXISTS tool VARCHAR(80) NOT NULL DEFAULT ''")
    op.execute("CREATE INDEX IF NOT EXISTS idx_media_assets_platform ON media_assets (platform)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_media_assets_role ON media_assets (asset_role)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_media_assets_pool ON media_assets (pool_id)")

    op.execute("ALTER TABLE virtual_characters ADD COLUMN IF NOT EXISTS derived_from_character_id VARCHAR(255)")
    op.execute("ALTER TABLE virtual_characters ADD COLUMN IF NOT EXISTS occupation TEXT NOT NULL DEFAULT ''")
    op.execute("ALTER TABLE virtual_characters ADD COLUMN IF NOT EXISTS location TEXT NOT NULL DEFAULT ''")
    op.execute("ALTER TABLE virtual_characters ADD COLUMN IF NOT EXISTS values JSONB NOT NULL DEFAULT '[]'::jsonb")
    op.execute("ALTER TABLE virtual_characters ADD COLUMN IF NOT EXISTS behavior TEXT NOT NULL DEFAULT ''")
    op.execute("ALTER TABLE virtual_characters ADD COLUMN IF NOT EXISTS speech TEXT NOT NULL DEFAULT ''")
    op.execute("ALTER TABLE virtual_characters ADD COLUMN IF NOT EXISTS style JSONB NOT NULL DEFAULT '{}'::jsonb")
    op.execute("ALTER TABLE virtual_characters ADD COLUMN IF NOT EXISTS accessories JSONB NOT NULL DEFAULT '[]'::jsonb")
    op.execute("ALTER TABLE virtual_characters ADD COLUMN IF NOT EXISTS photography TEXT NOT NULL DEFAULT ''")
    op.execute("ALTER TABLE virtual_characters ADD COLUMN IF NOT EXISTS lighting TEXT NOT NULL DEFAULT ''")
    op.execute("ALTER TABLE virtual_characters ADD COLUMN IF NOT EXISTS platform_personality TEXT NOT NULL DEFAULT ''")
    op.execute("ALTER TABLE virtual_characters ADD COLUMN IF NOT EXISTS content_behavior TEXT NOT NULL DEFAULT ''")
    op.execute("ALTER TABLE virtual_characters ADD COLUMN IF NOT EXISTS audience_relationship TEXT NOT NULL DEFAULT ''")
    op.execute("ALTER TABLE virtual_characters ADD COLUMN IF NOT EXISTS continuity_rules JSONB NOT NULL DEFAULT '{}'::jsonb")
    op.execute("ALTER TABLE virtual_characters ADD COLUMN IF NOT EXISTS character_dna JSONB NOT NULL DEFAULT '{}'::jsonb")

    op.execute("ALTER TABLE account_worlds ADD COLUMN IF NOT EXISTS city TEXT NOT NULL DEFAULT ''")
    op.execute("ALTER TABLE account_worlds ADD COLUMN IF NOT EXISTS season TEXT NOT NULL DEFAULT ''")
    op.execute("ALTER TABLE account_worlds ADD COLUMN IF NOT EXISTS time_of_day TEXT NOT NULL DEFAULT ''")
    op.execute("ALTER TABLE account_worlds ADD COLUMN IF NOT EXISTS lighting TEXT NOT NULL DEFAULT ''")
    op.execute("ALTER TABLE account_worlds ADD COLUMN IF NOT EXISTS lifestyle TEXT NOT NULL DEFAULT ''")
    op.execute("ALTER TABLE account_worlds ADD COLUMN IF NOT EXISTS social_relations JSONB NOT NULL DEFAULT '[]'::jsonb")
    op.execute("ALTER TABLE account_worlds ADD COLUMN IF NOT EXISTS world_dna JSONB NOT NULL DEFAULT '{}'::jsonb")

    op.execute("ALTER TABLE episodes ADD COLUMN IF NOT EXISTS primary_asset_id VARCHAR(255)")
    op.execute("ALTER TABLE episodes ADD COLUMN IF NOT EXISTS prompt_id VARCHAR(255)")

    op.execute("ALTER TABLE content_packages ADD COLUMN IF NOT EXISTS reference_assets JSONB NOT NULL DEFAULT '[]'::jsonb")
    op.execute("ALTER TABLE content_packages ADD COLUMN IF NOT EXISTS primary_assets JSONB NOT NULL DEFAULT '[]'::jsonb")
    op.execute("ALTER TABLE content_packages ADD COLUMN IF NOT EXISTS published_assets JSONB NOT NULL DEFAULT '[]'::jsonb")
    op.execute("ALTER TABLE content_packages ADD COLUMN IF NOT EXISTS prompt_id VARCHAR(255)")

    op.execute("ALTER TABLE asset_lineage ADD COLUMN IF NOT EXISTS reference_asset_ids JSONB NOT NULL DEFAULT '[]'::jsonb")
    op.execute("ALTER TABLE asset_lineage ADD COLUMN IF NOT EXISTS origin_episode_id VARCHAR(255)")
    op.execute("ALTER TABLE asset_lineage ADD COLUMN IF NOT EXISTS target_episode_id VARCHAR(255)")
    op.execute("ALTER TABLE asset_lineage ADD COLUMN IF NOT EXISTS origin_platform VARCHAR(120) NOT NULL DEFAULT ''")
    op.execute("ALTER TABLE asset_lineage ADD COLUMN IF NOT EXISTS target_platform VARCHAR(120) NOT NULL DEFAULT ''")
    op.execute("ALTER TABLE asset_lineage ADD COLUMN IF NOT EXISTS reuse_mode VARCHAR(40) NOT NULL DEFAULT 'NONE'")
    op.execute("ALTER TABLE asset_lineage ADD COLUMN IF NOT EXISTS generation_mode VARCHAR(80) NOT NULL DEFAULT ''")
    op.execute("ALTER TABLE asset_lineage ADD COLUMN IF NOT EXISTS tool VARCHAR(80) NOT NULL DEFAULT ''")
    op.execute("ALTER TABLE asset_lineage ADD COLUMN IF NOT EXISTS prompt_id VARCHAR(255)")

    op.create_table(
        "platform_asset_pools",
        sa.Column("pool_id", sa.String(255), primary_key=True),
        sa.Column("account_id", sa.String(255), sa.ForeignKey("platform_accounts.account_id", ondelete="CASCADE"), nullable=False),
        sa.Column("platform", sa.String(120), nullable=False),
        sa.Column("character_id", sa.String(255)),
        sa.Column("world_id", sa.String(255)),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint("account_id", "platform", name="uq_meiti_platform_asset_pool"),
    )
    op.create_index("idx_meiti_platform_asset_pools_account", "platform_asset_pools", ["account_id"])
    op.create_index("idx_meiti_platform_asset_pools_platform", "platform_asset_pools", ["platform"])

    op.create_table(
        "platform_creative_dna",
        sa.Column("dna_id", sa.String(255), primary_key=True),
        sa.Column("account_id", sa.String(255), sa.ForeignKey("platform_accounts.account_id", ondelete="CASCADE"), nullable=False),
        sa.Column("platform", sa.String(120), nullable=False),
        sa.Column("visual_style", JSONB, nullable=False, server_default="{}"),
        sa.Column("copy_style", JSONB, nullable=False, server_default="{}"),
        sa.Column("hook_style", sa.Text(), nullable=False, server_default=""),
        sa.Column("camera_style", sa.Text(), nullable=False, server_default=""),
        sa.Column("motion_style", sa.Text(), nullable=False, server_default=""),
        sa.Column("emotion_style", sa.Text(), nullable=False, server_default=""),
        sa.Column("audience_relationship", sa.Text(), nullable=False, server_default=""),
        sa.Column("cta_style", sa.Text(), nullable=False, server_default=""),
        sa.Column("content_frequency", sa.Text(), nullable=False, server_default=""),
        sa.Column("asset_freshness_policy", sa.String(80), nullable=False, server_default="NEW_PRIMARY_ASSET_REQUIRED"),
        sa.Column("prompt_dna", JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint("account_id", "platform", name="uq_meiti_platform_creative_dna"),
    )
    op.create_index("idx_meiti_platform_creative_dna_account", "platform_creative_dna", ["account_id"])

    op.create_table(
        "prompt_packages",
        sa.Column("prompt_id", sa.String(255), primary_key=True),
        sa.Column("account_id", sa.String(255), sa.ForeignKey("platform_accounts.account_id", ondelete="CASCADE"), nullable=False),
        sa.Column("platform", sa.String(120), nullable=False),
        sa.Column("kind", sa.String(40), nullable=False, server_default="IMAGE"),
        sa.Column("character_id", sa.String(255)),
        sa.Column("world_id", sa.String(255)),
        sa.Column("series_id", sa.String(255)),
        sa.Column("episode_id", sa.String(255)),
        sa.Column("character_lock", sa.Text(), nullable=False, server_default=""),
        sa.Column("world_lock", sa.Text(), nullable=False, server_default=""),
        sa.Column("scene_prompt", sa.Text(), nullable=False, server_default=""),
        sa.Column("visual_style", sa.Text(), nullable=False, server_default=""),
        sa.Column("camera", sa.Text(), nullable=False, server_default=""),
        sa.Column("motion", sa.Text(), nullable=False, server_default=""),
        sa.Column("composition", sa.Text(), nullable=False, server_default=""),
        sa.Column("lighting", sa.Text(), nullable=False, server_default=""),
        sa.Column("negative_prompt", sa.Text(), nullable=False, server_default=""),
        sa.Column("lens", sa.Text(), nullable=False, server_default=""),
        sa.Column("material_texture", sa.Text(), nullable=False, server_default=""),
        sa.Column("authenticity", sa.Text(), nullable=False, server_default=""),
        sa.Column("shot_list", JSONB, nullable=False, server_default="[]"),
        sa.Column("temporal_sequence", sa.Text(), nullable=False, server_default=""),
        sa.Column("camera_movement", sa.Text(), nullable=False, server_default=""),
        sa.Column("character_motion", sa.Text(), nullable=False, server_default=""),
        sa.Column("environment_motion", sa.Text(), nullable=False, server_default=""),
        sa.Column("start_state", sa.Text(), nullable=False, server_default=""),
        sa.Column("end_state", sa.Text(), nullable=False, server_default=""),
        sa.Column("duration", sa.Text(), nullable=False, server_default=""),
        sa.Column("aspect_ratio", sa.Text(), nullable=False, server_default=""),
        sa.Column("copy_ready", sa.Text(), nullable=False, server_default=""),
        sa.Column("reference_assets", JSONB, nullable=False, server_default="[]"),
        sa.Column("source_assets", JSONB, nullable=False, server_default="[]"),
        sa.Column("source_asset_id", sa.String(255)),
        sa.Column("recommended_model", sa.Text(), nullable=False, server_default=""),
        sa.Column("recommended_size", sa.Text(), nullable=False, server_default=""),
        sa.Column("recommended_ratio", sa.Text(), nullable=False, server_default=""),
        sa.Column("recommended_duration", sa.Text(), nullable=False, server_default=""),
        sa.Column("learning_basis", JSONB, nullable=False, server_default="[]"),
        sa.Column("prompt_patterns", JSONB, nullable=False, server_default="[]"),
        sa.Column("lechuang_parameters", JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("idx_meiti_prompt_packages_account", "prompt_packages", ["account_id"])
    op.create_index("idx_meiti_prompt_packages_episode", "prompt_packages", ["episode_id"])
    op.create_index("idx_meiti_prompt_packages_platform", "prompt_packages", ["platform"])

    op.create_table(
        "prompt_patterns",
        sa.Column("pattern_id", sa.String(255), primary_key=True),
        sa.Column("platform", sa.String(120), nullable=False),
        sa.Column("account_id", sa.String(255)),
        sa.Column("category", sa.String(120), nullable=False, server_default=""),
        sa.Column("prompt_fragment", sa.Text(), nullable=False, server_default=""),
        sa.Column("positive_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("negative_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("confidence", sa.Numeric(18, 6), nullable=False, server_default="0"),
        sa.Column("source_episode_ids", JSONB, nullable=False, server_default="[]"),
        sa.Column("global_pattern", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("idx_meiti_prompt_patterns_platform", "prompt_patterns", ["platform"])
    op.create_index("idx_meiti_prompt_patterns_account", "prompt_patterns", ["account_id"])

    op.create_table(
        "platform_learning_profiles",
        sa.Column("profile_id", sa.String(255), primary_key=True),
        sa.Column("account_id", sa.String(255), sa.ForeignKey("platform_accounts.account_id", ondelete="CASCADE"), nullable=False),
        sa.Column("platform", sa.String(120), nullable=False),
        sa.Column("successful_patterns", JSONB, nullable=False, server_default="[]"),
        sa.Column("failed_patterns", JSONB, nullable=False, server_default="[]"),
        sa.Column("high_performance_topics", JSONB, nullable=False, server_default="[]"),
        sa.Column("high_performance_hooks", JSONB, nullable=False, server_default="[]"),
        sa.Column("high_performance_visuals", JSONB, nullable=False, server_default="[]"),
        sa.Column("audience_preferences", JSONB, nullable=False, server_default="[]"),
        sa.Column("avoid_patterns", JSONB, nullable=False, server_default="[]"),
        sa.Column("prompt_patterns", JSONB, nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint("account_id", "platform", name="uq_meiti_platform_learning_profile"),
    )
    op.create_index("idx_meiti_platform_learning_profiles_account", "platform_learning_profiles", ["account_id"])
    op.create_index("idx_meiti_platform_learning_profiles_platform", "platform_learning_profiles", ["platform"])

    op.create_table(
        "content_package_assets",
        sa.Column("mapping_id", sa.String(255), primary_key=True),
        sa.Column("package_id", sa.String(255), nullable=False),
        sa.Column("asset_id", sa.String(255), nullable=False),
        sa.Column("role", sa.String(40), nullable=False, server_default="PRIMARY"),
        sa.Column("selected", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint("package_id", "asset_id", "role", name="uq_meiti_package_asset_role"),
    )
    op.create_index("idx_meiti_content_package_assets_package", "content_package_assets", ["package_id"])
    op.create_index("idx_meiti_content_package_assets_asset", "content_package_assets", ["asset_id"])


def downgrade() -> None:
    op.drop_table("content_package_assets")
    op.drop_table("platform_learning_profiles")
    op.drop_table("prompt_patterns")
    op.drop_table("prompt_packages")
    op.drop_table("platform_creative_dna")
    op.drop_table("platform_asset_pools")
    op.execute("ALTER TABLE asset_lineage DROP COLUMN IF EXISTS prompt_id")
    op.execute("ALTER TABLE asset_lineage DROP COLUMN IF EXISTS tool")
    op.execute("ALTER TABLE asset_lineage DROP COLUMN IF EXISTS generation_mode")
    op.execute("ALTER TABLE asset_lineage DROP COLUMN IF EXISTS reuse_mode")
    op.execute("ALTER TABLE asset_lineage DROP COLUMN IF EXISTS target_platform")
    op.execute("ALTER TABLE asset_lineage DROP COLUMN IF EXISTS origin_platform")
    op.execute("ALTER TABLE asset_lineage DROP COLUMN IF EXISTS target_episode_id")
    op.execute("ALTER TABLE asset_lineage DROP COLUMN IF EXISTS origin_episode_id")
    op.execute("ALTER TABLE asset_lineage DROP COLUMN IF EXISTS reference_asset_ids")
    op.execute("ALTER TABLE content_packages DROP COLUMN IF EXISTS prompt_id")
    op.execute("ALTER TABLE content_packages DROP COLUMN IF EXISTS published_assets")
    op.execute("ALTER TABLE content_packages DROP COLUMN IF EXISTS primary_assets")
    op.execute("ALTER TABLE content_packages DROP COLUMN IF EXISTS reference_assets")
    op.execute("ALTER TABLE episodes DROP COLUMN IF EXISTS prompt_id")
    op.execute("ALTER TABLE episodes DROP COLUMN IF EXISTS primary_asset_id")
    op.execute("ALTER TABLE account_worlds DROP COLUMN IF EXISTS world_dna")
    op.execute("ALTER TABLE account_worlds DROP COLUMN IF EXISTS social_relations")
    op.execute("ALTER TABLE account_worlds DROP COLUMN IF EXISTS lifestyle")
    op.execute("ALTER TABLE account_worlds DROP COLUMN IF EXISTS lighting")
    op.execute("ALTER TABLE account_worlds DROP COLUMN IF EXISTS time_of_day")
    op.execute("ALTER TABLE account_worlds DROP COLUMN IF EXISTS season")
    op.execute("ALTER TABLE account_worlds DROP COLUMN IF EXISTS city")
    op.execute("ALTER TABLE virtual_characters DROP COLUMN IF EXISTS character_dna")
    op.execute("ALTER TABLE virtual_characters DROP COLUMN IF EXISTS continuity_rules")
    op.execute("ALTER TABLE virtual_characters DROP COLUMN IF EXISTS audience_relationship")
    op.execute("ALTER TABLE virtual_characters DROP COLUMN IF EXISTS content_behavior")
    op.execute("ALTER TABLE virtual_characters DROP COLUMN IF EXISTS platform_personality")
    op.execute("ALTER TABLE virtual_characters DROP COLUMN IF EXISTS lighting")
    op.execute("ALTER TABLE virtual_characters DROP COLUMN IF EXISTS photography")
    op.execute("ALTER TABLE virtual_characters DROP COLUMN IF EXISTS accessories")
    op.execute("ALTER TABLE virtual_characters DROP COLUMN IF EXISTS style")
    op.execute("ALTER TABLE virtual_characters DROP COLUMN IF EXISTS speech")
    op.execute("ALTER TABLE virtual_characters DROP COLUMN IF EXISTS behavior")
    op.execute("ALTER TABLE virtual_characters DROP COLUMN IF EXISTS values")
    op.execute("ALTER TABLE virtual_characters DROP COLUMN IF EXISTS location")
    op.execute("ALTER TABLE virtual_characters DROP COLUMN IF EXISTS occupation")
    op.execute("ALTER TABLE virtual_characters DROP COLUMN IF EXISTS derived_from_character_id")
    op.execute("ALTER TABLE media_assets DROP COLUMN IF EXISTS tool")
    op.execute("ALTER TABLE media_assets DROP COLUMN IF EXISTS generation_mode")
    op.execute("ALTER TABLE media_assets DROP COLUMN IF EXISTS source_asset_id")
    op.execute("ALTER TABLE media_assets DROP COLUMN IF EXISTS parent_asset_id")
    op.execute("ALTER TABLE media_assets DROP COLUMN IF EXISTS pool_id")
    op.execute("ALTER TABLE media_assets DROP COLUMN IF EXISTS lifecycle")
    op.execute("ALTER TABLE media_assets DROP COLUMN IF EXISTS asset_role")
    op.execute("ALTER TABLE media_assets DROP COLUMN IF EXISTS scope_type")
    op.execute("ALTER TABLE media_assets DROP COLUMN IF EXISTS platform")
