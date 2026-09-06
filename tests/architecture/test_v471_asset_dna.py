from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_prompt_compiler_and_asset_guards_exist():
    compiler = (ROOT / "content/compiler.py").read_text(encoding="utf-8")
    assets = (ROOT / "content/assets.py").read_text(encoding="utf-8")
    models = (ROOT / "content/models.py").read_text(encoding="utf-8")
    assert "class PromptCompiler" in compiler
    assert "COPY READY" in compiler
    assert "IMAGE PROMPT PACKAGE" in compiler
    assert "VIDEO PROMPT PACKAGE" in compiler
    assert "IMAGE_TO_VIDEO PACKAGE" in compiler
    assert "STALE_ASSET_REUSE" in assets
    assert "SAME_FILE_REUSE" in assets
    assert "CROSS_PLATFORM_ASSET_REUSE" in assets
    assert "REFERENCE_AS_PRIMARY" in assets
    assert "EXISTING_ASSET" in assets
    assert "class PlatformAssetPool" in models
    assert "class PlatformCreativeDNA" in models
    assert "class PromptPackage" in models
    assert "class PlatformLearningProfile" in models


def test_cli_is_prompt_first_and_does_not_bypass_architecture():
    cli = (ROOT / "scripts/meiti.py").read_text(encoding="utf-8")
    assert "compile-prompt" in cli
    assert "import-asset" in cli
    assert "cmd_creative_import_asset" in cli
    assert "COPY_READY" in cli
    assert "manual-lechuang" in cli
    assert "LechuangAdapter(" not in cli
    assert "XAIVideoAdapter(" not in cli


def test_readme_is_prompt_first_and_does_not_treat_grok_as_video_model():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "prompt-first" in readme.lower() or "Prompt-first" in readme or "Meiti is prompt-first" in readme
    assert "only Creative Provider" in readme or "primary creative" in readme.lower()
    assert "never fabricates external generation evidence" in readme.lower() or "never fabricates" in readme
    assert "grok-4.6" not in (ROOT / "creative/providers/lechuang/client.py").read_text(encoding="utf-8")
    assert not (ROOT / "creative/providers/xai").exists()


def test_migration_0013_exists_and_heads_from_v47():
    path = ROOT / "migrations/versions/0013_v471_platform_asset_dna.py"
    body = path.read_text(encoding="utf-8")
    assert 'revision = "0013_v471_platform_asset_dna"' in body
    assert 'down_revision = "0012_v47_memory_brain"' in body
    assert "platform_asset_pools" in body
    assert "prompt_packages" in body
    assert "platform_learning_profiles" in body


def test_learning_isolation_is_enforced_in_retrieval():
    source = (ROOT / "memory/service.py").read_text(encoding="utf-8")
    assert "document.platform not in {platform, \"GLOBAL\"}" in source or "document.platform !=" in source
    patterns = (ROOT / "content/store.py").read_text(encoding="utf-8")
    assert "global_pattern" in patterns
    assert "list_prompt_patterns" in patterns
