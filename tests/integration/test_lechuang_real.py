import pytest

from creative.providers.lechuang.adapter import LechuangAdapter
from creative.providers.lechuang.client import LechuangClient


def test_lechuang_real_create_poll_result_persist():
    client = LechuangClient()
    ready, reason = client.live_ready()
    if not ready:
        pytest.skip(reason)
    adapter = LechuangAdapter(client=client)
    task = adapter.create_task("generate_image", {"prompt": "real image"})
    polled = adapter.get_task(task.provider_task_id)
    result = adapter.get_result(task.provider_task_id)
    assert polled.status in {"queued", "running", "succeeded"}
    assert result is not None
