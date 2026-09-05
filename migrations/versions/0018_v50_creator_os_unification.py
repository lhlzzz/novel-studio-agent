"""V5.0 Creator OS unification: CreatorAccount, strategy, state, decision, memory."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0018_v50_creator_os_unification"
down_revision = "0017_v483_production_integrity"
branch_labels = None
depends_on = None

JSONB = postgresql.JSONB


def _existing_tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _existing_columns(table: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table not in inspector.get_table_names():
        return set()
    return {column["name"] for column in inspector.get_columns(table)}


def _add_column(table: str, column: sa.Column) -> None:
    if column.name not in _existing_columns(table):
        op.add_column(table, column)


def upgrade() -> None:
    op.execute("ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(64)")
    _add_column("platform_accounts", sa.Column("account_name", sa.Text(), nullable=False, server_default=""))
    _add_column("platform_accounts", sa.Column("current_strategy_id", sa.String(255)))
    _add_column("platform_accounts", sa.Column("current_strategy_version", sa.Integer()))
    _add_column("platform_accounts", sa.Column("current_episode_id", sa.String(255)))
    _add_column("platform_accounts", sa.Column("current_phase", sa.Text(), nullable=False, server_default=""))
    _add_column("platform_accounts", sa.Column("current_objective", sa.Text(), nullable=False, server_default=""))
    _add_column("platform_accounts", sa.Column("current_next_action", sa.Text(), nullable=False, server_default=""))
    _add_column("platform_accounts", sa.Column("identity_payload", JSONB, nullable=False, server_default="{}"))
    op.execute("UPDATE platform_accounts SET account_name = display_name WHERE account_name IS NULL OR account_name = ''")
    op.execute(
        "DO $$ BEGIN "
        "ALTER TABLE platform_accounts DROP CONSTRAINT IF EXISTS ck_meiti_platform_account_status; "
        "ALTER TABLE platform_accounts ADD CONSTRAINT ck_meiti_platform_account_status "
        "CHECK (status IN ('DRAFT','ACTIVE','PAUSED','DISABLED','ARCHIVED')); "
        "END $$;"
    )

    for name, col in (
        ("series_goal", sa.Column("series_goal", sa.Text(), nullable=False, server_default="")),
        ("series_theme", sa.Column("series_theme", sa.Text(), nullable=False, server_default="")),
        ("series_arc", sa.Column("series_arc", sa.Text(), nullable=False, server_default="")),
        ("current_phase", sa.Column("current_phase", sa.Text(), nullable=False, server_default="")),
        ("phase_goal", sa.Column("phase_goal", sa.Text(), nullable=False, server_default="")),
        ("next_direction_candidates", sa.Column("next_direction_candidates", JSONB, nullable=False, server_default="[]")),
        ("completion_condition", sa.Column("completion_condition", sa.Text(), nullable=False, server_default="")),
    ):
        _add_column("content_series", col)

    for col in (
        sa.Column("strategy_id", sa.String(255)),
        sa.Column("strategy_version", sa.Integer()),
        sa.Column("creator_state_id", sa.String(255)),
        sa.Column("content_decision_id", sa.String(255)),
        sa.Column("creator_state_snapshot", JSONB, nullable=False, server_default="{}"),
        sa.Column("novelty_snapshot", JSONB, nullable=False, server_default="{}"),
        sa.Column("portfolio_snapshot", JSONB, nullable=False, server_default="{}"),
    ):
        _add_column("episodes", col)

    for col in (
        sa.Column("strategy_basis", JSONB, nullable=False, server_default="[]"),
        sa.Column("decision_basis", JSONB, nullable=False, server_default="[]"),
        sa.Column("novelty_basis", JSONB, nullable=False, server_default="[]"),
        sa.Column("continuity_basis", JSONB, nullable=False, server_default="[]"),
    ):
        _add_column("prompt_packages", col)

    for col in (
        sa.Column("strategy_id", sa.String(255)),
        sa.Column("creator_state_id", sa.String(255)),
        sa.Column("content_decision_id", sa.String(255)),
    ):
        _add_column("production_runs", col)

    _add_column("content_packages", sa.Column("content_decision_id", sa.String(255)))
    _add_column("learning_records", sa.Column("learning_status", sa.String(40), nullable=False, server_default=""))
    op.execute(
        "UPDATE learning_records SET learning_status = evidence_status "
        "WHERE learning_status IS NULL OR learning_status = ''"
    )
    op.execute(
        "DO $$ BEGIN "
        "ALTER TABLE learning_records DROP CONSTRAINT IF EXISTS ck_meiti_learning_evidence_status; "
        "ALTER TABLE learning_records ADD CONSTRAINT ck_meiti_learning_evidence_status "
        "CHECK (evidence_status IN ("
        "'OBSERVATION','PENDING','VERIFIED','REJECTED','SUPERSEDED','NOT_ENOUGH_EVIDENCE','NOT_VERIFIED'"
        ")); "
        "END $$;"
    )

    existing = _existing_tables()
    if "platform_connections" not in existing:
        op.create_table(
            "platform_connections",
            sa.Column("connection_id", sa.String(255), primary_key=True),
            sa.Column("creator_account_id", sa.String(255), sa.ForeignKey("platform_accounts.account_id", ondelete="CASCADE"), nullable=False),
            sa.Column("platform", sa.String(120), nullable=False),
            sa.Column("provider", sa.String(120), nullable=False, server_default=""),
            sa.Column("external_account_id", sa.String(255), nullable=False, server_default=""),
            sa.Column("connection_status", sa.String(40), nullable=False, server_default="NOT_CONNECTED"),
            sa.Column("credential_ref", sa.String(255), nullable=False, server_default=""),
            sa.Column("social_account_id", sa.String(255)),
            sa.Column("verified_capabilities", JSONB, nullable=False, server_default="[]"),
            sa.Column("last_verified_at", sa.DateTime()),
            sa.Column("blocked_reason", sa.Text(), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        )
        op.create_index("idx_meiti_platform_connections_account", "platform_connections", ["creator_account_id"])
        op.create_index("idx_meiti_platform_connections_platform", "platform_connections", ["platform"])
        op.create_unique_constraint("uq_meiti_platform_connection", "platform_connections", ["creator_account_id", "platform"])
        op.execute(
            "INSERT INTO platform_connections ("
            "connection_id, creator_account_id, platform, provider, external_account_id, "
            "connection_status, credential_ref, social_account_id, created_at, updated_at"
            ") SELECT "
            "'conn-' || account_id, account_id, platform, COALESCE(NULLIF(platform, ''), 'unknown'), "
            "COALESCE(external_account_id, ''), "
            "CASE WHEN COALESCE(social_account_id, '') <> '' OR COALESCE(credential_ref, '') <> '' "
            "THEN 'CONNECTED' ELSE 'NOT_CONNECTED' END, "
            "COALESCE(credential_ref, ''), social_account_id, NOW(), NOW() "
            "FROM platform_accounts "
            "ON CONFLICT DO NOTHING"
        )

    if "creator_strategies" not in existing:
        op.create_table(
            "creator_strategies",
            sa.Column("strategy_id", sa.String(255), primary_key=True),
            sa.Column("creator_account_id", sa.String(255), sa.ForeignKey("platform_accounts.account_id", ondelete="CASCADE"), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("objective", sa.Text(), nullable=False, server_default=""),
            sa.Column("positioning", sa.Text(), nullable=False, server_default=""),
            sa.Column("audience", sa.Text(), nullable=False, server_default=""),
            sa.Column("content_pillars", JSONB, nullable=False, server_default="[]"),
            sa.Column("pillar_weights", JSONB, nullable=False, server_default="{}"),
            sa.Column("content_mix", JSONB, nullable=False, server_default="{}"),
            sa.Column("growth_goal", sa.Text(), nullable=False, server_default=""),
            sa.Column("commercial_goal", sa.Text(), nullable=False, server_default=""),
            sa.Column("experimentation_policy", sa.Text(), nullable=False, server_default=""),
            sa.Column("continuity_policy", sa.Text(), nullable=False, server_default=""),
            sa.Column("visual_policy", sa.Text(), nullable=False, server_default=""),
            sa.Column("copy_policy", sa.Text(), nullable=False, server_default=""),
            sa.Column("quality_bar", sa.Text(), nullable=False, server_default=""),
            sa.Column("status", sa.String(40), nullable=False, server_default="ACTIVE"),
            sa.Column("reason", sa.Text(), nullable=False, server_default=""),
            sa.Column("effective_from", sa.String(80)),
            sa.Column("effective_until", sa.String(80)),
            sa.Column("supersedes_strategy_id", sa.String(255)),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        )
        op.create_index("idx_meiti_creator_strategies_account", "creator_strategies", ["creator_account_id"])
        op.create_index("idx_meiti_creator_strategies_status", "creator_strategies", ["status"])
        op.create_unique_constraint("uq_meiti_creator_strategy_version", "creator_strategies", ["creator_account_id", "version"])

    if "strategy_revisions" not in existing:
        op.create_table(
            "strategy_revisions",
            sa.Column("revision_id", sa.String(255), primary_key=True),
            sa.Column("strategy_id", sa.String(255), nullable=False),
            sa.Column("creator_account_id", sa.String(255), sa.ForeignKey("platform_accounts.account_id", ondelete="CASCADE"), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False),
            sa.Column("why_changed", sa.Text(), nullable=False, server_default=""),
            sa.Column("old_strategy", JSONB, nullable=False, server_default="{}"),
            sa.Column("new_strategy", JSONB, nullable=False, server_default="{}"),
            sa.Column("changed_by", sa.String(120), nullable=False, server_default="operator"),
            sa.Column("supersedes_strategy_id", sa.String(255)),
            sa.Column("effective_from", sa.String(80)),
            sa.Column("changed_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        )
        op.create_index("idx_meiti_strategy_revisions_account", "strategy_revisions", ["creator_account_id"])
        op.create_index("idx_meiti_strategy_revisions_strategy", "strategy_revisions", ["strategy_id"])

    if "creator_states" not in existing:
        op.create_table(
            "creator_states",
            sa.Column("state_id", sa.String(255), primary_key=True),
            sa.Column("creator_account_id", sa.String(255), sa.ForeignKey("platform_accounts.account_id", ondelete="CASCADE"), nullable=False),
            sa.Column("current_phase", sa.Text(), nullable=False, server_default=""),
            sa.Column("current_objective", sa.Text(), nullable=False, server_default=""),
            sa.Column("current_focus", sa.Text(), nullable=False, server_default=""),
            sa.Column("current_series", sa.String(255)),
            sa.Column("current_episode", sa.String(255)),
            sa.Column("current_content_mix", JSONB, nullable=False, server_default="{}"),
            sa.Column("recent_topics", JSONB, nullable=False, server_default="[]"),
            sa.Column("saturated_topics", JSONB, nullable=False, server_default="[]"),
            sa.Column("underused_topics", JSONB, nullable=False, server_default="[]"),
            sa.Column("current_strategy_id", sa.String(255)),
            sa.Column("current_strategy_version", sa.Integer()),
            sa.Column("current_character_version", sa.Integer()),
            sa.Column("current_world_version", sa.Integer()),
            sa.Column("last_production_at", sa.String(80)),
            sa.Column("last_production_episode_id", sa.String(255)),
            sa.Column("next_recommended_direction", sa.Text(), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        )
        op.create_index("idx_meiti_creator_states_account", "creator_states", ["creator_account_id"])
        op.create_unique_constraint("uq_meiti_creator_state_account", "creator_states", ["creator_account_id"])

    if "content_decisions" not in existing:
        op.create_table(
            "content_decisions",
            sa.Column("decision_id", sa.String(255), primary_key=True),
            sa.Column("account_id", sa.String(255), sa.ForeignKey("platform_accounts.account_id", ondelete="CASCADE"), nullable=False),
            sa.Column("platform", sa.String(120), nullable=False),
            sa.Column("strategy_id", sa.String(255)),
            sa.Column("creator_state_id", sa.String(255)),
            sa.Column("previous_episode_id", sa.String(255)),
            sa.Column("selected_pillar", sa.Text(), nullable=False, server_default=""),
            sa.Column("selected_topic", sa.Text(), nullable=False, server_default=""),
            sa.Column("selected_angle", sa.Text(), nullable=False, server_default=""),
            sa.Column("selected_format", sa.String(40), nullable=False, server_default="image"),
            sa.Column("selected_scene", sa.Text(), nullable=False, server_default=""),
            sa.Column("selected_emotion", sa.Text(), nullable=False, server_default=""),
            sa.Column("selected_hook", sa.Text(), nullable=False, server_default=""),
            sa.Column("idea_decision", sa.String(20), nullable=False, server_default="ACCEPT"),
            sa.Column("reasoning", sa.Text(), nullable=False, server_default=""),
            sa.Column("constraints", JSONB, nullable=False, server_default="[]"),
            sa.Column("avoids", JSONB, nullable=False, server_default="[]"),
            sa.Column("expected_effect", sa.Text(), nullable=False, server_default=""),
            sa.Column("confidence", sa.Numeric(18, 6), nullable=False, server_default="0.5"),
            sa.Column("user_request", sa.Text(), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        )
        op.create_index("idx_meiti_content_decisions_account", "content_decisions", ["account_id"])
        op.create_index("idx_meiti_content_decisions_strategy", "content_decisions", ["strategy_id"])

    if "content_portfolio_items" not in existing:
        op.create_table(
            "content_portfolio_items",
            sa.Column("item_id", sa.String(255), primary_key=True),
            sa.Column("account_id", sa.String(255), sa.ForeignKey("platform_accounts.account_id", ondelete="CASCADE"), nullable=False),
            sa.Column("pillar", sa.Text(), nullable=False, server_default=""),
            sa.Column("topic", sa.Text(), nullable=False, server_default=""),
            sa.Column("format", sa.String(40), nullable=False, server_default="image"),
            sa.Column("scene", sa.Text(), nullable=False, server_default=""),
            sa.Column("emotion", sa.Text(), nullable=False, server_default=""),
            sa.Column("angle", sa.Text(), nullable=False, server_default=""),
            sa.Column("hook", sa.Text(), nullable=False, server_default=""),
            sa.Column("series_id", sa.String(255)),
            sa.Column("episode_id", sa.String(255)),
            sa.Column("date", sa.String(40), nullable=False, server_default=""),
            sa.Column("status", sa.String(40), nullable=False, server_default="IDEA"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        )
        op.create_index("idx_meiti_content_portfolio_account", "content_portfolio_items", ["account_id"])
        op.create_index("idx_meiti_content_portfolio_date", "content_portfolio_items", ["date"])
        op.create_index("idx_meiti_content_portfolio_episode", "content_portfolio_items", ["episode_id"])

    if "production_memories" not in existing:
        op.create_table(
            "production_memories",
            sa.Column("memory_id", sa.String(255), primary_key=True),
            sa.Column("account_id", sa.String(255), sa.ForeignKey("platform_accounts.account_id", ondelete="CASCADE"), nullable=False),
            sa.Column("platform", sa.String(120), nullable=False),
            sa.Column("status", sa.String(40), nullable=False, server_default="CURRENT"),
            sa.Column("strategy_id", sa.String(255)),
            sa.Column("creator_state_id", sa.String(255)),
            sa.Column("episode_id", sa.String(255)),
            sa.Column("decision_id", sa.String(255)),
            sa.Column("prompt_id", sa.String(255)),
            sa.Column("character_id", sa.String(255)),
            sa.Column("world_id", sa.String(255)),
            sa.Column("series_id", sa.String(255)),
            sa.Column("scene", sa.Text(), nullable=False, server_default=""),
            sa.Column("asset_id", sa.String(255)),
            sa.Column("visual_direction", sa.Text(), nullable=False, server_default=""),
            sa.Column("copy_direction", sa.Text(), nullable=False, server_default=""),
            sa.Column("what_was_produced", sa.Text(), nullable=False, server_default=""),
            sa.Column("what_changed", sa.Text(), nullable=False, server_default=""),
            sa.Column("what_worked", sa.Text(), nullable=False, server_default=""),
            sa.Column("what_failed", sa.Text(), nullable=False, server_default=""),
            sa.Column("what_should_continue", sa.Text(), nullable=False, server_default=""),
            sa.Column("what_should_not_repeat", sa.Text(), nullable=False, server_default=""),
            sa.Column("next_direction", sa.Text(), nullable=False, server_default=""),
            sa.Column("confidence", sa.Numeric(18, 6), nullable=False, server_default="0.5"),
            sa.Column("importance", sa.Numeric(18, 6), nullable=False, server_default="0.5"),
            sa.Column("effective_from", sa.String(80)),
            sa.Column("expires_at", sa.String(80)),
            sa.Column("supersedes_id", sa.String(255)),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        )
        op.create_index("idx_meiti_production_memories_account", "production_memories", ["account_id"])
        op.create_index("idx_meiti_production_memories_episode", "production_memories", ["episode_id"])
        op.create_index("idx_meiti_production_memories_status", "production_memories", ["status"])


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS production_memories")
    op.execute("DROP TABLE IF EXISTS content_portfolio_items")
    op.execute("DROP TABLE IF EXISTS content_decisions")
    op.execute("DROP TABLE IF EXISTS creator_states")
    op.execute("DROP TABLE IF EXISTS strategy_revisions")
    op.execute("DROP TABLE IF EXISTS creator_strategies")
    op.execute("DROP TABLE IF EXISTS platform_connections")
