from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_v483_migration_and_owners_exist():
    migration = (ROOT / "migrations/versions/0017_v483_production_integrity.py").read_text(encoding="utf-8")
    assets = (ROOT / "content/assets.py").read_text(encoding="utf-8")
    readiness = (ROOT / "content/readiness.py").read_text(encoding="utf-8")
    runtime = (ROOT / "content/runtime.py").read_text(encoding="utf-8")
    gate = (ROOT / "social/publish/gate.py").read_text(encoding="utf-8")
    owners = (ROOT / "docs/architecture/canonical-owner-map.md").read_text(encoding="utf-8")
    assert 'revision = "0017_v483_production_integrity"' in migration
    assert 'down_revision = "0016_v482_final_hardening"' in migration
    assert "def _prevalidate_import" in assets
    assert "with self.store.transaction()" in assets
    assert "PACKAGE_MISSING" in readiness
    assert "CHARACTER_NOT_FOUND" in readiness
    assert "MEDIA_NOT_UPLOADED" in gate
    assert "MANUAL_ANALYTICS_OBSERVATION" in runtime
    assert "Canonical Owner Map" in owners


def test_audit_has_no_hardcoded_core_ready():
    audit = (ROOT / "scripts/meiti_production_audit.py").read_text(encoding="utf-8")
    doctor = (ROOT / "scripts/meiti_doctor.py").read_text(encoding="utf-8")
    assert not any(line.strip().startswith('"CORE_PRODUCTION_READY": True') for line in audit.splitlines())
    assert "CODE_STRUCTURE" in audit
    assert "SEMANTIC_INVARIANTS" in audit
    assert "REAL_PRODUCTION_EVIDENCE" in audit
    assert "MEITI_V483_STATUS" in doctor
    assert "REAL_EVIDENCE=NOT_VERIFIED" in doctor
