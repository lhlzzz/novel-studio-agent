"""Durable creative runtime tables."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

revision = "0004_creative_runtime"
down_revision = "0003_attempt_metadata"
branch_labels = None
depends_on = None

JSONB = postgresql.JSONB


def upgrade() -> None:
    existing = set(inspect(op.get_bind()).get_table_names())
    if "creative_runs" in existing and "creative_workflows" in existing:
        return
    op.create_table(
        "creative_workflows",
        sa.Column("workflow_id", sa.String(255), primary_key=True),
        sa.Column("version", sa.String(80), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False, server_default=""),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("category", sa.String(80), nullable=False, server_default="video"),
        sa.Column("inputs", JSONB, nullable=False, server_default="{}"),
        sa.Column("nodes", JSONB, nullable=False, server_default="[]"),
        sa.Column("edges", JSONB, nullable=False, server_default="[]"),
        sa.Column("variables", JSONB, nullable=False, server_default="{}"),
        sa.Column("quality_policy", JSONB, nullable=False, server_default="{}"),
        sa.Column("outputs", JSONB, nullable=False, server_default="{}"),
        sa.Column("snapshot", JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_table(
        "creative_runs",
        sa.Column("run_id", sa.String(255), primary_key=True),
        sa.Column("workflow_id", sa.String(255), nullable=False),
        sa.Column("workflow_version", sa.String(80), nullable=False),
        sa.Column("status", sa.String(40), nullable=False, server_default="DRAFT"),
        sa.Column("inputs", JSONB, nullable=False, server_default="{}"),
        sa.Column("outputs", JSONB, nullable=False, server_default="{}"),
        sa.Column("estimated_cost", sa.Numeric(18, 6), nullable=False, server_default="0"),
        sa.Column("actual_cost", sa.Numeric(18, 6), nullable=False, server_default="0"),
        sa.Column("budget", sa.Numeric(18, 6)),
        sa.Column("idempotency_key", sa.String(255), unique=True),
        sa.Column("replay_of", sa.String(255)),
        sa.Column("cursor", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("node_outputs", JSONB, nullable=False, server_default="{}"),
        sa.Column("judge_results", JSONB, nullable=False, server_default="[]"),
        sa.Column("quality", JSONB, nullable=False, server_default="{}"),
        sa.Column("error", sa.Text()),
        sa.Column("error_code", sa.String(80)),
        sa.Column("workflow_snapshot", JSONB, nullable=False, server_default="{}"),
        sa.Column("asset_ids", JSONB, nullable=False, server_default="[]"),
        sa.Column("task_ids", JSONB, nullable=False, server_default="[]"),
        sa.Column("selected_asset_id", sa.String(255)),
        sa.Column("selection_reason", sa.Text()),
        sa.Column("selection_score", sa.Numeric(18, 6)),
        sa.Column("worker_id", sa.String(255)),
        sa.Column("lease_until", sa.DateTime()),
        sa.Column("heartbeat_at", sa.DateTime()),
        sa.Column("request_id", sa.String(255), nullable=False, server_default=""),
        sa.Column("started_at", sa.DateTime()),
        sa.Column("completed_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("idx_creative_runs_status", "creative_runs", ["status"])
    op.create_index("idx_creative_runs_workflow", "creative_runs", ["workflow_id", "workflow_version"])
    op.create_index("idx_creative_runs_lease", "creative_runs", ["lease_until"])
    op.create_table(
        "creative_tasks",
        sa.Column("task_id", sa.String(255), primary_key=True),
        sa.Column("run_id", sa.String(255), sa.ForeignKey("creative_runs.run_id", ondelete="CASCADE"), nullable=False),
        sa.Column("node_id", sa.String(255), nullable=False),
        sa.Column("provider", sa.String(120), nullable=False),
        sa.Column("provider_task_id", sa.String(255), nullable=False, server_default=""),
        sa.Column("kind", sa.String(80), nullable=False, server_default=""),
        sa.Column("status", sa.String(40), nullable=False, server_default="QUEUED"),
        sa.Column("payload", JSONB, nullable=False, server_default="{}"),
        sa.Column("result", JSONB, nullable=False, server_default="{}"),
        sa.Column("poll_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("execution_key", sa.String(255), nullable=False, server_default=""),
        sa.Column("error", sa.Text()),
        sa.Column("started_at", sa.DateTime()),
        sa.Column("completed_at", sa.DateTime()),
        sa.Column("timeout_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint("execution_key", name="uq_creative_task_execution"),
    )
    op.create_index("idx_creative_tasks_run", "creative_tasks", ["run_id"])
    op.create_index("idx_creative_tasks_status", "creative_tasks", ["status"])
    op.create_index("idx_creative_tasks_provider_task", "creative_tasks", ["provider_task_id"])
    op.create_table(
        "creative_node_outputs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.String(255), sa.ForeignKey("creative_runs.run_id", ondelete="CASCADE"), nullable=False),
        sa.Column("node_id", sa.String(255), nullable=False),
        sa.Column("output", JSONB, nullable=False, server_default="{}"),
        sa.Column("assets", JSONB, nullable=False, server_default="[]"),
        sa.Column("timestamp", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint("run_id", "node_id", name="uq_creative_node_output"),
    )
    op.create_index("idx_creative_node_outputs_run", "creative_node_outputs", ["run_id"])
    op.create_table(
        "media_assets",
        sa.Column("asset_id", sa.String(255), primary_key=True),
        sa.Column("sha256", sa.String(64), nullable=False, unique=True),
        sa.Column("type", sa.String(40), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("mime_type", sa.String(120), nullable=False, server_default=""),
        sa.Column("size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("width", sa.Integer()),
        sa.Column("height", sa.Integer()),
        sa.Column("duration", sa.Numeric(18, 6)),
        sa.Column("fps", sa.Numeric(18, 6)),
        sa.Column("workflow_id", sa.String(255)),
        sa.Column("workflow_version", sa.String(80)),
        sa.Column("creative_run_id", sa.String(255)),
        sa.Column("prompt_id", sa.String(255)),
        sa.Column("character_id", sa.String(255)),
        sa.Column("metadata", JSONB, nullable=False, server_default="{}"),
        sa.Column("technical_score", sa.Numeric(18, 6)),
        sa.Column("visual_score", sa.Numeric(18, 6)),
        sa.Column("content_score", sa.Numeric(18, 6)),
        sa.Column("platform_score", sa.Numeric(18, 6)),
        sa.Column("overall_score", sa.Numeric(18, 6)),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("idx_media_assets_run", "media_assets", ["creative_run_id"])
    op.create_index("idx_media_assets_type", "media_assets", ["type"])
    op.create_table(
        "characters",
        sa.Column("character_id", sa.String(255), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("visual_dna", JSONB, nullable=False, server_default="{}"),
        sa.Column("behavior_dna", sa.Text(), nullable=False, server_default=""),
        sa.Column("style_dna", sa.Text(), nullable=False, server_default=""),
        sa.Column("reference_assets", JSONB, nullable=False, server_default="[]"),
        sa.Column("voice_assets", JSONB, nullable=False, server_default="[]"),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_table(
        "prompt_assets",
        sa.Column("prompt_id", sa.String(255), primary_key=True),
        sa.Column("version", sa.String(80), nullable=False, server_default="v1"),
        sa.Column("family_id", sa.String(255), nullable=False, server_default=""),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("negative_prompt", sa.Text(), nullable=False, server_default=""),
        sa.Column("references", JSONB, nullable=False, server_default="[]"),
        sa.Column("model", sa.String(120), nullable=False, server_default=""),
        sa.Column("provider", sa.String(120), nullable=False, server_default=""),
        sa.Column("parameters", JSONB, nullable=False, server_default="{}"),
        sa.Column("workflow_id", sa.String(255), nullable=False, server_default=""),
        sa.Column("workflow_version", sa.String(80), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("idx_prompt_assets_family", "prompt_assets", ["family_id"])
    op.create_index("idx_prompt_assets_workflow", "prompt_assets", ["workflow_id", "workflow_version"])
    op.create_table(
        "generation_usage",
        sa.Column("usage_id", sa.String(255), primary_key=True),
        sa.Column("provider", sa.String(120), nullable=False),
        sa.Column("model", sa.String(120), nullable=False, server_default=""),
        sa.Column("task", sa.String(80), nullable=False),
        sa.Column("input", JSONB, nullable=False, server_default="{}"),
        sa.Column("output", JSONB, nullable=False, server_default="{}"),
        sa.Column("credits_estimated", sa.Numeric(18, 6), nullable=False, server_default="0"),
        sa.Column("credits_actual", sa.Numeric(18, 6), nullable=False, server_default="0"),
        sa.Column("status", sa.String(40), nullable=False, server_default=""),
        sa.Column("timestamp", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("run_id", sa.String(255), nullable=False, server_default=""),
        sa.Column("node_id", sa.String(255), nullable=False, server_default=""),
    )
    op.create_index("idx_generation_usage_run", "generation_usage", ["run_id"])
    op.create_index("idx_generation_usage_provider", "generation_usage", ["provider"])
    op.create_table(
        "workflow_performance",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("workflow_id", sa.String(255), nullable=False),
        sa.Column("version", sa.String(80), nullable=False),
        sa.Column("run_id", sa.String(255), nullable=False, server_default=""),
        sa.Column("asset_id", sa.String(255), nullable=False, server_default=""),
        sa.Column("publication_id", sa.String(255), nullable=False, server_default=""),
        sa.Column("platform", sa.String(80), nullable=False, server_default=""),
        sa.Column("provider", sa.String(120), nullable=False, server_default=""),
        sa.Column("model", sa.String(120), nullable=False, server_default=""),
        sa.Column("character", sa.String(255), nullable=False, server_default=""),
        sa.Column("scene", sa.Text(), nullable=False, server_default=""),
        sa.Column("motion", sa.Text(), nullable=False, server_default=""),
        sa.Column("camera", sa.Text(), nullable=False, server_default=""),
        sa.Column("duration", sa.Numeric(18, 6)),
        sa.Column("quality_score", sa.Numeric(18, 6)),
        sa.Column("engagement", sa.Numeric(18, 6)),
        sa.Column("conversion", sa.Numeric(18, 6)),
        sa.Column("cost", sa.Numeric(18, 6)),
        sa.Column("latency", sa.Numeric(18, 6)),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("idx_workflow_performance_workflow", "workflow_performance", ["workflow_id", "version"])
    op.create_index("idx_workflow_performance_run", "workflow_performance", ["run_id"])
    op.create_table(
        "judge_results",
        sa.Column("judge_id", sa.String(255), primary_key=True),
        sa.Column("asset_id", sa.String(255)),
        sa.Column("creative_run_id", sa.String(255), nullable=False, server_default=""),
        sa.Column("judge_type", sa.String(80), nullable=False),
        sa.Column("judge_provider", sa.String(120), nullable=False, server_default=""),
        sa.Column("judge_model", sa.String(120), nullable=False, server_default=""),
        sa.Column("judge_version", sa.String(80), nullable=False, server_default=""),
        sa.Column("score", sa.Numeric(18, 6), nullable=False, server_default="0"),
        sa.Column("breakdown", JSONB, nullable=False, server_default="{}"),
        sa.Column("reasons", JSONB, nullable=False, server_default="[]"),
        sa.Column("decision", sa.String(40), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("idx_judge_results_run", "judge_results", ["creative_run_id"])
    op.create_index("idx_judge_results_asset", "judge_results", ["asset_id"])
    op.create_table(
        "creative_events",
        sa.Column("event_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.String(255), nullable=False, server_default=""),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("payload", JSONB, nullable=False, server_default="{}"),
        sa.Column("timestamp", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("idx_creative_events_run", "creative_events", ["run_id"])
    op.create_index("idx_creative_events_type", "creative_events", ["event_type"])


def downgrade() -> None:
    for table in (
        "creative_events",
        "judge_results",
        "workflow_performance",
        "generation_usage",
        "prompt_assets",
        "characters",
        "media_assets",
        "creative_node_outputs",
        "creative_tasks",
        "creative_runs",
        "creative_workflows",
    ):
        op.drop_table(table)
