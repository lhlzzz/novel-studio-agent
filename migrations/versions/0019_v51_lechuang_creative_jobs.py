"""V5.1 Lechuang creative jobs: ProductionRun generation snapshots."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0019_v51_lechuang_creative_jobs"
down_revision = "0018_v50_creator_os_unification"
branch_labels = None
depends_on = None

JSONB = postgresql.JSONB


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
    _add_column("production_runs", sa.Column("creative_provider", sa.String(120), nullable=False, server_default=""))
    _add_column("production_runs", sa.Column("creative_job_id", sa.String(255), nullable=False, server_default=""))
    _add_column("production_runs", sa.Column("creative_model", sa.String(120), nullable=False, server_default=""))
    _add_column("production_runs", sa.Column("creative_request_snapshot", JSONB, nullable=False, server_default="{}"))
    _add_column("production_runs", sa.Column("creative_result_snapshot", JSONB, nullable=False, server_default="{}"))
    op.create_index("idx_meiti_production_runs_creative_job", "production_runs", ["creative_job_id"])


def downgrade() -> None:
    op.drop_index("idx_meiti_production_runs_creative_job", table_name="production_runs")
    for name in (
        "creative_result_snapshot",
        "creative_request_snapshot",
        "creative_model",
        "creative_job_id",
        "creative_provider",
    ):
        op.drop_column("production_runs", name)
