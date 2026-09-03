import pytest

from creative.errors import UnsupportedCapability
from creative.providers.lechuang.adapter import LechuangAdapter
from creative.providers.lechuang.client import VIDEO_NOT_VERIFIED


def test_lechuang_live_is_blocked_without_key():
    adapter = LechuangAdapter()
    ready, reason = adapter.live_ready()
    if ready:
        assert adapter.has_verified("text_to_image")
        with pytest.raises(UnsupportedCapability):
            adapter.generate_video({"prompt": "nope"})
        return
    assert "XIAOLEAI_API_KEY" in reason or reason


def test_video_stays_not_verified():
    adapter = LechuangAdapter()
    status = adapter.capability_status("text_to_video")
    assert status["status"] == "NOT_VERIFIED"
    assert VIDEO_NOT_VERIFIED in status["reason"]
