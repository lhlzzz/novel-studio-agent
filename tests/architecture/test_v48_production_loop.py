from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_v48_models_and_migration_exist():
    models = (ROOT / "content/models.py").read_text(encoding="utf-8")
    runtime = (ROOT / "content/runtime.py").read_text(encoding="utf-8")
    store = (ROOT / "content/store.py").read_text(encoding="utf-8")
    assets = (ROOT / "content/assets.py").read_text(encoding="utf-8")
    compiler = (ROOT / "content/compiler.py").read_text(encoding="utf-8")
    migration = (ROOT / "migrations/versions/0014_v48_production_loop.py").read_text(encoding="utf-8")
    assert "class ProductionRun" in models
    assert "class ProductionEvidence" in models
    assert "class LearningRecord" in models
    assert "class AnalyticsRecord" in models
    assert "class CreativeExecutionReceipt" in models
    assert "class PatternPromotion" in models
    assert "HANDOFF_READY" in models
    assert "def record_handoff" in runtime
    assert "def record_analytics" in runtime
    assert "def record_learning" in runtime
    assert "EXISTING_ASSET" in store
    assert "DAY_" in assets and "REAL_ASSET_IMPORTED" in assets
    assert "DUPLICATE_CONTENT" in compiler
    assert 'revision = "0014_v48_production_loop"' in migration
    assert 'down_revision = "0013_v471_platform_asset_dna"' in migration


def test_cli_covers_production_loop_without_forging_providers():
    cli = (ROOT / "scripts/meiti.py").read_text(encoding="utf-8")
    doctor = (ROOT / "scripts/meiti_doctor.py").read_text(encoding="utf-8")
    audit = (ROOT / "scripts/meiti_production_audit.py").read_text(encoding="utf-8")
    assert "compile-prompt" in cli
    assert "import-asset" in cli
    assert "cmd_analytics_record" in cli
    assert "cmd_learning_record" in cli
    assert "cmd_sandbox_seed" in cli
    assert "package_id is required" in cli
    assert "LechuangAdapter(" not in cli
    assert "XAIVideoAdapter(" not in cli
    assert "MEITI_V48_STATUS" in doctor
    assert "PRODUCTION_EVIDENCE" in doctor
    assert "MEITI_V471_STATUS" not in doctor
    assert "REAL_DAY_X" in audit or "REAL_DAY_1" in audit
    assert "never real production PASS" in audit or "never real Day evidence" in audit


def test_grok_is_not_a_video_model_and_handoff_is_not_publication():
    lechuang = (ROOT / "creative/providers/lechuang/client.py").read_text(encoding="utf-8")
    runtime = (ROOT / "content/runtime.py").read_text(encoding="utf-8")
    assert "grok-4.6" not in lechuang
    assert not (ROOT / "creative/providers/xai").exists()
    assert "XHS_HANDOFF" in runtime
    assert "HANDED_OFF" in runtime
