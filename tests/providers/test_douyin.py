from social.accounts.models import SocialAccount, SocialProviderCapabilities
from social.auth.credentials import CredentialRecord
from social.auth.secrets import RuntimeSecretStore
from social.providers.douyin.adapter import DouyinAdapter
from social.providers.douyin.client import DouyinClient
from tests.fakes.social.http import FakeHttp
from integrations.contracts.distribution import MediaUploadResult


def _adapter(tmp_path, handler):
    http = FakeHttp(handler)
    secrets = RuntimeSecretStore(tmp_path)
    adapter = DouyinAdapter(client=DouyinClient(http=http), secrets=secrets)
    record = CredentialRecord.from_payload({"provider": "douyin", "access_token": "tok", "refresh_token": "r", "scope": "user_info video.create video.data", "provider_account_id": "open"})
    ref = secrets.put(record)
    account = SocialAccount("douyin:open", "douyin", "douyin", username="meiti", status="AUTHENTICATED", provider_account_id="open", credential_ref=ref, capabilities=SocialProviderCapabilities.from_claimed({"publish": True, "video": True, "image": True, "media_upload": True}))
    adapter._accounts[account.account_id] = account
    adapter._credential_ref = ref
    return adapter, http


def test_image_upload_uses_image_endpoint(tmp_path):
    def handler(method, path, kwargs):
        assert "upload_image" in path
        return {"data": {"image_id": "img-1"}}
    adapter, http = _adapter(tmp_path, handler)
    result = adapter._upload_bytes(b"jpeg", mime_type="image/jpeg", filename="a.jpg", account_id="douyin:open", idempotency_key="k")
    assert result["id"] == "img-1"
    assert result["provider_object_type"] == "image_post"


def test_video_upload_small(tmp_path):
    def handler(method, path, kwargs):
        assert "upload_video" in path
        return {"data": {"video_id": "v-1"}}
    adapter, _ = _adapter(tmp_path, handler)
    result = adapter._upload_bytes(b"mp4", mime_type="video/mp4", filename="a.mp4", account_id="douyin:open", idempotency_key="k")
    assert result["id"] == "v-1"


def test_image_post_object_type(tmp_path):
    def handler(method, path, kwargs):
        if "create_image_text" in path:
            return {"data": {"item_id": "item-1"}}
        return {"data": {}}
    adapter, _ = _adapter(tmp_path, handler)
    from integrations.contracts.distribution import ContentVariant, DistributionJob
    job = DistributionJob("j", "p", "douyin:open", ContentVariant("douyin:open", "hi"), idempotency_key="k", provider="douyin", platform="douyin", media_uploads=(MediaUploadResult(source_hash="h", source_path="a.jpg", mime_type="image/jpeg", size=1, provider="douyin", remote_id="img-1", remote_path="img-1", uploaded_at="now"),))
    result = adapter.publish(job)
    assert result["provider_object_type"] == "image_post"
    assert result["status"] == "processing"


def test_capability_evidence_not_over_verified(tmp_path):
    def handler(method, path, kwargs):
        return {"data": {"open_id": "open", "nickname": "meiti"}}
    adapter, _ = _adapter(tmp_path, handler)
    caps = adapter.verify_capabilities("douyin:open")
    assert caps.records["user_info"].verified is True
    assert caps.records["user_info"].evidence.get("endpoint")
    assert caps.records["publish"].verified is True
    assert caps.records["publish"].evidence.get("scope") == "video.create"
