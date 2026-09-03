from integrations.contracts.distribution import ContentVariant, DistributionJob
from tests.fixtures.fakes import FakeAdapter


def test_media_upload_required_before_payload(tmp_path):
    media = tmp_path / "pic.png"
    media.write_bytes(b"png-bytes")
    adapter = FakeAdapter()
    job = DistributionJob("job-1", "pkg-1", "i", ContentVariant("i", "hello", media=(str(media),)))
    updated, uploaded = adapter.ensure_media(job)
    assert uploaded[0].remote_path
    assert uploaded[0].source_hash
    assert uploaded[0].remote_id != str(media)
    assert updated.media_uploads[0].remote_id == "media-1"


def test_unknown_media_is_not_reuploaded(tmp_path):
    from integrations.contracts.distribution import MediaUploadResult
    from integrations.distribution_service import DistributionService
    from integrations.persistence import InMemoryStore
    media = tmp_path / "pic.png"
    media.write_bytes(b"png-bytes")
    adapter = FakeAdapter()
    store = InMemoryStore()
    import hashlib
    digest = hashlib.sha256(b"png-bytes").hexdigest()
    existing = MediaUploadResult(
        source_hash=digest, source_path=str(media), mime_type="image/png", size=9,
        provider="x", remote_id="", remote_path="", uploaded_at="now", status="UNKNOWN",
        account_id="i",
    )
    store.save_media(existing)
    job = DistributionJob("job-1", "pkg-1", "i", ContentVariant("i", "hello", media=(str(media),)), provider="x", platform="x")
    service = DistributionService(adapter, store=store)
    calls = []
    original = adapter.upload_media
    def wrapped(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)
    adapter.upload_media = wrapped
    updated = service._ensure_media(job)
    assert updated.media_uploads[0].status == "UNKNOWN"
    assert calls == []
