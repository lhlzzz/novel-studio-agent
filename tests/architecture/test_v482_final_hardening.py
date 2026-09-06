from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_v482_owners_and_migration_exist():
    models = (ROOT / "content/models.py").read_text(encoding="utf-8")
    tasks = (ROOT / "content/tasks.py").read_text(encoding="utf-8")
    readiness = (ROOT / "content/readiness.py").read_text(encoding="utf-8")
    persist = (ROOT / "analytics/persistence.py").read_text(encoding="utf-8")
    assets = (ROOT / "content/assets.py").read_text(encoding="utf-8")
    runtime = (ROOT / "content/runtime.py").read_text(encoding="utf-8")
    migration = (ROOT / "migrations/versions/0016_v482_final_hardening.py").read_text(encoding="utf-8")
    migration_v483 = (ROOT / "migrations/versions/0017_v483_production_integrity.py").read_text(encoding="utf-8")
    assert "ALLOWED_TASK_TRANSITIONS" in models
    assert "USER_OVERRIDE" in models
    assert "def reopen" in tasks
    assert "classify_open_tasks" in tasks
    assert "SYSTEM_CAPABILITY" in readiness
    assert "ACCOUNT_CONFIGURATION" in readiness
    assert "CORE_PRODUCTION" in readiness
    assert "class CanonicalAnalyticsError" in persist
    assert "except Exception:\n        return" not in persist
    assert "NO_PROMPT_REFERENCE" in assets
    assert "production_run_id" in assets
    assert "def continue_yesterday" in runtime
    assert runtime.count("class ContinuityRuntime") == 1
    assert 'revision = "0016_v482_final_hardening"' in migration
    assert 'down_revision = "0015_v481_production_ready_creator_os"' in migration
    assert 'revision = "0017_v483_production_integrity"' in migration_v483
    assert 'down_revision = "0016_v482_final_hardening"' in migration_v483


def test_single_engines_and_no_forged_providers():
    compiler = (ROOT / "content/compiler.py").read_text(encoding="utf-8")
    assets = (ROOT / "content/assets.py").read_text(encoding="utf-8")
    tasks = (ROOT / "content/tasks.py").read_text(encoding="utf-8")
    persist = (ROOT / "analytics/persistence.py").read_text(encoding="utf-8")
    lechuang = (ROOT / "creative/providers/lechuang/client.py").read_text(encoding="utf-8")
    runtime = (ROOT / "content/runtime.py").read_text(encoding="utf-8")
    cli = (ROOT / "scripts/meiti.py").read_text(encoding="utf-8")
    assert compiler.count("class PromptCompiler") == 1
    assert assets.count("class PlatformAssetService") == 1
    assert tasks.count("class TaskOS") == 1
    assert persist.count("CANONICAL_ANALYTICS_STORE") >= 1
    assert "Postiz" not in runtime
    assert "grok-4.6" not in lechuang
    assert not (ROOT / "creative/providers/xai").exists()
    assert "LechuangAdapter(" not in cli
    assert "XAIVideoAdapter(" not in cli


def test_cli_and_audit_keep_evidence_separate():
    doctor = (ROOT / "scripts/meiti_doctor.py").read_text(encoding="utf-8")
    audit = (ROOT / "scripts/meiti_production_audit.py").read_text(encoding="utf-8")
    readiness = (ROOT / "scripts/meiti_production_readiness.py").read_text(encoding="utf-8")
    smoke = (ROOT / "scripts/meiti_smoke_production.py").read_text(encoding="utf-8")
    assert "MEITI_V482_STATUS" in doctor
    assert "MEITI_V483_STATUS" in doctor
    assert "SYSTEM_CAPABILITY" in doctor
    assert "ACCOUNT_CONFIGURATION" in doctor
    assert "0017_v483_production_integrity" in audit or "SYSTEM_CAPABILITY" in audit
    assert not any(line.strip().startswith('"CORE_PRODUCTION_READY": True') for line in audit.splitlines())
    assert "SYSTEM_CAPABILITY is code/schema" in readiness
    assert "never real production PASS" in audit or "never real Day evidence" in audit
    assert "NOT_VERIFIED" in smoke
