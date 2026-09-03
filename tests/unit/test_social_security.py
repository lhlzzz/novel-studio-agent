from social.auth.secrets import RuntimeSecretStore, FORBIDDEN_COLUMNS
from content.models import ContentPackage


def test_credentials_not_persisted_plaintext(tmp_path):
    store = RuntimeSecretStore(root=tmp_path)
    ref = store.put({"access_token": "tok-secret", "refresh_token": "ref-secret"})
    assert "tok-secret" not in ref
    payload = store.get(ref)
    assert payload["access_token"] == "tok-secret"


def test_provider_secrets_not_in_content_package():
    package = ContentPackage("pkg", "title", "body", metadata={"caption": "hi"})
    dumped = str(package)
    assert "access_token" not in dumped
    assert "refresh_token" not in dumped
    assert FORBIDDEN_COLUMNS


def test_token_never_logged():
    from governance.observability import log_event
    logged = log_event(agent="social-provider", action="publish", status="ok", access_token="leak", authorization="Bearer leak")
    assert logged["access_token"] == "[redacted]"
    assert logged["authorization"] == "[redacted]"


def test_bearer_token_redacted():
    from governance.observability import log_event
    logged = log_event(agent="social-provider", action="publish", status="error", error_message="Authorization: Bearer super-secret-token")
    dumped = str(logged)
    assert "super-secret-token" not in dumped
    assert "Bearer" not in dumped or "[redacted]" in dumped
