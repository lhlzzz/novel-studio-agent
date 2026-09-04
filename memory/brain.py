"""Obsidian is Meiti's knowledge brain. It never owns operational state."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from memory.models import KnowledgeDocument

from content.models import utcnow

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_VAULT = ROOT / "obsidian"

SCOPE_DIRS = {
    "GLOBAL": "learnings",
    "PLATFORM": "platforms",
    "ACCOUNT": "accounts",
    "CHARACTER": "characters",
    "WORLD": "worlds",
    "SERIES": "series",
    "EPISODE": "episodes",
    "CAMPAIGN": "strategy",
    "PUBLICATION": "learnings",
    "ANALYTICS": "analytics",
}

FRONTMATTER_KEYS = (
    "id",
    "scope_type",
    "scope_id",
    "account_id",
    "platform",
    "source_type",
    "title",
    "version",
    "status",
    "hash",
    "character_id",
    "world_id",
    "series_id",
    "episode_id",
    "publication_id",
)


def content_hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def slug(value: str) -> str:
    text = re.sub(r"[^\w\u4e00-\u9fff-]+", "-", (value or "").strip(), flags=re.UNICODE)
    return text.strip("-") or "untitled"


class KnowledgeBrain:
    """Read/write human Markdown. Operational numbers stay in PostgreSQL."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root or DEFAULT_VAULT)
        self.root.mkdir(parents=True, exist_ok=True)
        for name in ("accounts", "characters", "worlds", "series", "episodes", "strategy", "platforms", "research", "learnings", "decisions", "analytics"):
            (self.root / name).mkdir(parents=True, exist_ok=True)

    def path_for(self, document: KnowledgeDocument) -> Path:
        folder = SCOPE_DIRS.get(document.scope_type, "learnings")
        identity = slug(document.scope_id or document.account_id or document.id)
        filename = f"{slug(document.title) or identity}.md"
        if document.account_id and document.scope_type not in {"GLOBAL", "PLATFORM"}:
            return self.root / folder / slug(document.account_id) / filename
        if document.platform and document.scope_type == "PLATFORM":
            return self.root / folder / f"{slug(document.platform)}.md"
        return self.root / folder / filename

    def read(self, path: str | Path) -> KnowledgeDocument | None:
        target = Path(path)
        if not target.is_file():
            return None
        raw = target.read_text(encoding="utf-8")
        meta, body = _split_frontmatter(raw)
        return KnowledgeDocument(
            id=str(meta.get("id") or target.stem),
            scope_type=str(meta.get("scope_type") or "GLOBAL"),
            title=str(meta.get("title") or target.stem),
            path=str(target),
            content=body,
            hash=str(meta.get("hash") or content_hash(body)),
            scope_id=meta.get("scope_id"),
            account_id=meta.get("account_id"),
            platform=str(meta.get("platform") or ""),
            source_type=str(meta.get("source_type") or "obsidian"),
            tags=tuple(meta.get("tags") or ()),
            created_at=meta.get("created_at"),
            updated_at=meta.get("updated_at"),
            version=int(meta.get("version") or 1),
            status=str(meta.get("status") or "ACTIVE"),
            character_id=meta.get("character_id"),
            world_id=meta.get("world_id"),
            series_id=meta.get("series_id"),
            episode_id=meta.get("episode_id"),
            publication_id=meta.get("publication_id"),
        )

    def write(self, document: KnowledgeDocument) -> KnowledgeDocument:
        path = Path(document.path) if document.path else self.path_for(document)
        path.parent.mkdir(parents=True, exist_ok=True)
        digest = content_hash(document.content)
        if path.is_file():
            existing = self.read(path)
            if existing is not None and existing.hash == digest:
                return existing
        version = document.version
        if path.is_file():
            existing = self.read(path)
            version = (existing.version + 1) if existing else document.version
        saved = KnowledgeDocument(
            id=document.id,
            scope_type=document.scope_type,
            title=document.title,
            path=str(path),
            content=document.content,
            hash=digest,
            scope_id=document.scope_id,
            account_id=document.account_id,
            platform=document.platform,
            source_type=document.source_type,
            tags=document.tags,
            created_at=document.created_at,
            updated_at=utcnow(),
            version=version,
            status=document.status,
            character_id=document.character_id,
            world_id=document.world_id,
            series_id=document.series_id,
            episode_id=document.episode_id,
            publication_id=document.publication_id,
            metadata=dict(document.metadata),
        )
        path.write_text(_render(saved), encoding="utf-8")
        return saved

    def upsert(self, document: KnowledgeDocument) -> KnowledgeDocument:
        return self.write(document)

    def append_learning(self, document: KnowledgeDocument, learning: str) -> KnowledgeDocument:
        body = document.content.rstrip()
        addition = learning.strip()
        if addition and addition in body:
            return document
        merged = f"{body}\n\n- {addition}\n" if body else f"- {addition}\n"
        return self.write(KnowledgeDocument(**{**document.__dict__, "content": merged, "updated_at": utcnow()}))

    def list_scoped(
        self,
        *,
        account_id: str | None = None,
        scope_type: str | None = None,
        platform: str | None = None,
    ) -> list[KnowledgeDocument]:
        items: list[KnowledgeDocument] = []
        folders = [SCOPE_DIRS[scope_type]] if scope_type else list(dict.fromkeys(SCOPE_DIRS.values()))
        for folder in folders:
            root = self.root / folder
            if not root.exists():
                continue
            for path in root.rglob("*.md"):
                document = self.read(path)
                if document is None:
                    continue
                if account_id and document.account_id not in {account_id, None} and document.scope_type not in {"GLOBAL", "PLATFORM"}:
                    continue
                if platform and document.platform and document.platform != platform and document.scope_type != "GLOBAL":
                    continue
                if scope_type and document.scope_type != scope_type:
                    continue
                items.append(document)
        return items


def _split_frontmatter(raw: str) -> tuple[dict[str, Any], str]:
    if not raw.startswith("---\n"):
        return {}, raw
    end = raw.find("\n---\n", 4)
    if end < 0:
        return {}, raw
    block = raw[4:end]
    body = raw[end + 5 :]
    meta: dict[str, Any] = {}
    for line in block.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        text = value.strip().strip('"')
        if text in {"", "null", "None"}:
            meta[key.strip()] = None
        elif text.startswith("[") and text.endswith("]"):
            inner = text[1:-1].strip()
            meta[key.strip()] = tuple(item.strip().strip('"') for item in inner.split(",") if item.strip()) if inner else ()
        else:
            meta[key.strip()] = text
    return meta, body


def _render(document: KnowledgeDocument) -> str:
    lines = ["---"]
    for key in FRONTMATTER_KEYS:
        value = getattr(document, key)
        if value is None:
            continue
        if isinstance(value, tuple):
            lines.append(f"{key}: [{', '.join(value)}]")
        else:
            lines.append(f"{key}: {value}")
    if document.tags:
        lines.append(f"tags: [{', '.join(document.tags)}]")
    lines.append(f"created_at: {document.created_at}")
    lines.append(f"updated_at: {document.updated_at}")
    lines.append("---")
    lines.append("")
    lines.append(f"# {document.title}")
    lines.append("")
    lines.append(document.content.rstrip())
    lines.append("")
    return "\n".join(lines)
