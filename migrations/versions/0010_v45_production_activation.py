"""V4.5 production activation: media upload fields and listing lifecycle."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0010_v45_production_activation"
down_revision = "0009_v444_production_closure"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE media_uploads ADD COLUMN IF NOT EXISTS platform VARCHAR(120) NOT NULL DEFAULT ''")
    op.execute("ALTER TABLE media_uploads ADD COLUMN IF NOT EXISTS source_asset_id VARCHAR(255) NOT NULL DEFAULT ''")
    op.execute("ALTER TABLE media_uploads ADD COLUMN IF NOT EXISTS media_type VARCHAR(40) NOT NULL DEFAULT ''")
    op.execute("ALTER TABLE media_uploads ADD COLUMN IF NOT EXISTS provider_request_id VARCHAR(255)")
    op.execute("ALTER TABLE media_uploads ADD COLUMN IF NOT EXISTS checksum VARCHAR(64) NOT NULL DEFAULT ''")
    op.execute("ALTER TABLE media_uploads ADD COLUMN IF NOT EXISTS completed_at TIMESTAMP")
    op.execute("ALTER TABLE media_uploads ADD COLUMN IF NOT EXISTS error_code VARCHAR(120)")
    op.execute("ALTER TABLE media_uploads ADD COLUMN IF NOT EXISTS error_message TEXT")
    op.execute("UPDATE media_uploads SET status = 'UPLOADED' WHERE status = 'uploaded'")
    op.execute("UPDATE media_uploads SET checksum = source_hash WHERE checksum = ''")
    op.drop_constraint("ck_meiti_xianyu_listing_status", "xianyu_listings", type_="check")
    op.execute("UPDATE xianyu_listings SET status = 'SUBMITTED' WHERE status IN ('SUBMITTING', 'PROCESSING')")
    op.execute("UPDATE xianyu_listings SET status = 'PUBLISHED' WHERE status = 'ONLINE'")
    op.execute("UPDATE xianyu_listings SET status = 'OFF_SHELF' WHERE status = 'REMOVED'")
    op.create_check_constraint(
        "ck_meiti_xianyu_listing_status",
        "xianyu_listings",
        "status IN ('DRAFT','SUBMITTED','PUBLISHED','OFF_SHELF','FAILED','UNKNOWN')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_meiti_xianyu_listing_status", "xianyu_listings", type_="check")
    op.execute("UPDATE xianyu_listings SET status = 'SUBMITTING' WHERE status = 'SUBMITTED'")
    op.execute("UPDATE xianyu_listings SET status = 'ONLINE' WHERE status = 'PUBLISHED'")
    op.execute("UPDATE xianyu_listings SET status = 'REMOVED' WHERE status = 'OFF_SHELF'")
    op.create_check_constraint(
        "ck_meiti_xianyu_listing_status",
        "xianyu_listings",
        "status IN ('DRAFT','SUBMITTING','PROCESSING','ONLINE','FAILED','REMOVED','UNKNOWN')",
    )
    op.execute("ALTER TABLE media_uploads DROP COLUMN IF EXISTS error_message")
    op.execute("ALTER TABLE media_uploads DROP COLUMN IF EXISTS error_code")
    op.execute("ALTER TABLE media_uploads DROP COLUMN IF EXISTS completed_at")
    op.execute("ALTER TABLE media_uploads DROP COLUMN IF EXISTS checksum")
    op.execute("ALTER TABLE media_uploads DROP COLUMN IF EXISTS provider_request_id")
    op.execute("ALTER TABLE media_uploads DROP COLUMN IF EXISTS media_type")
    op.execute("ALTER TABLE media_uploads DROP COLUMN IF EXISTS source_asset_id")
    op.execute("ALTER TABLE media_uploads DROP COLUMN IF EXISTS platform")
