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
    from social.accounts.models import SocialAccount, SocialProviderCapabilities
    from social.providers.xiaohongshu.adapter import XiaohongshuAdapter
    from social.publish.gate import admit

    adapter = XiaohongshuAdapter()
    adapter.authenticate({"username": "meiti", "account_id": "xiaohongshu:meiti"})
    caps = adapter.verify_capabilities("xiaohongshu:meiti")
    account = SocialAccount(
        "xiaohongshu:meiti",
        "xiaohongshu",
        "xiaohongshu",
        username="meiti",
        status="HANDOFF_READY",
        capabilities=caps,
        provider_account_id="meiti",
        region="cn",
    )
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


def test_gate_blocks_missing_credential():
    from dataclasses import replace
    from social.accounts.models import SocialAccount, SocialProviderCapabilities, enable_account
    from tests.fakes.social.adapter import FakeAdapter
    adapter = FakeAdapter()
    adapter.account = replace(adapter.account, credential_ref="")
    job = DistributionJob("j", "p", "i", ContentVariant("i", "hello", metadata={"approval": "approved"}), idempotency_key="k", provider="x", platform="x")
    decision = admit(job, adapter=adapter, account=adapter.account)
    assert decision.ready is False
    assert "account credential unusable" in decision.reasons


def test_gate_blocks_unverified_capability():
    from dataclasses import replace
    from social.accounts.models import SocialProviderCapabilities
    from tests.fakes.social.adapter import FakeAdapter
    adapter = FakeAdapter()
    adapter.account = replace(adapter.account, capabilities=SocialProviderCapabilities.from_claimed({"publish": True}, verified=False))
    job = DistributionJob("j", "p", "i", ContentVariant("i", "hello", metadata={"approval": "approved"}), idempotency_key="k")
    decision = admit(job, adapter=adapter, account=adapter.account)
    assert decision.ready is False
    assert "capability unverified" in decision.reasons
