"""Runtime secret store. Business tables may store credential_ref only."""

from __future__ import annotations

import json
import os
import secrets
import tempfile
from pathlib import Path
from typing import Any

FORBIDDEN_COLUMNS = {"access_token", "refresh_token", "client_secret", "cookie", "session"}


class RuntimeSecretStore:
    def __init__(self, root: Path | None = None) -> None:
        default = Path(os.environ.get("MEITI_SECRET_DIR") or (Path(tempfile.gettempdir()) / "meiti-secrets"))
        self.root = Path(root or default)
        self.root.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.root, 0o700)
        except OSError:
            pass
        self._memory: dict[str, dict[str, Any]] = {}

    def put(self, payload: dict[str, Any], *, ref: str | None = None) -> str:
        ref = ref or f"secret:{secrets.token_hex(16)}"
        clean = {key: value for key, value in payload.items() if value is not None}
        self._memory[ref] = dict(clean)
        path = self._path(ref)
        path.write_text(json.dumps(clean), encoding="utf-8")
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
        return ref

    def get(self, ref: str) -> dict[str, Any]:
        if ref in self._memory:
            return dict(self._memory[ref])
        path = self._path(ref)
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    def delete(self, ref: str) -> None:
        self._memory.pop(ref, None)
        path = self._path(ref)
        if path.exists():
            path.unlink()

    def _path(self, ref: str) -> Path:
        safe = ref.replace("/", "_").replace("..", "_")
        return self.root / f"{safe}.json"


_DEFAULT: RuntimeSecretStore | None = None


def default_secret_store() -> RuntimeSecretStore:
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = RuntimeSecretStore()
    return _DEFAULT
