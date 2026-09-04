"""V4.8.3 production integrity: analytics origin, run status, orphan-safe indexes."""

from alembic import op

revision = "0017_v483_production_integrity"
down_revision = "0016_v482_final_hardening"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE analytics_records ADD COLUMN IF NOT EXISTS origin VARCHAR(40) NOT NULL DEFAULT 'MANUAL'")
    op.execute("ALTER TABLE analytics_records ADD COLUMN IF NOT EXISTS verification_status VARCHAR(40) NOT NULL DEFAULT 'UNVERIFIED'")
    op.execute("ALTER TABLE analytics_records ADD COLUMN IF NOT EXISTS provider VARCHAR(120) NOT NULL DEFAULT ''")
    op.execute("ALTER TABLE analytics_records ADD COLUMN IF NOT EXISTS provider_payload JSONB NOT NULL DEFAULT '{}'::jsonb")
    op.execute("UPDATE analytics_records SET origin = 'MANUAL' WHERE origin IS NULL OR origin = ''")
    op.execute("UPDATE analytics_records SET verification_status = 'UNVERIFIED' WHERE verification_status IS NULL OR verification_status = ''")
    op.execute("UPDATE production_runs SET status = 'CREATED' WHERE status IS NULL OR status = ''")
    op.execute(
        "DO $$ BEGIN "
        "IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_meiti_analytics_origin') THEN "
        "ALTER TABLE analytics_records ADD CONSTRAINT ck_meiti_analytics_origin "
        "CHECK (origin IN ('MANUAL','PROVIDER')); "
        "END IF; END $$;"
    )
    op.execute(
        "DO $$ BEGIN "
        "IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_meiti_analytics_verification') THEN "
        "ALTER TABLE analytics_records ADD CONSTRAINT ck_meiti_analytics_verification "
        "CHECK (verification_status IN ('VERIFIED','UNVERIFIED')); "
        "END IF; END $$;"
    )
    op.execute(
        "DO $$ BEGIN "
        "IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_meiti_learning_evidence_status') THEN "
        "ALTER TABLE learning_records ADD CONSTRAINT ck_meiti_learning_evidence_status "
        "CHECK (evidence_status IN ('VERIFIED','NOT_ENOUGH_EVIDENCE','NOT_VERIFIED')); "
        "END IF; END $$;"
    )
    op.execute(
        "DO $$ BEGIN "
        "IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_meiti_package_asset_role') THEN "
        "ALTER TABLE content_package_assets ADD CONSTRAINT ck_meiti_package_asset_role "
        "CHECK (role IN ('PRIMARY','COVER','THUMBNAIL','REFERENCE')); "
        "END IF; END $$;"
    )
    op.execute(
        "DO $$ BEGIN "
        "IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_meiti_production_run_status') THEN "
        "ALTER TABLE production_runs ADD CONSTRAINT ck_meiti_production_run_status "
        "CHECK (status IN ("
        "'CREATED','PROMPT_READY','CREATIVE_EXECUTION','ASSET_IMPORTED','QA_PASSED',"
        "'PACKAGE_READY','HANDED_OFF','PUBLISHED','ANALYTICS_CAPTURED','LEARNING_VERIFIED',"
        "'CLOSED','BLOCKED','OPEN','AWAITING_CREATIVE','IMPORTED','PACKAGED','LEARNED'"
        ")); "
        "END IF; END $$;"
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_meiti_production_evidence_run ON production_evidence (production_run_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_meiti_asset_reference_snapshots_asset ON asset_reference_snapshots (asset_id)")
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_meiti_asset_reference_snapshot "
        "ON asset_reference_snapshots (prompt_id, asset_id, role)"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_meiti_learning_analytics "
        "ON learning_records (analytics_id) WHERE analytics_id IS NOT NULL"
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_meiti_lifecycle_transitions_evidence ON lifecycle_transitions (evidence_id)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_meiti_creative_receipts_asset_run "
        "ON creative_execution_receipts (asset_id, production_run_id)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_meiti_creative_receipts_asset_run")
    op.execute("DROP INDEX IF EXISTS idx_meiti_lifecycle_transitions_evidence")
    op.execute("DROP INDEX IF EXISTS uq_meiti_learning_analytics")
    op.execute("DROP INDEX IF EXISTS uq_meiti_asset_reference_snapshot")
    op.execute("DROP INDEX IF EXISTS idx_meiti_asset_reference_snapshots_asset")
    op.execute("DROP INDEX IF EXISTS idx_meiti_production_evidence_run")
    op.execute("ALTER TABLE production_runs DROP CONSTRAINT IF EXISTS ck_meiti_production_run_status")
    op.execute("ALTER TABLE content_package_assets DROP CONSTRAINT IF EXISTS ck_meiti_package_asset_role")
    op.execute("ALTER TABLE learning_records DROP CONSTRAINT IF EXISTS ck_meiti_learning_evidence_status")
    op.execute("ALTER TABLE analytics_records DROP CONSTRAINT IF EXISTS ck_meiti_analytics_verification")
    op.execute("ALTER TABLE analytics_records DROP CONSTRAINT IF EXISTS ck_meiti_analytics_origin")
    op.execute("ALTER TABLE analytics_records DROP COLUMN IF EXISTS provider_payload")
    op.execute("ALTER TABLE analytics_records DROP COLUMN IF EXISTS provider")
    op.execute("ALTER TABLE analytics_records DROP COLUMN IF EXISTS verification_status")
    op.execute("ALTER TABLE analytics_records DROP COLUMN IF EXISTS origin")
