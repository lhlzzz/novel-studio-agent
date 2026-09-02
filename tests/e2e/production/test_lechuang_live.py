from creative.providers.lechuang.adapter import LechuangAdapter


def test_lechuang_live_is_blocked_without_contract_and_key():
    adapter = LechuangAdapter()
    ready, reason = adapter.live_ready()
    assert ready is False
    assert reason
