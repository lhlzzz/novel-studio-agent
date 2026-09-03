from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PRODUCTION = ("agents", "social", "creative", "integrations", "scripts", "services", "governance")


def _iter_py():
    for name in PRODUCTION:
        for path in (ROOT / name).rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            yield path


def test_ci_has_production_gate_without_true_swallow():
    workflows = ROOT / ".github/workflows"
    names = {path.name for path in workflows.glob("*.yml")}
    assert "architecture.yml" in names
    assert "test.yml" in names
    assert "doctor.yml" in names
    assert "production-gate.yml" in names
    for path in workflows.glob("*.yml"):
        body = path.read_text(encoding="utf-8")
        assert "|| true" not in body, path


def test_postiz_cannot_reappear():
    hits = []
    for path in _iter_py():
        body = path.read_text(encoding="utf-8")
        if "postiz" in body.lower():
            hits.append(str(path.relative_to(ROOT)))
    assert hits == []


def test_production_adapter_does_not_own_store():
    for path in (ROOT / "social/providers").rglob("*.py"):
        if path.name == "base.py" or "__pycache__" in path.parts:
            continue
        body = path.read_text(encoding="utf-8")
        assert "self.store =" not in body, path
        assert "getattr(self, \"store\"" not in body, path


def test_distribution_does_not_read_platform_from_metadata():
    source = (ROOT / "integrations/distribution_service.py").read_text(encoding="utf-8")
    assert 'variant.metadata["platform"]' not in source
    assert 'variant.metadata["provider"]' not in source
    assert "self.provider_name" not in source


def test_credentials_read_source_has_no_refresh():
    source = (ROOT / "social/providers/base.py").read_text(encoding="utf-8")
    block = source.split("def _credentials", 1)[1].split("def ensure_valid_credentials", 1)[0]
    assert "refresh" not in block


def test_media_upload_is_first_class():
    from integrations.contracts.distribution import MEDIA_UPLOAD_STATES, MediaUpload, MediaUploadResult
    assert MediaUpload is MediaUploadResult
    assert "UPLOADED" in MEDIA_UPLOAD_STATES
    item = MediaUploadResult(
        source_hash="abc", source_path="a.jpg", mime_type="image/jpeg", size=1,
        provider="douyin", remote_id="m1", remote_path="m1", uploaded_at="now", status="uploaded",
    )
    assert item.status == "UPLOADED"
    assert item.provider_media_id == "m1"
    assert item.id


def test_listing_statuses_are_independent():
    from commerce.xianyu import LISTING_STATES
    assert LISTING_STATES == ("DRAFT", "SUBMITTED", "PUBLISHED", "OFF_SHELF", "FAILED", "UNKNOWN")


def test_distribution_outcome_is_a_union():
    from integrations.contracts.distribution import DistributionOutcome, HandoffOutcome, ListingOutcome, PublicationOutcome
    assert DistributionOutcome == PublicationOutcome | HandoffOutcome | ListingOutcome


def test_doctor_cannot_pass_when_runtime_blocked():
    from scripts.social_doctor import evaluate_production_readiness
    checks = {
        "Runtime": {"status": "BLOCKED_EXTERNAL"},
        "Production Store": {"status": "PASS"},
        "Credential Store": {"status": "BLOCKED_EXTERNAL"},
        "Scheduler": {"status": "PASS"},
        "Publish Gate": {"status": "PASS"},
        "Reconciliation": {"status": "PASS"},
        "Analytics": {"status": "PASS"},
        "Xiaohongshu": {"status": "HANDOFF_ONLY", "Real E2E": "BLOCKED_EXTERNAL"},
        "Douyin": {"status": "BLOCKED_EXTERNAL", "Real E2E": "BLOCKED_EXTERNAL"},
        "Kuaishou": {"status": "BLOCKED_EXTERNAL", "Real E2E": "BLOCKED_EXTERNAL"},
        "Xianyu": {"status": "BLOCKED_EXTERNAL", "Real E2E": "BLOCKED_EXTERNAL"},
        "Lechuang": {"status": "BLOCKED_EXTERNAL"},
    }
    readiness = evaluate_production_readiness(checks)
    assert readiness["architecture"] == "PASS"
    assert readiness["overall"] == "BLOCKED_EXTERNAL"
    assert readiness["overall_ready"] is False


REQUIRED_PRODUCTION_SECRETS = (
    "DOUYIN_CLIENT_KEY",
    "DOUYIN_CLIENT_SECRET",
    "DOUYIN_REDIRECT_URI",
    "KUAISHOU_APP_ID",
    "KUAISHOU_APP_SECRET",
    "KUAISHOU_REDIRECT_URI",
    "XIANYU_APP_KEY",
    "XIANYU_APP_SECRET",
    "XIANYU_REDIRECT_URI",
    "XHS_CLIENT_ID",
    "XHS_CLIENT_SECRET",
    "XHS_REDIRECT_URI",
    "XIAOLEAI_API_KEY",
    "XIAOLEAI_BASE_URL",
)


def test_production_gate_secret_injection_contract():
    body = (ROOT / ".github/workflows/production-gate.yml").read_text(encoding="utf-8")
    assert "MEITI_SECRET_DIR: ${{ runner.temp }}/meiti-secrets" in body
    assert "mkdir -p \"$MEITI_SECRET_DIR\"" in body or "mkdir -p \"$MEITI_SECRET_DIR\"" in body.replace("'", '"')
    assert "chmod 700" in body
    for name in REQUIRED_PRODUCTION_SECRETS:
        assert "${{ secrets." + name + " }}" in body, name
    assert "printenv" not in body
    assert "continue-on-error" not in body
    assert "|| true" not in body
    assert "value: \"real-secret\"" not in body


def test_no_provider_first_account_fallback():
    hits = []
    needle = "next(iter(self._accounts.values())"
    for path in _iter_py():
        body = path.read_text(encoding="utf-8")
        if needle in body:
            hits.append(str(path.relative_to(ROOT)))
    assert hits == []


def test_bootstrap_is_read_only(tmp_path, monkeypatch):
    monkeypatch.setenv("MEITI_SECRET_DIR", str(tmp_path))
    monkeypatch.setenv("XIAOLEAI_API_KEY", "must-not-be-written")
    monkeypatch.setenv("XIAOLEAI_BASE_URL", "https://example.invalid")
    tmp_path.chmod(0o700)
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir() if p.is_file()}
    from scripts.meiti import bootstrap_production
    report = bootstrap_production()
    after = {p.name: p.read_bytes() for p in tmp_path.iterdir() if p.is_file()}
    assert before == after
    assert report["generated_credentials"] is False
    assert report["credential_writes"] is False
    assert report["overall"]["status"] in {"BLOCKED_EXTERNAL", "FAIL"}


def test_bootstrap_does_not_write_lechuang_secret(tmp_path, monkeypatch):
    monkeypatch.setenv("MEITI_SECRET_DIR", str(tmp_path))
    monkeypatch.setenv("XIAOLEAI_API_KEY", "xiaole-secret")
    monkeypatch.setenv("XIAOLEAI_BASE_URL", "https://example.invalid")
    tmp_path.chmod(0o700)
    from scripts.meiti import bootstrap_production
    from social.auth.secrets import secret_id
    bootstrap_production()
    digest_name = None
    from hashlib import sha256
    ref = secret_id("xiaole", "api")
    name = sha256(ref.encode("utf-8")).hexdigest() + ".json"
    assert not (tmp_path / name).exists()


def test_provider_status_requires_account_id(tmp_path):
    from social.providers.douyin.adapter import DouyinAdapter
    from social.providers.errors import AuthenticationError
    import pytest
    adapter = DouyinAdapter()
    with pytest.raises(AuthenticationError):
        adapter.get_status("item-1")


def test_doctor_probe_semantics():
    from scripts.social_doctor import _aggregate_probe, evaluate_production_readiness
    probe = _aggregate_probe({
        "douyin": {"status": "BLOCKED_EXTERNAL"},
        "kuaishou": {"status": "BLOCKED_EXTERNAL"},
        "xianyu": {"status": "BLOCKED_EXTERNAL"},
        "xiaohongshu": {"status": "HANDOFF_ONLY"},
    })
    assert probe == "BLOCKED_EXTERNAL"
    healthy = _aggregate_probe({
        "xiaohongshu": {"status": "HANDOFF_ONLY"},
        "douyin": {"status": "PASS"},
    })
    assert healthy == "PASS"
    checks = {
        "Runtime": {"status": "PASS"},
        "Production Store": {"status": "PASS"},
        "Credential Store": {"status": "PASS"},
        "Scheduler": {"status": "PASS"},
        "Publish Gate": {"status": "PASS"},
        "Reconciliation": {"status": "PASS"},
        "Analytics": {"status": "PASS"},
        "Xiaohongshu": {"status": "HANDOFF_ONLY", "Real E2E": "BLOCKED_EXTERNAL"},
        "Douyin": {"status": "BLOCKED_EXTERNAL", "Real E2E": "BLOCKED_EXTERNAL"},
        "Kuaishou": {"status": "BLOCKED_EXTERNAL", "Real E2E": "BLOCKED_EXTERNAL"},
        "Xianyu": {"status": "BLOCKED_EXTERNAL", "Real E2E": "BLOCKED_EXTERNAL"},
        "Social Accounts": {"status": "PASS", "account_count": 0, "enabled_count": 0},
        "Lechuang": {"status": "BLOCKED_EXTERNAL"},
    }
    readiness = evaluate_production_readiness(checks)
    assert readiness["architecture"] == "PASS"
    assert readiness["overall"] == "BLOCKED_EXTERNAL"


def test_production_gate_semantics():
    from scripts.social_doctor import structured_report
    checks = {
        "Runtime": {"status": "PASS"},
        "Production Store": {"status": "PASS"},
        "Credential Store": {"status": "PASS"},
        "Scheduler": {"status": "PASS"},
        "Publish Gate": {"status": "PASS"},
        "Reconciliation": {"status": "PASS"},
        "Analytics": {"status": "PASS"},
        "Xiaohongshu": {"status": "HANDOFF_ONLY", "Real E2E": "LIVE_VERIFIED"},
        "Douyin": {"status": "PASS", "Real E2E": "LIVE_VERIFIED"},
        "Kuaishou": {"status": "PASS", "Real E2E": "LIVE_VERIFIED"},
        "Xianyu": {"status": "PASS", "Real E2E": "LIVE_VERIFIED"},
        "Social Accounts": {"status": "PASS", "account_count": 0, "enabled_count": 0},
        "Lechuang": {"status": "PASS"},
    }
    report = structured_report(checks)
    assert report["architecture"]["status"] == "PASS"
    assert report["overall"]["status"] == "BLOCKED_EXTERNAL"
    checks["Social Accounts"] = {"status": "PASS", "account_count": 2, "enabled_count": 2}
    report = structured_report(checks)
    assert report["overall"]["status"] == "PASS"


def test_migration_status_contract():
    source = (ROOT / "migrations/versions/0010_v45_production_activation.py").read_text(encoding="utf-8")
    upgrade = source.split("def upgrade", 1)[1].split("def downgrade", 1)[0]
    assert "UPDATE xianyu_listings SET status" in upgrade
    assert "create_check_constraint" in upgrade
    assert upgrade.index("UPDATE xianyu_listings SET status") < upgrade.index("create_check_constraint")
    assert "lossy" in source.lower() or "not strictly reversible" in source.lower()
