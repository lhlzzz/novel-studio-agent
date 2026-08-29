from integrations.providers.postiz.errors import NetworkError, ValidationError
from services.queue import WorkQueue


def test_permanent_failure_dead_letters():
    queue = WorkQueue(max_attempts=3)
    queue.enqueue("job-1", {"action": "publish"})
    for _ in range(3):
        item = queue.fail("job-1", error_code="ValidationError", error_message="bad payload", provider_response={"ok": False})
    assert item.status == "dead_letter"
    assert item.attempt_count == 3
    assert item.error_code == "ValidationError"
    assert item.provider_response == {"ok": False}


def test_retryable_network_error_flag():
    assert NetworkError("down").retryable is True
    assert ValidationError("bad").retryable is False
