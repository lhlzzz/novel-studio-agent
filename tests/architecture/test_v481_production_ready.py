from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_v481_models_and_migration_exist():
    models = (ROOT / "content/models.py").read_text(encoding="utf-8")
    runtime = (ROOT / "content/runtime.py").read_text(encoding="utf-8")
    store = (ROOT / "content/store.py").read_text(encoding="utf-8")
    assets = (ROOT / "content/assets.py").read_text(encoding="utf-8")
    tasks = (ROOT / "content/tasks.py").read_text(encoding="utf-8")
    planner = (ROOT / "content/planner.py").read_text(encoding="utf-8")
    readiness = (ROOT / "content/readiness.py").read_text(encoding="utf-8")
    migration = (ROOT / "migrations/versions/0015_v481_production_ready_creator_os.py").read_text(encoding="utf-8")
    assert "class AccountProfile" in models
    assert "class AccountOperatingState" in models
    assert "class CreatorTask" in models
    assert "class ContentCalendarEntry" in models
    assert "CANONICAL_ANALYTICS_STORE" in models
    assert "def dashboard" in runtime
    assert "def get_next_action" in runtime
    assert "def override_profile" in runtime
    assert "account_profiles" in store
    assert "creator_tasks" in store
    assert "NO_PROMPT_REFERENCE" in assets
    assert "class TaskOS" in tasks
    assert "class EpisodePlanner" in planner
    assert "NEW_PRIMARY_REQUIRED" in planner
    assert "class ProductionReadinessService" in readiness
    assert 'revision = "0015_v481_production_ready_creator_os"' in migration
    assert 'down_revision = "0014_v48_production_loop"' in migration


def test_cli_covers_creator_os_without_forging_providers():
    cli = (ROOT / "scripts/meiti.py").read_text(encoding="utf-8")
    doctor = (ROOT / "scripts/meiti_doctor.py").read_text(encoding="utf-8")
    audit = (ROOT / "scripts/meiti_production_audit.py").read_text(encoding="utf-8")
    readiness = (ROOT / "scripts/meiti_production_readiness.py").read_text(encoding="utf-8")
    smoke = (ROOT / "scripts/meiti_smoke_production.py").read_text(encoding="utf-8")
    assert "cmd_task_next" in cli
    assert "cmd_dashboard" in cli
    assert "cmd_production_readiness" in cli
    assert "LechuangAdapter(" not in cli
    assert "XAIVideoAdapter(" not in cli
    assert "MEITI_V481_STATUS" in doctor
    assert "CORE_PRODUCTION" in doctor
    assert "0015_v481_production_ready_creator_os" in audit
    assert "CORE_PRODUCTION" in readiness
    assert "NOT_VERIFIED" in smoke
    assert "never real production PASS" in audit or "never real Day evidence" in audit


def test_single_prompt_compiler_and_no_postiz_or_grok_video():
    compiler = (ROOT / "content/compiler.py").read_text(encoding="utf-8")
    lechuang = (ROOT / "creative/providers/lechuang/client.py").read_text(encoding="utf-8")
    runtime = (ROOT / "content/runtime.py").read_text(encoding="utf-8")
    persist = (ROOT / "analytics/persistence.py").read_text(encoding="utf-8")
    assert compiler.count("class PromptCompiler") == 1
    assert "Postiz" not in runtime
    assert "grok-4.6" not in lechuang
    assert not (ROOT / "creative/providers/xai").exists()
    assert "CANONICAL_ANALYTICS_STORE" in persist
    assert "content.models.AnalyticsRecord" in persist
    assert "XHS_HANDOFF" in runtime
