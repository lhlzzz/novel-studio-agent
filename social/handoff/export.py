"""Atomic XHS handoff export. This is not a publication."""

from __future__ import annotations

import json
import os
from dataclasses import replace
from pathlib import Path

from social.handoff.models import XHSHandoff
from social.providers.errors import ValidationError


def materialize_handoff_export(handoff: XHSHandoff) -> XHSHandoff:
    """Atomically export a persisted handoff. Path traversal and symlinks are rejected."""
    root = os.getenv("MEITI_XHS_HANDOFF_DIR", "").strip()
    if not root:
        return handoff
    directory = Path(root).resolve()
    if directory.exists() and directory.is_symlink():
        raise ValidationError("XHS handoff directory must not be a symlink")
    directory.mkdir(parents=True, exist_ok=True)
    os.chmod(directory, 0o700)
    if ".." in handoff.handoff_id or "/" in handoff.handoff_id or "\\" in handoff.handoff_id:
        raise ValidationError("invalid handoff_id")
    path = (directory / f"{handoff.handoff_id}.json").resolve()
    if not str(path).startswith(str(directory) + os.sep):
        raise ValidationError("XHS handoff export path traversal blocked")
    if path.exists() and path.is_symlink():
        raise ValidationError("XHS handoff export must not follow a symlink")
    tmp = path.with_name(path.name + ".tmp")
    if tmp.exists():
        tmp.unlink()
    payload = json.dumps(handoff.as_export(), ensure_ascii=False, indent=2)
    with tmp.open("w", encoding="utf-8") as fh:
        fh.write(payload)
        fh.flush()
        os.fsync(fh.fileno())
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)
    os.chmod(path, 0o600)
    return replace(handoff, export_path=str(path), export_status="READY")
