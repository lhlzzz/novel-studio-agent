"""MemoryService is the unique production memory owner."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from content.models import IsolationError, utcnow
from memory.brain import KnowledgeBrain, content_hash
from memory.embeddings import search_scoped, upsert_document_embeddings
from memory.models import LEARNING_KINDS, KnowledgeDocument, MemoryFact, SCOPE_TYPES
from memory.store import KnowledgeStore


class AmbiguousAccount(IsolationError):
    """Raised when production memory cannot uniquely resolve an account."""


class MemoryService:
    def __init__(self, *, store: KnowledgeStore | None = None, brain: KnowledgeBrain | None = None) -> None:
        self.store = store or KnowledgeStore()
        self.brain = brain or KnowledgeBrain()

    @classmethod
    def testing(cls) -> "MemoryService":
        import tempfile
        from pathlib import Path

        root = Path(tempfile.mkdtemp(prefix="meiti-memory-"))
        return cls(store=KnowledgeStore.testing(), brain=KnowledgeBrain(root=root))

    def remember(
        self,
        *,
        title: str,
        content: str,
        scope_type: str,
        account_id: str | None = None,
        platform: str = "",
        scope_id: str | None = None,
        source_type: str = "system",
        tags: tuple[str, ...] = (),
        character_id: str | None = None,
        world_id: str | None = None,
        series_id: str | None = None,
        episode_id: str | None = None,
        publication_id: str | None = None,
        document_id: str | None = None,
    ) -> KnowledgeDocument:
        if scope_type not in SCOPE_TYPES:
            raise ValueError(f"invalid knowledge scope: {scope_type}")
        if scope_type not in {"GLOBAL", "PLATFORM"} and not account_id:
            raise IsolationError("production memory requires account_id")
        digest = content_hash(content)
        existing = self.store.get_by_hash(digest, account_id=account_id)
        if existing is not None:
            return existing
        document = KnowledgeDocument(
            id=document_id or uuid4().hex,
            scope_type=scope_type,
            title=title,
            path="",
            content=content,
            hash=digest,
            scope_id=scope_id or account_id,
            account_id=account_id,
            platform=platform,
            source_type=source_type,
            tags=tags,
            character_id=character_id,
            world_id=world_id,
            series_id=series_id,
            episode_id=episode_id,
            publication_id=publication_id,
        )
        written = self.brain.upsert(document)
        saved = self.store.save_document(written)
        self._index(saved)
        return saved

    def writeback(self, insight: dict[str, Any], *, account_id: str | None = None, platform: str = "") -> dict[str, Any]:
        account = str(insight.get("account_id") or account_id or "")
        if not account:
            if str(insight.get("source") or "") == "research" or str(insight.get("kind") or "") == "validated_research":
                return self._write_global(insight, platform=platform)
            return {"written": 0, "facts": [], "documents": [], "skipped": "missing_account_id"}
        platform = str(insight.get("platform") or platform or "")
        documents = []
        mapping = {
            "successful_pattern": ("WHAT_WORKED", "Successful Patterns"),
            "failed_pattern": ("WHAT_FAILED", "Failed Patterns"),
            "platform_preference": ("PLATFORM_LEARNING", "Platform Insights"),
            "audience_preference": ("AUDIENCE_LEARNING", "Audience Insights"),
            "content_pattern": ("CREATIVE_LEARNING", "Creative Decisions"),
        }
        for key, (kind, title) in mapping.items():
            if key not in insight:
                continue
            documents.append(self.remember(
                title=title,
                content=_learning_body(kind, insight[key], insight),
                scope_type="ANALYTICS" if kind.endswith("LEARNING") else "ACCOUNT",
                account_id=account,
                platform=platform,
                source_type="analytics",
                tags=(kind, key),
                series_id=insight.get("series_id"),
                episode_id=insight.get("episode_id"),
                publication_id=insight.get("publication_id"),
            ))
        kind = str(insight.get("kind") or "")
        if kind:
            documents.append(self.remember(
                title=kind.replace("_", " ").title(),
                content=_learning_body(kind, insight, insight),
                scope_type="ACCOUNT",
                account_id=account,
                platform=platform,
                source_type=str(insight.get("source") or "production"),
                tags=(kind,),
                series_id=insight.get("series_id"),
                episode_id=insight.get("episode_id"),
                publication_id=insight.get("publication_id"),
            ))
        return {"written": len(documents), "facts": documents, "documents": documents}

    def _write_global(self, insight: dict[str, Any], *, platform: str = "") -> dict[str, Any]:
        document = self.remember(
            title=str(insight.get("kind") or "Research"),
            content=_learning_body(str(insight.get("kind") or "research"), insight.get("successful_pattern") or insight, insight),
            scope_type="GLOBAL",
            platform=str(insight.get("platform") or platform or ""),
            source_type="research",
            tags=("research", str(insight.get("kind") or "")),
        )
        return {"written": 1, "facts": [document], "documents": [document]}

    def retrieve(self, task: dict[str, Any] | None = None) -> dict[str, Any]:
        task = dict(task or {})
        account_id = self.resolve_account_id(task)
        query = str(task.get("query") or task.get("title") or task.get("body") or "")
        hits = self.search(query, account_id=account_id, platform=str(task.get("platform") or ""), extra=task)
        related = hits
        historical = [item for item in related if "success" in item.title.lower() or "fail" in item.title.lower() or item.scope_type in {"ACCOUNT", "ANALYTICS"}]
        return {
            "account_id": account_id,
            "query": query,
            "documents": related,
            "historical_content": related,
            "historical_successful_patterns": [item for item in related if "success" in item.title.lower() or "WHAT_WORKED" in item.tags],
            "historical_failed_patterns": [item for item in related if "fail" in item.title.lower() or "WHAT_FAILED" in item.tags],
            "previous_experiments": [item for item in related if "experiment" in item.title.lower()],
            "experiments": [item for item in related if "experiment" in item.title.lower()],
            "audience_insights": [item for item in related if item.scope_type in {"ANALYTICS"} or "audience" in item.title.lower()],
            "platform_insights": [item for item in related if item.scope_type == "PLATFORM" or "platform" in item.title.lower()],
            "feedback": [item for item in related if "audience" in item.title.lower()],
            "platform_performance": [item for item in related if item.scope_type in {"PLATFORM", "ANALYTICS"}],
            "brand_knowledge": [item for item in related if item.scope_type in {"ACCOUNT", "WORLD"}],
            "creative": [item for item in related if "creative" in item.title.lower() or "CREATIVE" in item.tags],
            "publication": [item for item in related if item.scope_type == "PUBLICATION"],
            "analytics": [item for item in related if item.scope_type == "ANALYTICS"],
            "research": [item for item in related if item.source_type == "research"],
            "continuity": [item for item in related if item.scope_type in {"EPISODE", "SERIES", "CHARACTER", "WORLD"}],
        }

    def search(
        self,
        query: str,
        *,
        account_id: str | None,
        platform: str = "",
        extra: dict[str, Any] | None = None,
    ) -> list[KnowledgeDocument]:
        extra = dict(extra or {})
        extra.setdefault("platform", platform)
        if not account_id:
            raise IsolationError("production retrieval requires account_id")
        ordered: list[KnowledgeDocument] = []
        seen: set[str] = set()
        layers = [
            {"account_id": account_id, "scope_type": "ACCOUNT"},
            {"account_id": account_id, "scope_type": "CHARACTER", "character_id": extra.get("character_id")},
            {"account_id": account_id, "scope_type": "WORLD", "world_id": extra.get("world_id")},
            {"account_id": account_id, "scope_type": "SERIES", "series_id": extra.get("series_id")},
            {"account_id": account_id, "scope_type": "EPISODE", "episode_id": extra.get("episode_id")},
            {"account_id": account_id, "scope_type": "PUBLICATION"},
            {"account_id": account_id, "scope_type": "ANALYTICS"},
            {"scope_type": "PLATFORM", "platform": platform or extra.get("platform")},
            {"scope_type": "GLOBAL"},
        ]
        for layer in layers:
            if layer.get("scope_type") == "PLATFORM" and not layer.get("platform"):
                continue
            for document in self.store.list_documents(**{k: v for k, v in layer.items() if v not in {None, ""}}):
                if document.id in seen:
                    continue
                if not _visible_to(document, account_id, platform=platform or str(extra.get("platform") or "")):
                    continue
                if query and query.lower() not in (document.title + " " + document.content).lower():
                    continue
                seen.add(document.id)
                ordered.append(document)
        semantic = self._semantic(query, account_id=account_id, extra=extra)
        for document in semantic:
            if document.id not in seen:
                seen.add(document.id)
                ordered.append(document)
        return self.rank(ordered, query=query)

    def rank(self, documents: list[KnowledgeDocument], *, query: str = "") -> list[KnowledgeDocument]:
        needle = (query or "").lower()
        def score(document: KnowledgeDocument) -> tuple[int, str]:
            text = f"{document.title} {document.content}".lower()
            hit = 1 if needle and needle in text else 0
            order = {
                "ACCOUNT": 8,
                "CHARACTER": 7,
                "WORLD": 6,
                "SERIES": 5,
                "EPISODE": 4,
                "PUBLICATION": 3,
                "ANALYTICS": 3,
                "PLATFORM": 2,
                "GLOBAL": 1,
            }.get(document.scope_type, 0)
            return (hit, order, document.updated_at or "")
        return sorted(documents, key=score, reverse=True)

    def scope(self, *, account_id: str, **filters: Any) -> list[KnowledgeDocument]:
        platform = str(filters.get("platform") or "")
        return [item for item in self.store.list_documents(account_id=account_id, **filters) if _visible_to(item, account_id, platform=platform)]

    def sync(self, document: KnowledgeDocument) -> KnowledgeDocument:
        written = self.brain.upsert(document)
        saved = self.store.save_document(written)
        self._index(saved)
        return saved

    def resolve_account_id(self, task: dict[str, Any]) -> str | None:
        explicit = str(task.get("account_id") or "")
        if explicit:
            return explicit
        context = task.get("account_context") or {}
        if isinstance(context, dict) and context.get("account_id"):
            return str(context["account_id"])
        if hasattr(context, "account_id") and context.account_id:
            return str(context.account_id)
        if task.get("allow_unscoped"):
            return None
        raise AmbiguousAccount("production memory request is missing account_id")

    def _semantic(self, query: str, *, account_id: str, extra: dict[str, Any]) -> list[KnowledgeDocument]:
        if not query:
            return []
        with self.store.session() as session:
            rows = search_scoped(
                session,
                query,
                filters={
                    "account_id": account_id,
                    "platform": extra.get("platform"),
                    "character_id": extra.get("character_id"),
                    "world_id": extra.get("world_id"),
                    "series_id": extra.get("series_id"),
                    "episode_id": extra.get("episode_id"),
                    "publication_id": extra.get("publication_id"),
                },
            )
        documents = []
        for row in rows:
            document_id = row.get("source_document_id")
            if not document_id:
                continue
            document = self.store.get_document(str(document_id))
            if document is not None and _visible_to(document, account_id, platform=str(extra.get("platform") or "")):
                documents.append(document)
        return documents

    def _index(self, document: KnowledgeDocument) -> None:
        with self.store.session() as session:
            upsert_document_embeddings(
                session,
                document_id=document.id,
                body=document.content,
                title=document.title,
                path=document.path,
                filters={
                    "account_id": document.account_id,
                    "platform": document.platform,
                    "scope_type": document.scope_type,
                    "scope_id": document.scope_id,
                    "character_id": document.character_id,
                    "world_id": document.world_id,
                    "series_id": document.series_id,
                    "episode_id": document.episode_id,
                    "publication_id": document.publication_id,
                    "source_line": "memory",
                },
            )
            session.commit()


def _visible_to(document: KnowledgeDocument, account_id: str, *, platform: str = "") -> bool:
    if document.scope_type == "GLOBAL":
        return True
    if document.platform and platform and document.platform not in {platform, "GLOBAL"}:
        return False
    if document.scope_type == "PLATFORM":
        if not document.platform:
            return False
        if platform and document.platform != platform:
            return False
        return True
    if not document.account_id:
        return False
    return document.account_id == account_id


def _learning_body(kind: str, value: Any, insight: dict[str, Any]) -> str:
    lines = [
        f"Kind: {kind}",
        f"Account: {insight.get('account_id') or ''}",
        f"Platform: {insight.get('platform') or ''}",
        f"Series: {insight.get('series_id') or ''}",
        f"Episode: {insight.get('episode_id') or ''}",
        f"Publication: {insight.get('publication_id') or ''}",
        f"Source: {insight.get('source') or 'production'}",
        f"Timestamp: {insight.get('timestamp') or utcnow()}",
        "",
        str(value),
    ]
    return "\n".join(lines)


_SERVICE: MemoryService | None = None


def get_memory_service(*, reset: bool = False) -> MemoryService:
    global _SERVICE
    if reset or _SERVICE is None:
        import os
        if os.environ.get("PYTEST_CURRENT_TEST") or os.environ.get("MEITI_MEMORY_STORE") == "memory":
            _SERVICE = MemoryService.testing()
        else:
            _SERVICE = MemoryService()
    return _SERVICE
