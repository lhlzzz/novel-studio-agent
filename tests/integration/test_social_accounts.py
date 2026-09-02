from social.accounts.manager import SocialAccountManager
from social.accounts.models import SocialAccount, SocialProviderCapabilities, enable_account
from tests.e2e.fake_x import FakeXAdapter


def test_account_manager_connect_verify_enable():
    adapter = FakeXAdapter()
    adapter.account = SocialAccount(
        "x-test", "x", "x", username="meiti", status="AUTHENTICATED",
        capabilities=SocialProviderCapabilities.from_claimed({"publish": True, "text": True}, verified=False),
    )
    manager = SocialAccountManager()
    connected = manager.connect_account("x", adapter=adapter)
    assert connected.status == "AUTHENTICATED"
    verified = manager.verify_account(connected.account_id, adapter=adapter)
    assert verified.status == "VERIFIED"
    enabled = manager.enable_account(verified.account_id)
    assert enabled.status == "ENABLED"


def test_only_verified_can_enable():
    import pytest
    account = SocialAccount("a", "x", "x", status="AUTHENTICATED")
    with pytest.raises(ValueError):
        enable_account(account)
