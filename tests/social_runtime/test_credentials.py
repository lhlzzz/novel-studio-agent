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


def test_secret_id_is_hashed_not_plaintext():
    from social.auth.secrets import secret_id
    value = secret_id("douyin", "open-id-1")
    assert value.startswith("cred:")
    assert "douyin" not in value
    assert "open-id-1" not in value


def test_get_credentials_does_not_refresh(tmp_path):
    from social.accounts.models import SocialAccount
    from social.auth.credentials import CredentialRecord
    from social.runtime.container import SocialRuntime
    runtime = SocialRuntime.testing()
    ref = runtime.secrets.put(CredentialRecord.from_payload({"provider": "douyin", "access_token": "tok", "refresh_token": "rt", "provider_account_id": "x"}))
    account = runtime.manager.save(SocialAccount("douyin:x", "douyin", "douyin", credential_ref=ref, provider_account_id="x", status="AUTHENTICATED"))
    loaded = runtime.manager.get_credentials(account.account_id)
    assert loaded.access_token == "tok"
    assert runtime.secrets.get_record(ref).access_token == "tok"


def test_simultaneous_replace_does_not_leave_corrupt_json(tmp_path):
    import json
    import threading
    store = RuntimeSecretStore(tmp_path)
    ref = store.put({"provider": "douyin", "access_token": "start", "refresh_token": "keep"})
    errors = []

    def writer(idx: int):
        try:
            store.replace(ref, {"provider": "douyin", "access_token": f"tok-{idx}"})
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=writer, args=(i,)) for i in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []
    loaded = store.get_record(ref)
    assert loaded is not None
    assert loaded.access_token.startswith("tok-")
    assert loaded.refresh_token == "keep"
    payload = json.loads(store._path(ref).read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    leftovers = list(tmp_path.glob("*.tmp*"))
    assert leftovers == []
