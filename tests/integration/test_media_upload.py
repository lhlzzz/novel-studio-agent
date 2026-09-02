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
    assert updated.variant.metadata["uploaded_media"][0]["remote_id"] == "media-1"
