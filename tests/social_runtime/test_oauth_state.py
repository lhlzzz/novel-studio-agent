from datetime import datetime, timedelta, timezone

import pytest
from social.auth.oauth import OAuthStart, OAuthStateStore, generate_pkce, listen_for_callback
from social.auth.secrets import RuntimeSecretStore
from social.providers.errors import AuthenticationError
from social.runtime.container import SocialRuntime


def test_oauth_state_save_consume_and_replay(tmp_path):
    secrets = RuntimeSecretStore(tmp_path)
    store = OAuthStateStore(secrets)
    start = OAuthStart(url="https://open.douyin.com/platform/oauth/connect?x=1", state="abc", provider="douyin", redirect_uri="https://meiti.local/cb", code_verifier="verifier")
    store.save(start)
    payload = store.consume("douyin", "abc")
    assert payload["code_verifier"] == "verifier"
    with pytest.raises(AuthenticationError):
        store.consume("douyin", "abc")


def test_oauth_state_provider_mismatch_and_expiry(tmp_path):
    secrets = RuntimeSecretStore(tmp_path)
    store = OAuthStateStore(secrets)
    start = OAuthStart(url="https://example/oauth", state="s1", provider="douyin", redirect_uri="https://cb")
    store.save(start, ttl_seconds=600)
    with pytest.raises(AuthenticationError):
        store.consume("kuaishou", "s1")
    store.save(OAuthStart(url="https://example/oauth", state="s2", provider="douyin", redirect_uri="https://cb"), ttl_seconds=-1)
    with pytest.raises(AuthenticationError):
        store.consume("douyin", "s2")


def test_pkce_roundtrip():
    verifier, challenge = generate_pkce()
    assert verifier
    assert challenge
    assert verifier != challenge


def test_complete_oauth_requires_state():
    runtime = SocialRuntime.testing()
    with pytest.raises(Exception):
        runtime.manager.connect_account("douyin", authorization={"code": "x"})


def test_oauth_redirect_uri_binding(tmp_path):
    secrets = RuntimeSecretStore(tmp_path)
    store = OAuthStateStore(secrets)
    store.save(OAuthStart(url="https://example/oauth", state="s3", provider="douyin", redirect_uri="https://cb/a"))
    with pytest.raises(AuthenticationError):
        store.consume("douyin", "s3", redirect_uri="https://cb/other")
    store.save(OAuthStart(url="https://example/oauth", state="s4", provider="douyin", redirect_uri="https://cb/a"))
    payload = store.consume("douyin", "s4", redirect_uri="https://cb/a")
    assert payload["redirect_uri"] == "https://cb/a"


def test_listen_for_callback_roundtrip():
    import socket
    import threading
    import time
    from urllib.request import urlopen

    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    uri = f"http://127.0.0.1:{port}/oauth/douyin"
    box: dict[str, dict[str, str]] = {}

    def run() -> None:
        box["payload"] = listen_for_callback(uri, timeout=5)

    thread = threading.Thread(target=run)
    thread.start()
    last_error = None
    for _ in range(20):
        try:
            urlopen(f"{uri}?code=test-code&state=test-state", timeout=2).read()
            last_error = None
            break
        except Exception as exc:
            last_error = exc
            time.sleep(0.05)
    thread.join(5)
    assert last_error is None
    assert box["payload"]["code"] == "test-code"
    assert box["payload"]["state"] == "test-state"


def test_real_e2e_reads_nested_providers(tmp_path, monkeypatch):
    import json
    from scripts import social_doctor

    path = tmp_path / "e2e.json"
    path.write_text(json.dumps({"providers": {"douyin": {"oauth": "PASS", "real_e2e": True}}}), encoding="utf-8")
    monkeypatch.setattr(social_doctor, "AUDIT_PATHS", (path,))
    data = social_doctor._real_e2e("douyin")
    assert data["oauth"] == "PASS"
    assert data["real_e2e"] is True


def test_oauth_start_cli_exists():
    import scripts.meiti as meiti
    source = (meiti.ROOT / "scripts/meiti.py").read_text(encoding="utf-8")
    assert 'social_sub.add_parser("oauth-start")' in source
    assert 'connect.add_argument("--state")' in source
