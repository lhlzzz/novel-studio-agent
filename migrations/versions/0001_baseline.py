"""Adopt the existing Meiti schema as the initial Alembic revision."""

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Existing installations are stamped by scripts/db/migrate.py. This
    # revision intentionally has no DDL because it adopts the V3 baseline.
    return None


def downgrade() -> None:
    raise RuntimeError("The Meiti baseline is not downgradeable")
