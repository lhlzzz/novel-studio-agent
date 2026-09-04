"""PostgreSQL index for knowledge documents. Obsidian remains the readable brain."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from memory.models import KnowledgeDocument


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def is_test_runtime() -> bool:
    return bool(os.environ.get("PYTEST_CURRENT_TEST")) or os.environ.get("MEITI_MEMORY_STORE") == "memory"


def sqlite_engine():
    return create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)


class KnowledgeStore:
    def __init__(self, *, engine=None) -> None:
        if engine is None:
            if is_test_runtime():
                engine = sqlite_engine()
            else:
                from scripts.db.engine import engine as production_engine
                engine = production_engine
        self.engine = engine
        self.Session = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        dialect = getattr(getattr(self.engine, "dialect", None), "name", "")
        if is_test_runtime() or dialect == "sqlite":
            from scripts.db.models import Base
            tables = [Base.metadata.tables[name] for name in ("knowledge_documents", "content_embeddings") if name in Base.metadata.tables]
            if tables:
                Base.metadata.create_all(self.engine, tables=tables)

    @classmethod
    def testing(cls) -> "KnowledgeStore":
        return cls(engine=sqlite_engine())

    def session(self):
        return self.Session()

    def save_document(self, document: KnowledgeDocument) -> KnowledgeDocument:
        from scripts.db.models import KnowledgeDocumentRecord

        with self.session() as session:
            row = session.get(KnowledgeDocumentRecord, document.id)
            fields = dict(
                scope_type=document.scope_type,
                scope_id=document.scope_id,
                account_id=document.account_id,
                platform=document.platform or "",
                source_type=document.source_type,
                title=document.title,
                path=document.path,
                content=document.content,
                tags=list(document.tags),
                version=document.version,
                status=document.status,
                content_hash=document.hash,
                character_id=document.character_id,
                world_id=document.world_id,
                series_id=document.series_id,
                episode_id=document.episode_id,
                publication_id=document.publication_id,
                updated_at=_now(),
            )
            if row is None:
                session.add(KnowledgeDocumentRecord(document_id=document.id, **fields))
            else:
                for name, value in fields.items():
                    setattr(row, name, value)
            session.commit()
        return document

    def get_document(self, document_id: str) -> KnowledgeDocument | None:
        from scripts.db.models import KnowledgeDocumentRecord

        with self.session() as session:
            row = session.get(KnowledgeDocumentRecord, document_id)
            return _from_row(row) if row else None

    def get_by_hash(self, digest: str, *, account_id: str | None) -> KnowledgeDocument | None:
        from scripts.db.models import KnowledgeDocumentRecord

        with self.session() as session:
            stmt = select(KnowledgeDocumentRecord).where(KnowledgeDocumentRecord.content_hash == digest)
            if account_id:
                stmt = stmt.where(
                    (KnowledgeDocumentRecord.account_id == account_id) | (KnowledgeDocumentRecord.scope_type.in_(("GLOBAL", "PLATFORM")))
                )
            row = session.execute(stmt).scalars().first()
            return _from_row(row) if row else None

    def list_documents(
        self,
        *,
        account_id: str | None = None,
        scope_type: str | None = None,
        platform: str | None = None,
        character_id: str | None = None,
        world_id: str | None = None,
        series_id: str | None = None,
        episode_id: str | None = None,
    ) -> list[KnowledgeDocument]:
        from scripts.db.models import KnowledgeDocumentRecord

        with self.session() as session:
            stmt = select(KnowledgeDocumentRecord)
            if account_id and scope_type not in {"GLOBAL", "PLATFORM"}:
                stmt = stmt.where(
                    (KnowledgeDocumentRecord.account_id == account_id) | (KnowledgeDocumentRecord.scope_type.in_(("GLOBAL", "PLATFORM")))
                )
            if scope_type:
                stmt = stmt.where(KnowledgeDocumentRecord.scope_type == scope_type)
            if platform:
                stmt = stmt.where((KnowledgeDocumentRecord.platform == platform) | (KnowledgeDocumentRecord.platform == "") | KnowledgeDocumentRecord.platform.is_(None))
            if character_id:
                stmt = stmt.where(KnowledgeDocumentRecord.character_id == character_id)
            if world_id:
                stmt = stmt.where(KnowledgeDocumentRecord.world_id == world_id)
            if series_id:
                stmt = stmt.where(KnowledgeDocumentRecord.series_id == series_id)
            if episode_id:
                stmt = stmt.where(KnowledgeDocumentRecord.episode_id == episode_id)
            return [_from_row(row) for row in session.execute(stmt).scalars()]


def _from_row(row) -> KnowledgeDocument:
    return KnowledgeDocument(
        id=row.document_id,
        scope_type=row.scope_type,
        title=row.title,
        path=row.path or "",
        content=row.content or "",
        hash=row.content_hash,
        scope_id=row.scope_id,
        account_id=row.account_id,
        platform=row.platform or "",
        source_type=row.source_type or "obsidian",
        tags=tuple(row.tags or ()),
        created_at=row.created_at.isoformat() if row.created_at else None,
        updated_at=row.updated_at.isoformat() if row.updated_at else None,
        version=int(row.version or 1),
        status=row.status or "ACTIVE",
        character_id=row.character_id,
        world_id=row.world_id,
        series_id=row.series_id,
        episode_id=row.episode_id,
        publication_id=row.publication_id,
    )
