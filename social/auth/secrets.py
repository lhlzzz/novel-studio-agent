"""Production secret store. Tokens never enter business tables or logs."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import stat
from pathlib import Path
from typing import Any

from social.auth.credentials import CredentialRecord

FORBIDDEN_COLUMNS = {"access_token", "refresh_token", "client_secret", "cookie", "session"}
FORBIDDEN_LOG_KEYS = FORBIDDEN_COLUMNS | {"authorization", "bearer", "token", "id_token"}


def secret_id(provider: str, account_id: str) -> str:
    """Stable credential identity. Filenames never contain raw provider/account."""
    digest = hashlib.sha256(f"{provider}:{account_id}".encode("utf-8")).hexdigest()
    return f"cred:{digest}"


class SecretStoreError(RuntimeError):
    """Secret storage is unusable."""


class RuntimeSecretStore:
    def __init__(self, root: Path, *, production: bool = False) -> None:
        self.root = Path(root)
        self.production = production
        self.root.mkdir(parents=True, exist_ok=True)
        os.chmod(self.root, 0o700)
        mode = stat.S_IMODE(self.root.stat().st_mode)
        if mode != 0o700:
            raise SecretStoreError(f"secret directory permissions must be 0700, got {oct(mode)}")

    def put(self, payload: dict[str, Any] | CredentialRecord, *, ref: str | None = None) -> str:
        record = payload if isinstance(payload, CredentialRecord) else CredentialRecord.from_payload(payload, ref=ref or "")
        ref = ref or record.credential_ref or f"secret:{secrets.token_hex(16)}"
        stored = record.replace() if record.credential_ref == ref else CredentialRecord.from_payload(record.to_payload(), provider=record.provider, ref=ref)
        path = self._path(ref)
        payload = stored.to_payload()
        payload.setdefault("provider", stored.provider)
        payload.setdefault("provider_account_id", stored.provider_account_id)
        payload.setdefault("created_at", stored.created_at)
        payload.setdefault("updated_at", stored.updated_at)
        payload.setdefault("expires_at", stored.expires_at)
        self._write_atomic(path, payload)
        return ref

    def put_json(self, payload: dict[str, Any], *, ref: str) -> str:
        if not ref:
            raise SecretStoreError("json secret ref is required")
        path = self._path(ref)
        self._write_atomic(path, payload)
        return ref

    def get_json(self, ref: str) -> dict[str, Any] | None:
        if not ref:
            return None
        path = self._path(ref)
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise SecretStoreError("secret payload is not an object")
        return payload

    def get(self, ref: str) -> dict[str, Any]:
        record = self.get_record(ref)
        return record.to_payload() if record is not None else {}

    def get_record(self, ref: str) -> CredentialRecord | None:
        if not ref:
            return None
        path = self._path(ref)
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise SecretStoreError("credential payload is not an object")
        return CredentialRecord.from_payload(payload, ref=ref)

    def exists(self, ref: str) -> bool:
        return bool(ref) and self._path(ref).exists()

    def rotate(self, ref: str, payload: dict[str, Any] | CredentialRecord) -> CredentialRecord:
        if not self.exists(ref):
            raise SecretStoreError(f"cannot rotate missing credential {ref}")
        return self.replace(ref, payload)

    def replace(self, ref: str, payload: dict[str, Any] | CredentialRecord) -> CredentialRecord:
        existing = self.get_record(ref)
        incoming = payload if isinstance(payload, CredentialRecord) else CredentialRecord.from_payload(payload, ref=ref)
        merged = incoming.replace(
            credential_ref=ref,
            provider=incoming.provider or (existing.provider if existing else ""),
            refresh_token=incoming.refresh_token if incoming.refresh_token else (existing.refresh_token if existing else None),
            provider_account_id=incoming.provider_account_id or (existing.provider_account_id if existing else ""),
            created_at=(existing.created_at if existing else incoming.created_at),
        )
        self.put(merged, ref=ref)
        stored = self.get_record(ref)
        if stored is None:
            raise SecretStoreError(f"credential replace failed for {ref}")
        return stored

    def delete(self, ref: str) -> None:
        path = self._path(ref)
        if path.exists():
            path.unlink()

    def doctor(self) -> dict[str, Any]:
        evidence: dict[str, Any] = {"root": str(self.root)}
        try:
            mode = stat.S_IMODE(self.root.stat().st_mode)
            evidence["directory_mode"] = oct(mode)
            if mode != 0o700:
                return {"ok": False, "reason": f"directory mode {oct(mode)} != 0700", **evidence}
            probe_ref = "secret:doctor-roundtrip"
            self.put(CredentialRecord.from_payload({"access_token": "doctor-token", "provider": "doctor"}, ref=probe_ref), ref=probe_ref)
            path = self._path(probe_ref)
            file_mode = stat.S_IMODE(path.stat().st_mode)
            evidence["file_mode"] = oct(file_mode)
            loaded = self.get_record(probe_ref)
            self.delete(probe_ref)
            if file_mode != 0o600:
                return {"ok": False, "reason": f"file mode {oct(file_mode)} != 0600", **evidence}
            if loaded is None or loaded.access_token != "doctor-token":
                return {"ok": False, "reason": "read/write roundtrip failed", **evidence}
            if path.exists():
                return {"ok": False, "reason": "delete failed", **evidence}
            return {"ok": True, **evidence}
        except Exception as exc:
            return {"ok": False, "reason": str(exc), **evidence}

    def _write_atomic(self, path: Path, payload: dict[str, Any]) -> None:
        tmp = path.with_name(f"{path.name}.tmp.{os.getpid()}.{secrets.token_hex(8)}")
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_TRUNC
        fd = os.open(tmp, flags, 0o600)
        replaced = False
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fd = None
                json.dump(payload, fh)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, path)
            replaced = True
        finally:
            if fd is not None:
                os.close(fd)
            if not replaced and tmp.exists():
                tmp.unlink()
        dir_fd = os.open(str(path.parent), os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)

    def _path(self, ref: str) -> Path:
        digest = hashlib.sha256(str(ref).encode("utf-8")).hexdigest()
        return self.root / f"{digest}.json"


def production_secret_store() -> RuntimeSecretStore:
    root = os.environ.get("MEITI_SECRET_DIR", "").strip()
    if not root:
        raise SecretStoreError("MEITI_SECRET_DIR is required for production secret storage")
    return RuntimeSecretStore(Path(root), production=True)


class UnconfiguredSecretStore:
    """Constructable without MEITI_SECRET_DIR. Reads are empty; writes are BLOCKED."""

    production = False

    def put(self, payload, *, ref: str | None = None) -> str:
        raise SecretStoreError("MEITI_SECRET_DIR is required; production services must not default to /tmp")

    def get(self, ref: str) -> dict[str, Any]:
        return {}

    def put_json(self, payload: dict[str, Any], *, ref: str) -> str:
        raise SecretStoreError("MEITI_SECRET_DIR is required; production services must not default to /tmp")

    def get_json(self, ref: str) -> dict[str, Any] | None:
        return None

    def get_record(self, ref: str) -> CredentialRecord | None:
        return None

    def exists(self, ref: str) -> bool:
        return False

    def rotate(self, ref: str, payload) -> CredentialRecord:
        raise SecretStoreError("MEITI_SECRET_DIR is required")

    def replace(self, ref: str, payload) -> CredentialRecord:
        raise SecretStoreError("MEITI_SECRET_DIR is required")

    def delete(self, ref: str) -> None:
        return None

    def doctor(self) -> dict[str, Any]:
        return {"ok": False, "reason": "MEITI_SECRET_DIR missing"}


def default_secret_store() -> RuntimeSecretStore | UnconfiguredSecretStore:
    root = os.environ.get("MEITI_SECRET_DIR", "").strip()
    if not root:
        return UnconfiguredSecretStore()
    return RuntimeSecretStore(Path(root), production=True)
