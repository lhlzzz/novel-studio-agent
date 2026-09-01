"""Creative run block reasons and per-call cost fields."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0005_v42_hardening"
down_revision = "0004_creative_runtime"
branch_labels = None
depends_on = None


def _columns(table: str) -> set[str]:
    bind = op.get_bind()
    inspector = inspect(bind)
    if table not in inspector.get_table_names():
        return set()
    return {item["name"] for item in inspector.get_columns(table)}


def upgrade() -> None:
    run_cols = _columns("creative_runs")
    if run_cols:
        if "blocked_reason" not in run_cols:
            op.add_column("creative_runs", sa.Column("blocked_reason", sa.String(80)))
        if "blocked_message" not in run_cols:
            op.add_column("creative_runs", sa.Column("blocked_message", sa.Text()))
        if "blocked_at" not in run_cols:
            op.add_column("creative_runs", sa.Column("blocked_at", sa.DateTime()))
        if "retryable" not in run_cols:
            op.add_column("creative_runs", sa.Column("retryable", sa.Boolean(), nullable=False, server_default=sa.false()))
    usage_cols = _columns("generation_usage")
    if usage_cols:
        if "input_units" not in usage_cols:
            op.add_column("generation_usage", sa.Column("input_units", sa.Numeric(18, 6), nullable=False, server_default="0"))
        if "output_units" not in usage_cols:
            op.add_column("generation_usage", sa.Column("output_units", sa.Numeric(18, 6), nullable=False, server_default="0"))
        if "duration_ms" not in usage_cols:
            op.add_column("generation_usage", sa.Column("duration_ms", sa.Numeric(18, 6), nullable=False, server_default="0"))
        if "estimated_cost" not in usage_cols:
            op.add_column("generation_usage", sa.Column("estimated_cost", sa.Numeric(18, 6), nullable=False, server_default="0"))
        if "actual_cost" not in usage_cols:
            op.add_column("generation_usage", sa.Column("actual_cost", sa.Numeric(18, 6), nullable=False, server_default="0"))


def downgrade() -> None:
    run_cols = _columns("creative_runs")
    for name in ("retryable", "blocked_at", "blocked_message", "blocked_reason"):
        if name in run_cols:
            op.drop_column("creative_runs", name)
    usage_cols = _columns("generation_usage")
    for name in ("actual_cost", "estimated_cost", "duration_ms", "output_units", "input_units"):
        if name in usage_cols:
            op.drop_column("generation_usage", name)
