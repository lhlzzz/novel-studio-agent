"""V4.8.2 final pre-production hardening: task history, receipt run binding, analytics dedup."""

from alembic import op
import sqlalchemy as sa

revision = "0016_v482_final_hardening"
down_revision = "0015_v481_production_ready_creator_os"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE lifecycle_transitions ADD COLUMN IF NOT EXISTS task_id VARCHAR(255)")
    op.execute("ALTER TABLE lifecycle_transitions ADD COLUMN IF NOT EXISTS reason TEXT NOT NULL DEFAULT ''")
    op.execute("ALTER TABLE lifecycle_transitions ADD COLUMN IF NOT EXISTS operator VARCHAR(120) NOT NULL DEFAULT ''")
    op.execute("ALTER TABLE creative_execution_receipts ADD COLUMN IF NOT EXISTS production_run_id VARCHAR(255)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_meiti_lifecycle_transitions_task ON lifecycle_transitions (task_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_meiti_creative_receipts_run ON creative_execution_receipts (production_run_id)")
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_meiti_analytics_observation "
        "ON analytics_records (publication_id, observed_at) "
        "WHERE publication_id IS NOT NULL AND observed_at IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_meiti_analytics_observation")
    op.execute("DROP INDEX IF EXISTS idx_meiti_creative_receipts_run")
    op.execute("DROP INDEX IF EXISTS idx_meiti_lifecycle_transitions_task")
    op.execute("ALTER TABLE creative_execution_receipts DROP COLUMN IF EXISTS production_run_id")
    op.execute("ALTER TABLE lifecycle_transitions DROP COLUMN IF EXISTS operator")
    op.execute("ALTER TABLE lifecycle_transitions DROP COLUMN IF EXISTS reason")
    op.execute("ALTER TABLE lifecycle_transitions DROP COLUMN IF EXISTS task_id")
