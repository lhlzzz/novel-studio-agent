from dataclasses import replace

from social.accounts.models import SocialAccount, SocialProviderCapabilities, enable_account, transition_account
from social.auth.credentials import CredentialRecord
from social.auth.oauth import RevokeResult
from social.providers.errors import CapabilityUnsupported
from social.runtime.container import SocialRuntime
import pytest


class _Auth:
    def __init__(self):
        self.refreshed = []
        self.revoked = []

    def refresh(self, refresh_token):
        self.refreshed.append(refresh_token)
        return CredentialRecord.from_payload({"provider": "douyin", "access_token": "new", "provider_account_id": "open"})

    def revoke(self, token, *, token_type_hint="access_token"):
        self.revoked.append(token)
        return RevokeResult(remote_revoked=False, unsupported=True, reason="no endpoint")


class _Adapter:
    provider = "douyin"

    def __init__(self, account, auth):
        self.account = account
        self.auth = auth
        self._accounts = {account.account_id: account}

    def list_accounts(self):
        return [self.account]

    def get_account(self, account_id):
        return self.account

    def verify_capabilities(self, account_id):
        return self.account.capabilities

    def authenticate(self, authorization=None):
        return True


def _enabled(runtime):
    caps = SocialProviderCapabilities.from_claimed({"publish": True, "video": True, "media_upload": True}, verified=True, method="test")
    account = SocialAccount("douyin:open", "douyin", "douyin", username="meiti", status="AUTHENTICATED", capabilities=caps, provider_account_id="open")
    account = runtime.manager.save(account)
    account = runtime.manager.save(transition_account(account, "VERIFYING"))
    account = runtime.manager.save(transition_account(account, "VERIFIED", capabilities=caps))
    return runtime.manager.save(enable_account(account))


def test_refresh_keeps_refresh_token_and_verifies():
    runtime = SocialRuntime.testing()
    account = _enabled(runtime)
    ref = runtime.secrets.put(CredentialRecord.from_payload({"provider": "douyin", "access_token": "old", "refresh_token": "keep-me", "provider_account_id": "open"}))
    account = runtime.manager.save(replace(account, credential_ref=ref))
    auth = _Auth()
    adapter = _Adapter(account, auth)
    refreshed = runtime.manager.refresh_account(account.account_id, adapter=adapter)
    assert runtime.secrets.get_record(ref).refresh_token == "keep-me"
    assert runtime.secrets.get_record(ref).access_token == "new"
    assert refreshed.status in {"ENABLED", "VERIFIED"}
    assert auth.refreshed == ["keep-me"]


def test_xhs_refresh_not_supported():
    runtime = SocialRuntime.testing()
    account = runtime.manager.save(SocialAccount("xiaohongshu:meiti", "xiaohongshu", "xiaohongshu", username="meiti", status="HANDOFF_READY", provider_account_id="meiti"))
    with pytest.raises(CapabilityUnsupported):
        runtime.manager.refresh_account(account.account_id)


def test_disconnect_deletes_local_credential():
    runtime = SocialRuntime.testing()
    account = _enabled(runtime)
    ref = runtime.secrets.put({"provider": "douyin", "access_token": "tok", "refresh_token": "r"})
    account = runtime.manager.save(replace(account, credential_ref=ref))
    auth = _Auth()
    adapter = _Adapter(account, auth)
    revoked = runtime.manager.disconnect_account(account.account_id, adapter=adapter)
    assert revoked.status == "REVOKED"
    assert runtime.secrets.get_record(ref) is None
    assert revoked.revoke_attempted is True
    assert revoked.remote_revoke_supported is False
