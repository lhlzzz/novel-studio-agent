"""Typed Postiz HTTP errors used to decide retry vs fail-closed."""

from __future__ import annotations


class PostizError(RuntimeError):
    retryable = False
    reauthenticate = False


class PostizClientError(PostizError):
    """Client-side Postiz boundary error."""


class PostizNetworkError(PostizClientError):
    retryable = True


class NetworkError(PostizNetworkError):
    """Short name retained for existing callers."""


class PostizTimeoutError(PostizNetworkError):
    """Network timeout; safe to retry within the bounded policy."""


class PostizAuthenticationError(PostizClientError):
    reauthenticate = True


class AuthenticationError(PostizAuthenticationError):
    """Short name retained for existing callers."""


class PostizAuthorizationError(PostizClientError):
    reauthenticate = True


class AuthorizationError(PostizAuthorizationError):
    """Short name retained for existing callers."""


class PostizRateLimitError(PostizClientError):
    retryable = True

    def __init__(self, message: str, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class RateLimitError(PostizRateLimitError):
    """Short name retained for existing callers."""


class PostizValidationError(PostizClientError):
    """Request rejected by Postiz validation."""


class ValidationError(PostizValidationError):
    """Short name retained for existing callers."""


class PostizProviderError(PostizClientError):
    """Downstream provider rejected the operation."""


class ProviderError(PostizProviderError):
    """Short name retained for existing callers."""


class PostizNotFoundError(PostizClientError):
    """Requested Postiz object does not exist."""


class NotFoundError(PostizNotFoundError):
    """Short name retained for existing callers."""


class PostizServerError(PostizClientError):
    retryable = True


class ServerError(PostizServerError):
    """Short name retained for existing callers."""


class UnknownPostizError(PostizClientError):
    """Unclassified non-retryable Postiz response."""


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
