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
