"""Native social provider errors. Retry only network/timeout/429/5xx."""

from __future__ import annotations


class SocialProviderError(RuntimeError):
    retryable = False


class AuthenticationError(SocialProviderError):
    retryable = False


class AuthorizationError(SocialProviderError):
    retryable = False


class RateLimitError(SocialProviderError):
    retryable = True

    def __init__(self, message: str, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class ValidationError(SocialProviderError):
    retryable = False


class ProviderError(SocialProviderError):
    retryable = False


class NotFoundError(SocialProviderError):
    retryable = False


class NetworkError(SocialProviderError):
    retryable = True


class TimeoutError(SocialProviderError):
    retryable = True


class ServerError(SocialProviderError):
    retryable = True


def classify_http_error(status: int, detail: str, retry_after: float | None = None) -> SocialProviderError:
    if status in {401}:
        return AuthenticationError(detail)
    if status in {403}:
        return AuthorizationError(detail)
    if status == 404:
        return NotFoundError(detail)
    if status == 429:
        return RateLimitError(detail, retry_after=retry_after)
    if status in {400, 409, 422}:
        return ValidationError(detail)
    if status >= 500:
        return ServerError(detail)
    return ProviderError(detail)
