"""Typed Postiz HTTP errors used to decide retry vs fail-closed."""

from __future__ import annotations


class PostizClientError(RuntimeError):
    retryable = False
    reauthenticate = False


class NetworkError(PostizClientError):
    retryable = True


class AuthenticationError(PostizClientError):
    reauthenticate = True


class AuthorizationError(PostizClientError):
    reauthenticate = True


class RateLimitError(PostizClientError):
    retryable = True

    def __init__(self, message: str, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class ValidationError(PostizClientError):
    retryable = False


class ProviderError(PostizClientError):
    retryable = False


class NotFoundError(PostizClientError):
    retryable = False


class ServerError(PostizClientError):
    retryable = True


class UnknownPostizError(PostizClientError):
    retryable = False


def classify_http_error(status: int, detail: str, retry_after: float | None = None) -> PostizClientError:
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
    if status in {502, 503, 504} or status >= 500:
        return ServerError(detail)
    return UnknownPostizError(detail)
