from integrations.contracts.distribution import ContentVariant, DistributionJob
from social.publish.gate import admit
from tests.fixtures.fakes import FakeAdapter


def test_gate_ignores_caller_verified_flags():
    adapter = FakeAdapter()
    job = DistributionJob("j", "p", "i", ContentVariant("i", "hello", metadata={"approval": "approved"}), idempotency_key="k")
    decision = admit(job, adapter=adapter)
    assert decision.ready is True
    blocked = admit(DistributionJob("j", "p", "i", ContentVariant("i", "hello"), idempotency_key="k"), adapter=adapter)
    assert blocked.ready is False
    assert "approval invalid" in blocked.reasons


def test_xhs_handoff_does_not_require_token():
    from social.accounts.models import SocialAccount, SocialProviderCapabilities, enable_account
    from social.providers.xiaohongshu.adapter import XiaohongshuAdapter
    from social.publish.gate import admit

    adapter = XiaohongshuAdapter()
    adapter.authenticate({"username": "meiti", "account_id": "xiaohongshu:meiti"})
    caps = adapter.verify_capabilities("xiaohongshu:meiti")
    account = enable_account(SocialAccount(
        "xiaohongshu:meiti",
        "xiaohongshu",
        "xiaohongshu",
        username="meiti",
        status="VERIFIED",
        capabilities=caps,
        provider_account_id="meiti",
        region="cn",
    ))
    adapter._accounts[account.account_id] = account
    job = DistributionJob(
        "j",
        "p",
        "xiaohongshu:meiti",
        ContentVariant("xiaohongshu:meiti", "hello", media=("a.jpg",), title="hi", metadata={"approval": "approved"}),
        idempotency_key="k",
    )
    decision = admit(job, adapter=adapter, account=account)
    assert decision.ready is True
    assert all("credential" not in reason for reason in decision.reasons)
