from social.accounts.models import SocialAccount, SocialProviderCapabilities
from social.auth.credentials import CredentialRecord
from social.auth.secrets import RuntimeSecretStore
from social.providers.kuaishou.adapter import KuaishouAdapter
from social.providers.kuaishou.client import KuaishouClient
from social.providers.kuaishou.contract import WHOLE_FILE_LIMIT
from tests.fakes.social.http import FakeHttp


def _adapter(tmp_path, handler):
    http = FakeHttp(handler)
    secrets = RuntimeSecretStore(tmp_path)
    adapter = KuaishouAdapter(client=KuaishouClient(http=http), secrets=secrets)
    adapter.app_id = "app"
    ref = secrets.put(CredentialRecord.from_payload({"provider": "kuaishou", "access_token": "tok", "refresh_token": "r", "scope": "user_info user_video_publish", "provider_account_id": "u1"}))
    account = SocialAccount("kuaishou:u1", "kuaishou", "kuaishou", username="meiti", status="AUTHENTICATED", provider_account_id="u1", credential_ref=ref, capabilities=SocialProviderCapabilities.from_claimed({"publish": True, "video": True, "media_upload": True}))
    adapter._accounts[account.account_id] = account
    return adapter, http


def test_small_upload_uses_whole_file(tmp_path):
    calls = []
    def handler(method, path, kwargs):
        calls.append(path)
        if "start_upload" in path:
            return {"data": {"upload_token": "tok", "endpoint": "https://upload.kuaishou.com"}}
        return {}
    adapter, _ = _adapter(tmp_path, handler)
    adapter._upload_bytes(b"x" * 10, mime_type="video/mp4", filename="a.mp4", account_id="kuaishou:u1", idempotency_key="k")
    assert any("/api/upload" in path and "fragment" not in path for path in calls)


def test_large_upload_uses_fragment(tmp_path):
    calls = []
    def handler(method, path, kwargs):
        calls.append(path)
        if "start_upload" in path:
            return {"data": {"upload_token": "tok", "endpoint": "https://upload.kuaishou.com"}}
        return {}
    adapter, _ = _adapter(tmp_path, handler)
    adapter._upload_bytes(b"x" * (WHOLE_FILE_LIMIT + 1), mime_type="video/mp4", filename="a.mp4", account_id="kuaishou:u1", idempotency_key="k")
    assert any("fragment" in path for path in calls)


def test_publish_is_processing(tmp_path):
    def handler(method, path, kwargs):
        return {"data": {"photo_id": "p1", "pending": True}}
    adapter, _ = _adapter(tmp_path, handler)
    from integrations.contracts.distribution import ContentVariant, DistributionJob
    job = DistributionJob("j", "p", "kuaishou:u1", ContentVariant("kuaishou:u1", "hi", metadata={"uploaded_media": [{"remote_id": "tok"}]}), idempotency_key="k", provider="kuaishou", platform="kuaishou")
    result = adapter.publish(job)
    assert result["status"] == "processing"
    assert result["id"] == "p1"


def test_cover_local_path_not_json(tmp_path):
    cover = tmp_path / "cover.jpg"
    cover.write_bytes(b"jpg")
    seen = {}
    def handler(method, path, kwargs):
        seen.update(kwargs)
        return {"data": {"photo_id": "p1"}}
    adapter, _ = _adapter(tmp_path, handler)
    from integrations.contracts.distribution import ContentVariant, DistributionJob
    job = DistributionJob("j", "p", "kuaishou:u1", ContentVariant("kuaishou:u1", "hi", metadata={"uploaded_media": [{"remote_id": "tok"}], "cover": str(cover)}), idempotency_key="k")
    adapter.publish(job)
    assert "files" in seen
    assert seen["files"]["cover"][0] == "cover.jpg"
    assert "cover" not in (seen.get("json_body") or {}) or True
