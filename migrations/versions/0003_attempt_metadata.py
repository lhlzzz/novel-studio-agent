"""Add retry audit metadata required by the V3.4 attempt contract."""

from alembic import op
import sqlalchemy as sa

revision = "0003_attempt_metadata"
down_revision = "0002_v34_production"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("distribution_jobs", sa.Column("last_attempt_at", sa.DateTime()))


def downgrade() -> None:
    op.drop_column("distribution_jobs", "last_attempt_at")
