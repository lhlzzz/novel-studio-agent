"""Media agent runtime validates and hashes local assets before provider upload."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any


class MediaAgent:
    name = "media-agent"
    owner = "media"
    capabilities = ("validate", "prepare", "hash")
    state_store = "postgres:agent_records"
    tests = ("tests/unit/test_media_upload.py",)

    def run(self, task: dict[str, Any]) -> dict[str, Any]:
        paths = [Path(item) for item in task.get("media") or task.get("media_assets") or []]
        missing = [str(path) for path in paths if not path.is_file()]
        ready = []
        for path in paths:
            if not path.is_file():
                continue
            digest = hashlib.sha256()
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
            ready.append({
                "source_path": str(path),
                "source_hash": digest.hexdigest(),
                "size": path.stat().st_size,
                "mime_type": None,
            })
        return {
            "agent": self.name,
            "valid": not missing,
            "missing": missing,
            "ready": ready,
        }
