"""V4.8.1 production-ready creator OS: account profile/state, tasks, calendar."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0015_v481_production_ready_creator_os"
down_revision = "0014_v48_production_loop"
branch_labels = None
depends_on = None

JSONB = postgresql.JSONB

TASK_TYPES = (
    "ACCOUNT_SETUP","ACCOUNT_MAINTENANCE","CONTENT_IDEA","CONTENT_PLAN","PROMPT_GENERATION",
    "CREATIVE_EXECUTION","ASSET_IMPORT","QA","PACKAGE","HANDOFF","PUBLISH","ANALYTICS",
    "LEARNING","RESEARCH","REVIEW",
)
TASK_STATES = ("TODO","READY","IN_PROGRESS","WAITING_OPERATOR","WAITING_EXTERNAL","BLOCKED","DONE","CANCELLED")
CALENDAR_STATES = ("PLANNED","READY","PRODUCING","READY_TO_PUBLISH","PUBLISHED","MISSED","CANCELLED")


def _existing_tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    # Alembic's default version_num is VARCHAR(32); this revision id is 39 chars.
    op.execute("ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(64)")
    op.execute("ALTER TABLE platform_accounts ADD COLUMN IF NOT EXISTS series_id VARCHAR(255)")
    op.execute("ALTER TABLE production_runs ADD COLUMN IF NOT EXISTS task_id VARCHAR(255)")
    op.execute("ALTER TABLE analytics_records ADD COLUMN IF NOT EXISTS clicks INTEGER")
    op.execute("ALTER TABLE analytics_records ADD COLUMN IF NOT EXISTS followers_delta INTEGER")
    op.execute("ALTER TABLE analytics_records ADD COLUMN IF NOT EXISTS observed_at VARCHAR(80)")
    op.execute("ALTER TABLE learning_records ADD COLUMN IF NOT EXISTS prompt_id VARCHAR(255)")
    op.execute("ALTER TABLE learning_records ADD COLUMN IF NOT EXISTS asset_id VARCHAR(255)")
    op.execute("ALTER TABLE learning_records ADD COLUMN IF NOT EXISTS evidence_status VARCHAR(40) NOT NULL DEFAULT 'NOT_VERIFIED'")
    op.execute("ALTER TABLE learning_records ADD COLUMN IF NOT EXISTS failure_type TEXT NOT NULL DEFAULT ''")
    op.execute("ALTER TABLE learning_records ADD COLUMN IF NOT EXISTS diagnosis TEXT NOT NULL DEFAULT ''")
    op.execute("ALTER TABLE learning_records ADD COLUMN IF NOT EXISTS root_cause TEXT NOT NULL DEFAULT ''")
    op.execute("ALTER TABLE learning_records ADD COLUMN IF NOT EXISTS evidence_gap TEXT NOT NULL DEFAULT ''")
    op.execute("ALTER TABLE learning_records ADD COLUMN IF NOT EXISTS outcome TEXT NOT NULL DEFAULT ''")

    existing = _existing_tables()

    if "account_profiles" not in existing:
        op.create_table(
            "account_profiles",
            sa.Column("account_id", sa.String(255), sa.ForeignKey("platform_accounts.account_id", ondelete="CASCADE"), primary_key=True),
            sa.Column("platform", sa.String(120), nullable=False),
            sa.Column("display_name", sa.Text(), nullable=False, server_default=""),
            sa.Column("external_account_id", sa.String(255), nullable=False, server_default=""),
            sa.Column("status", sa.String(40), nullable=False, server_default="DRAFT"),
            sa.Column("character_id", sa.String(255)),
            sa.Column("world_id", sa.String(255)),
            sa.Column("series_id", sa.String(255)),
            sa.Column("account_objective", JSONB, nullable=False, server_default="{}"),
            sa.Column("target_audience", JSONB, nullable=False, server_default="{}"),
            sa.Column("positioning", JSONB, nullable=False, server_default="{}"),
            sa.Column("content_pillars", JSONB, nullable=False, server_default="{}"),
            sa.Column("brand_voice", JSONB, nullable=False, server_default="{}"),
            sa.Column("visual_style", JSONB, nullable=False, server_default="{}"),
            sa.Column("content_frequency", JSONB, nullable=False, server_default="{}"),
            sa.Column("preferred_publish_windows", JSONB, nullable=False, server_default="{}"),
            sa.Column("content_formats", JSONB, nullable=False, server_default="{}"),
            sa.Column("operating_rules", JSONB, nullable=False, server_default="{}"),
            sa.Column("forbidden_rules", JSONB, nullable=False, server_default="{}"),
            sa.Column("manual_notes", JSONB, nullable=False, server_default="{}"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        )
        op.create_index("idx_meiti_account_profiles_platform", "account_profiles", ["platform"])

    if "account_operating_states" not in existing:
        op.create_table(
            "account_operating_states",
            sa.Column("account_id", sa.String(255), sa.ForeignKey("platform_accounts.account_id", ondelete="CASCADE"), primary_key=True),
            sa.Column("platform", sa.String(120), nullable=False),
            sa.Column("current_objective", sa.Text(), nullable=False, server_default=""),
            sa.Column("current_priority", sa.String(20), nullable=False, server_default="NORMAL"),
            sa.Column("current_series", sa.String(255)),
            sa.Column("current_episode", sa.String(255)),
            sa.Column("current_task", sa.String(255)),
            sa.Column("current_campaign", sa.String(255)),
            sa.Column("current_strategy", sa.Text(), nullable=False, server_default=""),
            sa.Column("current_content_status", sa.String(40), nullable=False, server_default="IDEA"),
            sa.Column("last_published_episode", sa.String(255)),
            sa.Column("last_generated_asset", sa.String(255)),
            sa.Column("last_learning", sa.String(255)),
            sa.Column("learning_summary", sa.Text(), nullable=False, server_default=""),
            sa.Column("next_action", sa.Text(), nullable=False, server_default=""),
            sa.Column("next_due_at", sa.String(80)),
            sa.Column("paused_until", sa.String(80)),
            sa.Column("operator_notes", sa.Text(), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        )
        op.create_index("idx_meiti_account_operating_states_platform", "account_operating_states", ["platform"])
        op.create_index("idx_meiti_account_operating_states_task", "account_operating_states", ["current_task"])

    if "manual_overrides" not in existing:
        op.create_table(
            "manual_overrides",
            sa.Column("override_id", sa.String(255), primary_key=True),
            sa.Column("account_id", sa.String(255), sa.ForeignKey("platform_accounts.account_id", ondelete="CASCADE"), nullable=False),
            sa.Column("platform", sa.String(120), nullable=False),
            sa.Column("target_kind", sa.String(40), nullable=False),
            sa.Column("target_id", sa.String(255), nullable=False),
            sa.Column("field_name", sa.String(80), nullable=False),
            sa.Column("old_value", JSONB, nullable=False, server_default="{}"),
            sa.Column("new_value", JSONB, nullable=False, server_default="{}"),
            sa.Column("changed_by", sa.String(120), nullable=False, server_default="operator"),
            sa.Column("reason", sa.Text(), nullable=False, server_default=""),
            sa.Column("source", sa.String(40), nullable=False, server_default="USER_OVERRIDE"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        )
        op.create_index("idx_meiti_manual_overrides_account", "manual_overrides", ["account_id"])
        op.create_index("idx_meiti_manual_overrides_target", "manual_overrides", ["target_kind", "target_id"])

    if "creator_tasks" not in existing:
        op.create_table(
            "creator_tasks",
            sa.Column("task_id", sa.String(255), primary_key=True),
            sa.Column("account_id", sa.String(255), sa.ForeignKey("platform_accounts.account_id", ondelete="CASCADE"), nullable=False),
            sa.Column("platform", sa.String(120), nullable=False),
            sa.Column("task_type", sa.String(40), nullable=False),
            sa.Column("title", sa.Text(), nullable=False),
            sa.Column("description", sa.Text(), nullable=False, server_default=""),
            sa.Column("priority", sa.String(20), nullable=False, server_default="NORMAL"),
            sa.Column("status", sa.String(40), nullable=False, server_default="TODO"),
            sa.Column("due_at", sa.String(80)),
            sa.Column("episode_id", sa.String(255)),
            sa.Column("series_id", sa.String(255)),
            sa.Column("prompt_id", sa.String(255)),
            sa.Column("asset_id", sa.String(255)),
            sa.Column("package_id", sa.String(255)),
            sa.Column("production_run_id", sa.String(255)),
            sa.Column("parent_task_id", sa.String(255)),
            sa.Column("next_task_id", sa.String(255)),
            sa.Column("next_task_type", sa.String(40)),
            sa.Column("dependencies", JSONB, nullable=False, server_default="[]"),
            sa.Column("operator_notes", sa.Text(), nullable=False, server_default=""),
            sa.Column("blocked_reason", sa.Text(), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
            sa.Column("completed_at", sa.DateTime()),
            sa.CheckConstraint("task_type IN (" + ",".join(f"'{item}'" for item in TASK_TYPES) + ")", name="ck_meiti_creator_task_type"),
            sa.CheckConstraint("status IN (" + ",".join(f"'{item}'" for item in TASK_STATES) + ")", name="ck_meiti_creator_task_status"),
            sa.CheckConstraint("priority IN ('CRITICAL','HIGH','NORMAL','LOW')", name="ck_meiti_creator_task_priority"),
        )
        op.create_index("idx_meiti_creator_tasks_account", "creator_tasks", ["account_id"])
        op.create_index("idx_meiti_creator_tasks_status", "creator_tasks", ["status"])
        op.create_index("idx_meiti_creator_tasks_due", "creator_tasks", ["due_at"])
        op.create_index("idx_meiti_creator_tasks_episode", "creator_tasks", ["episode_id"])

    if "content_calendar" not in existing:
        op.create_table(
            "content_calendar",
            sa.Column("calendar_id", sa.String(255), primary_key=True),
            sa.Column("account_id", sa.String(255), sa.ForeignKey("platform_accounts.account_id", ondelete="CASCADE"), nullable=False),
            sa.Column("platform", sa.String(120), nullable=False),
            sa.Column("date", sa.String(40), nullable=False),
            sa.Column("slot", sa.String(40), nullable=False, server_default="default"),
            sa.Column("episode_id", sa.String(255)),
            sa.Column("task_id", sa.String(255)),
            sa.Column("status", sa.String(40), nullable=False, server_default="PLANNED"),
            sa.Column("topic", sa.Text(), nullable=False, server_default=""),
            sa.Column("format", sa.String(40), nullable=False, server_default="image"),
            sa.Column("priority", sa.String(20), nullable=False, server_default="NORMAL"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
            sa.UniqueConstraint("account_id", "date", "slot", name="uq_meiti_content_calendar_slot"),
            sa.CheckConstraint("status IN (" + ",".join(f"'{item}'" for item in CALENDAR_STATES) + ")", name="ck_meiti_content_calendar_status"),
        )
        op.create_index("idx_meiti_content_calendar_account", "content_calendar", ["account_id"])
        op.create_index("idx_meiti_content_calendar_date", "content_calendar", ["date"])

    if "production_readiness_records" not in existing:
        op.create_table(
            "production_readiness_records",
            sa.Column("record_id", sa.String(255), primary_key=True),
            sa.Column("account_id", sa.String(255)),
            sa.Column("platform", sa.String(120), nullable=False, server_default=""),
            sa.Column("core_production", sa.String(40), nullable=False, server_default="NOT_CONFIGURED"),
            sa.Column("post_production", sa.String(40), nullable=False, server_default="NOT_VERIFIED"),
            sa.Column("full_loop", sa.String(40), nullable=False, server_default="NOT_VERIFIED"),
            sa.Column("checks", JSONB, nullable=False, server_default="{}"),
            sa.Column("detail", JSONB, nullable=False, server_default="{}"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        )
        op.create_index("idx_meiti_production_readiness_account", "production_readiness_records", ["account_id"])


def downgrade() -> None:
    for table in (
        "production_readiness_records",
        "content_calendar",
        "creator_tasks",
        "manual_overrides",
        "account_operating_states",
        "account_profiles",
    ):
        op.drop_table(table)
    op.execute("ALTER TABLE learning_records DROP COLUMN IF EXISTS outcome")
    op.execute("ALTER TABLE learning_records DROP COLUMN IF EXISTS evidence_gap")
    op.execute("ALTER TABLE learning_records DROP COLUMN IF EXISTS root_cause")
    op.execute("ALTER TABLE learning_records DROP COLUMN IF EXISTS diagnosis")
    op.execute("ALTER TABLE learning_records DROP COLUMN IF EXISTS failure_type")
    op.execute("ALTER TABLE learning_records DROP COLUMN IF EXISTS evidence_status")
    op.execute("ALTER TABLE learning_records DROP COLUMN IF EXISTS asset_id")
    op.execute("ALTER TABLE learning_records DROP COLUMN IF EXISTS prompt_id")
    op.execute("ALTER TABLE analytics_records DROP COLUMN IF EXISTS observed_at")
    op.execute("ALTER TABLE analytics_records DROP COLUMN IF EXISTS followers_delta")
    op.execute("ALTER TABLE analytics_records DROP COLUMN IF EXISTS clicks")
    op.execute("ALTER TABLE production_runs DROP COLUMN IF EXISTS task_id")
    op.execute("ALTER TABLE platform_accounts DROP COLUMN IF EXISTS series_id")
