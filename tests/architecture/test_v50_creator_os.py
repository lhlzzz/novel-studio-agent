from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_v50_models_and_migration_exist():
    models = (ROOT / "content/models.py").read_text(encoding="utf-8")
    runtime = (ROOT / "content/runtime.py").read_text(encoding="utf-8")
    planner = (ROOT / "content/planner.py").read_text(encoding="utf-8")
    compiler = (ROOT / "content/compiler.py").read_text(encoding="utf-8")
    store = (ROOT / "content/store.py").read_text(encoding="utf-8")
    migration = (ROOT / "migrations/versions/0018_v50_creator_os_unification.py").read_text(encoding="utf-8")
    owners = (ROOT / "docs/architecture/canonical-owner-map.md").read_text(encoding="utf-8")
    assert "CreatorAccount = PlatformAccount" in models
    assert "class PlatformConnection" in models
    assert "class CreatorStrategy" in models
    assert "class CreatorState" in models
    assert "class ContentDecision" in models
    assert "class ProductionMemory" in models
    assert "class ContentNovelty" in models
    assert "def produce_today" in runtime
    assert runtime.count("class ContinuityRuntime") == 1
    assert planner.count("class CreatorBrain") == 1
    assert planner.count("class ContentNoveltyService") == 1
    assert planner.count("class CreatorStrategyService") == 1
    assert "CREATOR STRATEGY BASIS" in compiler
    assert "CONTENT DECISION" in compiler
    assert "NOVELTY BASIS" in compiler
    assert "CONTINUITY BASIS" in compiler
    assert "platform_connections" in store
    assert "creator_strategies" in store
    assert "production_memories" in store
    assert 'revision = "0018_v50_creator_os_unification"' in migration
    assert 'down_revision = "0017_v483_production_integrity"' in migration
    assert "Creator Identity" in owners
    assert "Content decision" in owners


def test_v50_cli_and_doctor_keep_oauth_optional():
    cli = (ROOT / "scripts/meiti.py").read_text(encoding="utf-8")
    doctor = (ROOT / "scripts/meiti_doctor.py").read_text(encoding="utf-8")
    audit = (ROOT / "scripts/meiti_production_audit.py").read_text(encoding="utf-8")
    assert "cmd_creator_today" in cli
    assert "cmd_creator_continue" in cli
    assert "cmd_creator_idea" in cli
    assert "LechuangAdapter(" not in cli
    assert "XAIVideoAdapter(" not in cli
    assert "MEITI_V50_STATUS" in doctor
    assert "CORE_CONTENT_PRODUCTION" in doctor
    assert "0018_v50_creator_os_unification" in audit
    assert not any(line.strip().startswith('"CORE_PRODUCTION_READY": True') for line in audit.splitlines())
