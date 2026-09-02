"""Native social provider errors. Retry only network/timeout/429/5xx."""

from __future__ import annotations


class SocialProviderError(RuntimeError):
    retryable = False
    unknown = False
    http_status = None
    provider_error_code = None
    provider_error_message = None
    request_id = None

    def __init__(self, message: str, *, http_status: int | None = None, provider_error_code: str | None = None, provider_error_message: str | None = None, request_id: str | None = None) -> None:
        super().__init__(message)
        self.http_status = http_status
        self.provider_error_code = provider_error_code
        self.provider_error_message = provider_error_message or message
        self.request_id = request_id


class AuthenticationError(SocialProviderError):
    retryable = False


class PermissionError(SocialProviderError):
    retryable = False

    def __init__(self, message: str, *, kind: str = "permission_missing", http_status: int | None = None) -> None:
        super().__init__(message, http_status=http_status)
        self.kind = kind


class RateLimitError(SocialProviderError):
    retryable = True

    def __init__(self, message: str, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class ValidationError(SocialProviderError):
    retryable = False


class ProviderError(SocialProviderError):
    retryable = False


class ProviderContractError(SocialProviderError):
    retryable = False


class ProviderUnavailable(SocialProviderError):
    retryable = True


class UnsupportedCapability(SocialProviderError):
    retryable = False


class RemoteObjectNotFound(SocialProviderError):
    retryable = False


class RemoteProcessing(SocialProviderError):
    retryable = True
    unknown = True


class NotFoundError(RemoteObjectNotFound):
    pass


class NetworkError(SocialProviderError):
    retryable = True
    unknown = True


class TimeoutError(SocialProviderError):
    retryable = True
    unknown = True


class ServerError(ProviderUnavailable):
    retryable = True


def classify_http_error(status: int, detail: str, retry_after: float | None = None) -> SocialProviderError:
    text = str(detail or "").lower()
    if status == 401 or "invalid_token" in text or "token_expired" in text:
        if "expired" in text or "token_expired" in text:
            err = TokenExpired(detail, http_status=status)
        elif "revoked" in text or "invalid" in text:
            err = AuthenticationError(detail, http_status=status)
        else:
            err = AuthenticationError(detail, http_status=status)
        return err
    if status == 403:
        if any(token in text for token in ("scope", "permission", "insufficient")):
            return AuthorizationDenied(detail, kind="scope_missing")
        if any(token in text for token in ("restricted", "unpublished", "audit", "not approved", "unaudited", "app review")):
            return PermissionError(detail, kind="provider_restriction")
        if any(token in text for token in ("account", "user", "page")):
            return AccountBlocked(detail)
        return AuthorizationDenied(detail, kind="permission_missing")
    if status == 404:
        return RemoteObjectNotFound(detail, http_status=status)
    if status == 429:
        return RateLimitError(detail, retry_after=retry_after)
    if status in {400, 409, 422}:
        if "invalid_grant" in text or "revoked" in text:
            return AuthenticationError(detail, http_status=status)
        return ValidationError(detail, http_status=status)
    if status >= 500:
        return ServerError(detail, http_status=status)
    return ProviderError(detail, http_status=status)


def classify_oauth_error(payload: dict | str) -> SocialProviderError:
    if isinstance(payload, str):
        text = payload.lower()
        data = {"error": payload}
    else:
        data = payload or {}
        text = str(data.get("error") or data.get("error_description") or "").lower()
    if "invalid_grant" in text or "revoked" in text:
        return AuthenticationError(str(data))
    if "invalid_token" in text or "expired" in text:
        return AuthenticationError(str(data))
    return AuthenticationError(str(data))


class TokenExpired(AuthenticationError):
    retryable = False


class AuthorizationDenied(PermissionError):
    retryable = False


class CapabilityUnsupported(UnsupportedCapability):
    retryable = False


class PlatformValidationError(ValidationError):
    retryable = False


class MediaUploadError(SocialProviderError):
    retryable = False


class PublishError(SocialProviderError):
    retryable = False


class AccountBlocked(SocialProviderError):
    retryable = False


class PolicyBlocked(SocialProviderError):
    retryable = False


RateLimited = RateLimitError
RemoteNotFound = RemoteObjectNotFound
