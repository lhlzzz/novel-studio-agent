from datetime import datetime, timedelta, timezone

import pytest
from social.auth.oauth import OAuthStart, OAuthStateStore, generate_pkce
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
