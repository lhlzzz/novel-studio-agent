from pathlib import Path

from integrations.contracts.distribution import ContentVariant, DistributionJob
from integrations.providers.postiz.adapter import PostizAdapter
from tests.fixtures.fakes import FakePostizClient


def test_media_upload_required_before_payload(tmp_path):
    media = tmp_path / "pic.png"
    media.write_bytes(b"png-bytes")
    client = FakePostizClient()
    adapter = PostizAdapter(client=client)
    adapter.verify_capabilities("x-123")
    job = DistributionJob("job-1", "pkg-1", "x-123", ContentVariant("x-123", "hello", media=(str(media),)))
    _, uploaded = adapter.ensure_media(job)
    assert uploaded[0].remote_path
    assert uploaded[0].source_hash
    payload = adapter._payload(job, post_type="now")
    assert payload["posts"][0]["value"][0]["image"][0]["path"] == uploaded[0].remote_path
    assert payload["posts"][0]["value"][0]["image"][0]["id"] != str(media)
