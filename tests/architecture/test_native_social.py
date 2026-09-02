from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

SKIP_DIRS = {".git", "node_modules", ".understand-anything", "__pycache__", ".pytest_cache", "postgres-data"}


PRODUCTION = (
    "agents", "social", "creative", "integrations", "scripts", "services",
    "governance", "content", "analytics", "memory", "commerce", "intelligence",
    "strategy", "media", "workflows", "config", "infrastructure", "docs",
)
PRODUCTION_FILES = (
    "AGENTS.md", "README.md", "RULES.md", "STATE.md", "TASK.md", "TOOLING.md",
    "DECISIONS.md", "HANDOFF.md", "NEXT_ACTION.md", ".env.example", "skills-lock.json",
)

def _iter_text_files():
    for name in PRODUCTION:
        root = ROOT / name
        if not root.exists():
            continue
        paths = root.rglob("*") if root.is_dir() else [root]
        for path in paths:
            if not path.is_file():
                continue
            if any(part in SKIP_DIRS for part in path.parts):
                continue
            if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".pyc", ".db", ".zst"}:
                continue
            yield path
    for name in PRODUCTION_FILES:
        path = ROOT / name
        if path.exists():
            yield path


def test_no_third_party_scheduler_reference():
    hits = []
    for path in _iter_text_files():
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        token = "pos" + "tiz"
        lowered = text.lower()
        if token in lowered and "does not exist" not in lowered and "removed" not in lowered:
            hits.append(str(path.relative_to(ROOT)))
    assert hits == []


def test_no_third_party_scheduler_env():
    env = (ROOT / ".env.example").read_text(encoding="utf-8")
    token = ("POS" + "TIZ").lower()
    assert token not in env.lower()


def test_no_third_party_scheduler_provider():
    name = "pos" + "tiz"
    assert not (ROOT / "integrations/providers" / name).exists()
    assert not (ROOT / "infrastructure" / name).exists()
    from social.providers.resolver import ADAPTER_IMPORTS
    assert ("pos" + "tiz") not in ADAPTER_IMPORTS


def test_distribution_uses_native_provider():
    from social.providers.resolver import resolve_social_provider
    handle = resolve_social_provider("x")
    assert handle.implementation.__class__.__name__ == "XAdapter"
    assert handle.owner == "social"


def test_social_provider_resolver():
    from integrations.providers.resolver import resolve_provider
    handle = resolve_provider("x")
    assert handle.implementation.__class__.__name__ == "XAdapter"


def test_account_verification_required():
    from social.accounts.models import SocialAccount, enable_account
    import pytest
    account = SocialAccount("a1", "x", "x", status="AUTHENTICATED")
    with pytest.raises(ValueError):
        enable_account(account)


def test_publish_requires_verified_account():
    from governance.distribution_gate import check_distribution_job
    from integrations.contracts.distribution import ContentVariant, DistributionJob
    from social.accounts.models import SocialAccount
    account = SocialAccount("i", "x", "x", status="AUTHENTICATED")
    job = DistributionJob("j", "p", "i", ContentVariant("i", "hello"), idempotency_key="k")
    failures = check_distribution_job(job, account)
    assert "account not verified" in failures
    assert "account disabled" in failures or "account not enabled" in failures


def test_no_creative_to_social_direct_call():
    for path in (ROOT / "creative").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "social.providers" not in text
        assert "SocialProviderResolver" not in text
