from pathlib import Path

from integrations.contracts.distribution import ContentVariant, DistributionJob
from integrations.distribution_service import DistributionService
from integrations.persistence import InMemoryStore
from social.providers.xiaohongshu.adapter import XiaohongshuAdapter
from social.providers.errors import CapabilityUnsupported
import pytest


def _job(tmp_path, images=1, video=False, extra=()):
    media = []
    for i in range(images):
        path = tmp_path / f"img{i}.jpg"
        path.write_bytes(b"jpeg")
        media.append(str(path))
    for item in extra:
        media.append(item)
    if video:
        path = tmp_path / "clip.mp4"
        path.write_bytes(b"mp4")
        media.append(str(path))
    return DistributionJob(
        "j", "pkg", "xiaohongshu:meiti",
        ContentVariant("xiaohongshu:meiti", "hello", media=tuple(media), title="hi", metadata={"approval": "approved", "platform": "xiaohongshu"}),
        idempotency_key="k", provider="xiaohongshu", platform="xiaohongshu",
    )


def test_handoff_does_not_create_publication(tmp_path):
    adapter = XiaohongshuAdapter()
    adapter.authenticate({"username": "meiti", "account_id": "xiaohongshu:meiti"})
    store = InMemoryStore()
    result = DistributionService(adapter, store=store).execute(_job(tmp_path), gate_check=lambda job: True)
    assert result.handoff_id
    assert result.status == "READY_FOR_XHS"
    assert store.get_publication("j") is None
    assert store.get_handoff(result.handoff_id) is not None


def test_handoff_does_not_enter_remote_reconciliation(tmp_path):
    from social.reconciliation.service import SocialReconciliationService
    adapter = XiaohongshuAdapter()
    adapter.authenticate({"username": "meiti", "account_id": "xiaohongshu:meiti"})
    store = InMemoryStore()
    result = DistributionService(adapter, store=store).execute(_job(tmp_path), gate_check=lambda job: True)
    recon = SocialReconciliationService(adapter, store=store).reconcile("j")
    assert recon["status"] == "NOT_APPLICABLE"
    assert recon["handoff_id"] == result.handoff_id


def test_image_note_limits(tmp_path):
    adapter = XiaohongshuAdapter()
    adapter.authenticate({"username": "meiti", "account_id": "xiaohongshu:meiti"})
    note = adapter.prepare_image_note(_job(tmp_path, images=1))
    assert note.content_type == "image_note"
    note = adapter.prepare_image_note(_job(tmp_path, images=18))
    assert len(note.images) == 18
    errors = adapter._validate_platform(_job(tmp_path, images=19), adapter.get_account("xiaohongshu:meiti"))
    assert any("1..18" in item for item in errors)


def test_mixed_image_video_blocked(tmp_path):
    adapter = XiaohongshuAdapter()
    adapter.authenticate({"username": "meiti", "account_id": "xiaohongshu:meiti"})
    errors = adapter._validate_platform(_job(tmp_path, images=1, video=True), adapter.get_account("xiaohongshu:meiti"))
    assert any("mix" in item for item in errors)


def test_xhs_account_is_handoff_ready():
    adapter = XiaohongshuAdapter()
    adapter.authenticate({"username": "meiti", "account_id": "xiaohongshu:meiti"})
    account = adapter.get_account("xiaohongshu:meiti")
    assert account.status == "HANDOFF_READY"
    assert account.status != "AUTHENTICATED"


def test_xhs_get_status_not_remote():
    adapter = XiaohongshuAdapter()
    with pytest.raises(CapabilityUnsupported):
        adapter.get_status("xhs-handoff-1")
