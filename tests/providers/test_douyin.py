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


def test_multi_account_douyin_status(tmp_path):
    seen = []
    def handler(method, path, kwargs):
        seen.append(kwargs)
        return {"data": {"list": [{"item_id": "item-b", "video_status": 5}]}}
    adapter, _ = _adapter(tmp_path, handler)
    secrets = adapter.secrets
    from social.auth.credentials import CredentialRecord
    from social.accounts.models import SocialAccount, SocialProviderCapabilities
    ref_a = secrets.put(CredentialRecord.from_payload({"provider": "douyin", "access_token": "token-a", "provider_account_id": "open-a"}))
    ref_b = secrets.put(CredentialRecord.from_payload({"provider": "douyin", "access_token": "token-b", "provider_account_id": "open-b"}))
    account_a = SocialAccount("douyin:open-a", "douyin", "douyin", username="a", status="ENABLED", provider_account_id="open-a", credential_ref=ref_a, capabilities=SocialProviderCapabilities.from_claimed({"publish": True}))
    account_b = SocialAccount("douyin:open-b", "douyin", "douyin", username="b", status="ENABLED", provider_account_id="open-b", credential_ref=ref_b, capabilities=SocialProviderCapabilities.from_claimed({"publish": True}))
    adapter.bind_account(account_a)
    adapter.bind_account(account_b)
    status = adapter.get_status("item-b", account_id="douyin:open-b", provider_object_type="video")
    assert status["id"] == "item-b"
    headers = seen[0].get("headers") or {}
    blob = str(headers)
    assert "token-b" in blob
    assert "token-a" not in blob


def test_multi_account_analytics(tmp_path):
    seen = []
    def handler(method, path, kwargs):
        seen.append(kwargs)
        return {"data": {"list": [{"item_id": "item-b", "statistics": {"play_count": 1}}]}}
    adapter, _ = _adapter(tmp_path, handler)
    secrets = adapter.secrets
    from social.auth.credentials import CredentialRecord
    from social.accounts.models import SocialAccount, SocialProviderCapabilities
    from integrations.contracts.distribution import Publication
    ref_a = secrets.put(CredentialRecord.from_payload({"provider": "douyin", "access_token": "token-a", "provider_account_id": "open-a"}))
    ref_b = secrets.put(CredentialRecord.from_payload({"provider": "douyin", "access_token": "token-b", "provider_account_id": "open-b"}))
    adapter.bind_account(SocialAccount("douyin:open-a", "douyin", "douyin", username="a", status="ENABLED", provider_account_id="open-a", credential_ref=ref_a, capabilities=SocialProviderCapabilities.from_claimed({"analytics": True})))
    adapter.bind_account(SocialAccount("douyin:open-b", "douyin", "douyin", username="b", status="ENABLED", provider_account_id="open-b", credential_ref=ref_b, capabilities=SocialProviderCapabilities.from_claimed({"analytics": True})))
    adapter.analytics(Publication("job-b", "douyin:open-b", "douyin", "item-b", platform="douyin"))
    blob = str(seen[0].get("headers") or "")
    assert "token-b" in blob
    assert "token-a" not in blob


def test_open_id_maps_into_credential_record():
    record = CredentialRecord.from_payload({"provider": "douyin", "access_token": "tok", "open_id": "open-live", "scope": "user_info"})
    assert record.provider_account_id == "open-live"


def test_image_upload_uses_multipart(tmp_path):
    seen = []
    def handler(method, path, kwargs):
        seen.append(kwargs)
        return {"data": {"image_id": "img-1"}, "extra": {"error_code": 0, "logid": "log-1"}}
    adapter, _ = _adapter(tmp_path, handler)
    result = adapter._upload_bytes(b"jpeg", mime_type="image/jpeg", filename="a.jpg", account_id="douyin:open", idempotency_key="k")
    assert result["id"] == "img-1"
    assert result["provider_request_id"] == "log-1"
    assert "image" in (seen[0].get("files") or {})


def test_http_200_error_code_is_not_success(tmp_path):
    import pytest
    from social.providers.errors import MediaUploadError
    def handler(method, path, kwargs):
        return {"data": {"error_code": 2100005, "description": "Parameter error"}, "extra": {"error_code": 2100005, "logid": "log-err"}}
    adapter, _ = _adapter(tmp_path, handler)
    with pytest.raises(MediaUploadError):
        adapter._upload_bytes(b"jpeg", mime_type="image/jpeg", filename="a.jpg", account_id="douyin:open", idempotency_key="k")


def test_analytics_reads_nested_statistics(tmp_path):
    from integrations.contracts.distribution import Publication
    def handler(method, path, kwargs):
        return {"data": {"list": [{"item_id": "item-b", "statistics": {"play_count": 9, "digg_count": 3, "comment_count": 1, "share_count": 2}}]}}
    adapter, _ = _adapter(tmp_path, handler)
    metrics = adapter.analytics(Publication("job-b", "douyin:open", "douyin", "item-b", platform="douyin"))
    assert metrics["views"] == 9
    assert metrics["likes"] == 3
    assert metrics["comments"] == 1
    assert metrics["shares"] == 2
    assert metrics["followers_delta"] is None


def test_complete_oauth_binds_unconfigured_adapter_and_survives_restart(tmp_path, monkeypatch):
    from social.auth.secrets import UnconfiguredSecretStore
    from social.runtime.container import SocialRuntime
    monkeypatch.setenv("DOUYIN_CLIENT_KEY", "key")
    monkeypatch.setenv("DOUYIN_CLIENT_SECRET", "secret")
    monkeypatch.setenv("DOUYIN_REDIRECT_URI", "http://127.0.0.1:8787/oauth/douyin")
    runtime = SocialRuntime.testing()
    def handler(method, path, kwargs):
        if "access_token" in path:
            return {"data": {"access_token": "tok", "refresh_token": "rt", "open_id": "open-live", "scope": "user_info,video.create,video.data", "expires_in": 1296000, "error_code": 0}}
        if "userinfo" in path:
            return {"data": {"open_id": "open-live", "nickname": "meiti-e2e", "error_code": 0}}
        return {"data": {"error_code": 0}}
    adapter = DouyinAdapter(client=DouyinClient(http=FakeHttp(handler)), secrets=UnconfiguredSecretStore())
    start = runtime.manager.start_oauth("douyin", adapter=adapter)
    account = runtime.manager.complete_oauth("douyin", code="auth-code", state=start.state, adapter=adapter)
    assert account.account_id == "douyin:open-live"
    assert account.credential_ref
    assert "tok" not in account.account_id
    record = runtime.secrets.get_record(account.credential_ref)
    assert record.access_token == "tok"
    assert record.provider_account_id == "open-live"
    loaded = runtime.manager.get_account(account.account_id)
    assert loaded.account_id == account.account_id
    fresh = DouyinAdapter(client=DouyinClient(http=FakeHttp(handler)), secrets=UnconfiguredSecretStore())
    verified = runtime.manager.verify_account(loaded.account_id, adapter=fresh)
    assert verified.status == "VERIFIED"
    assert verified.capabilities.records["publish"].authorized is True
    assert verified.capabilities.records["publish"].live_verified is False
