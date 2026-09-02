from social.providers.errors import AuthenticationError, RateLimitError, ValidationError, classify_http_error


def test_error_retry_policy():
    assert classify_http_error(401, "no").retryable is False
    assert isinstance(classify_http_error(401, "no"), AuthenticationError)
    assert classify_http_error(429, "slow").retryable is True
    assert isinstance(classify_http_error(429, "slow"), RateLimitError)
    assert ValidationError("bad").retryable is False
    assert classify_http_error(503, "down").retryable is True
