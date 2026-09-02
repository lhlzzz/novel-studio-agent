import os
import stat

from social.auth.credentials import CredentialRecord
from social.auth.secrets import RuntimeSecretStore


def test_credential_put_get_replace_rotate_delete(tmp_path):
    store = RuntimeSecretStore(tmp_path)
    ref = store.put(CredentialRecord.from_payload({"provider": "douyin", "access_token": "a", "refresh_token": "r", "scope": "video.create"}))
    loaded = store.get_record(ref)
    assert loaded.access_token == "a"
    replaced = store.replace(ref, CredentialRecord.from_payload({"provider": "douyin", "access_token": "b"}))
    assert replaced.access_token == "b"
    assert replaced.refresh_token == "r"
    store.rotate(ref, {"provider": "douyin", "access_token": "c", "refresh_token": "r2"})
    assert store.get_record(ref).access_token == "c"
    store.delete(ref)
    assert store.get_record(ref) is None


def test_secret_permissions(tmp_path):
    store = RuntimeSecretStore(tmp_path)
    ref = store.put({"provider": "douyin", "access_token": "tok"})
    assert stat.S_IMODE(tmp_path.stat().st_mode) == 0o700
    assert stat.S_IMODE(store._path(ref).stat().st_mode) == 0o600


def test_restart_persistence(tmp_path):
    store = RuntimeSecretStore(tmp_path)
    ref = store.put({"provider": "kuaishou", "access_token": "tok", "expires_in": 3600})
    again = RuntimeSecretStore(tmp_path)
    loaded = again.get_record(ref)
    assert loaded.access_token == "tok"
    assert loaded.expires_at
