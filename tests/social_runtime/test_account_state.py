from social.accounts.models import SocialAccount, enable_account, transition_account
import pytest


def test_authenticated_goes_through_verifying():
    account = SocialAccount("a", "douyin", "douyin", status="AUTHENTICATED")
    verifying = transition_account(account, "VERIFYING")
    verified = transition_account(verifying, "VERIFIED")
    enabled = enable_account(verified)
    assert enabled.status == "ENABLED"
    with pytest.raises(Exception):
        transition_account(account, "ENABLED")
    with pytest.raises(Exception):
        transition_account(account, "VERIFIED")
