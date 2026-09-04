"""Embedding infrastructure owned by MemoryService. CLI is a caller, not a second memory system."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError

DEFAULT_CHUNK_CHARS = 800
DEFAULT_OVERLAP = 100
DEFAULT_DIM = int(os.environ.get("MEITI_EMBEDDING_DIM", "1536"))


def chunk_text(
    text_body: str,
    *,
    chunk_chars: int = DEFAULT_CHUNK_CHARS,
    overlap: int = DEFAULT_OVERLAP,
) -> list[str]:
    body = (text_body or "").strip()
    if not body:
        return []
    paras = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
    chunks: list[str] = []
    buf = ""
    for para in paras or [body]:
        if not buf:
            buf = para
        elif len(buf) + 2 + len(para) <= chunk_chars:
            buf = f"{buf}\n\n{para}"
        else:
            chunks.append(buf)
            buf = para
    if buf:
        chunks.append(buf)
    final: list[str] = []
    for ch in chunks:
        if len(ch) <= chunk_chars:
            final.append(ch)
            continue
        start = 0
        while start < len(ch):
            end = min(len(ch), start + chunk_chars)
            final.append(ch[start:end])
            if end >= len(ch):
                break
            start = max(0, end - overlap)
    return final


def hash_embed(text_body: str, dim: int = DEFAULT_DIM) -> list[float]:
    vec = [0.0] * dim
    tokens = re.findall(r"[\w\u4e00-\u9fff]+", (text_body or "").lower())
    if not tokens:
        tokens = ["empty"]
    for tok in tokens:
        digest = hashlib.sha256(tok.encode("utf-8")).digest()
        for i in range(0, min(len(digest), 32), 4):
            idx = int.from_bytes(digest[i : i + 4], "little") % dim
            sign = 1.0 if digest[i] % 2 == 0 else -1.0
            vec[idx] += sign
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    return sum(x * y for x, y in zip(a, b))


def embed_texts(texts: list[str], *, model: str | None = None) -> tuple[list[list[float]], str]:
    provider = os.environ.get("MEITI_EMBEDDING_PROVIDER", "hash").lower()
    dim = DEFAULT_DIM
    if provider in {"hash", "local", "deterministic"}:
        return [hash_embed(t, dim) for t in texts], model or "hash-embed-v1"
    if provider in {"openai", "oai"}:
        from scripts.embeddings import openai_embed
        model_name = model or os.environ.get("MEITI_EMBEDDING_MODEL", "text-embedding-3-small")
        return openai_embed(texts, model=model_name, dim=dim), model_name
    raise RuntimeError(f"Unknown MEITI_EMBEDDING_PROVIDER={provider}")


def scope_filter_sql(filters: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    clauses = ["embedding IS NOT NULL"]
    params: dict[str, Any] = {}
    mapping = {
        "account_id": "account_id",
        "platform": "platform",
        "scope_type": "scope_type",
        "scope_id": "scope_id",
        "character_id": "character_id",
        "world_id": "world_id",
        "series_id": "series_id",
        "episode_id": "episode_id",
        "publication_id": "publication_id",
        "source_document_id": "source_document_id",
        "source_line": "source_line",
    }
    for key, column in mapping.items():
        value = filters.get(key)
        if value not in {None, ""}:
            clauses.append(f"{column} = :{key}")
            params[key] = value
    return " AND ".join(clauses), params


def upsert_document_embeddings(
    session,
    *,
    document_id: str,
    body: str,
    filters: dict[str, Any],
    title: str | None = None,
    path: str | None = None,
) -> list[str]:
    from scripts.db.models import ContentEmbedding, DEFAULT_EMBEDDING_DIM

    chunks = chunk_text(body)
    if not chunks:
        return []
    vectors, model = embed_texts(chunks)
    keys: list[str] = []
    dialect = getattr(getattr(session.get_bind(), "dialect", None), "name", "")
    for index, (chunk, vector) in enumerate(zip(chunks, vectors)):
        key = f"knowledge:{document_id}#c{index:04d}"
        row = session.execute(select(ContentEmbedding).where(ContentEmbedding.embedding_key == key)).scalar_one_or_none()
        metadata = {
            **{k: v for k, v in filters.items() if v not in {None, ""}},
            "chunk_index": index,
            "chunk_total": len(chunks),
            "source_document_id": document_id,
        }
        fields = dict(
            content_type="knowledge",
            source_line=str(filters.get("source_line") or "memory"),
            title=title if index == 0 else f"{title or document_id} [{index}]",
            body=chunk,
            path=path,
            platform=filters.get("platform"),
            language=str(filters.get("language") or "zh"),
            model=model,
            dim=len(vector),
            metadata_json=metadata,
        )
        if dialect == "postgresql":
            fields["embedding"] = vector
        else:
            fields["embedding"] = None
            metadata["vector"] = vector
            fields["metadata_json"] = metadata
        extra = {
            "account_id": filters.get("account_id"),
            "scope_type": filters.get("scope_type"),
            "scope_id": filters.get("scope_id"),
            "character_id": filters.get("character_id"),
            "world_id": filters.get("world_id"),
            "series_id": filters.get("series_id"),
            "episode_id": filters.get("episode_id"),
            "publication_id": filters.get("publication_id"),
            "source_document_id": document_id,
        }
        if row is None:
            kwargs = dict(fields)
            for name, value in extra.items():
                if hasattr(ContentEmbedding, name):
                    kwargs[name] = value
            session.add(ContentEmbedding(embedding_key=key, **kwargs))
        else:
            for name, value in fields.items():
                setattr(row, name, value)
            for name, value in extra.items():
                if hasattr(row, name):
                    setattr(row, name, value)
        keys.append(key)
    session.flush()
    return keys


def search_scoped(
    session,
    query: str,
    *,
    filters: dict[str, Any],
    limit: int = 8,
) -> list[dict[str, Any]]:
    vectors, model = embed_texts([query])
    qvec = vectors[0]
    dialect = getattr(getattr(session.get_bind(), "dialect", None), "name", "")
    if dialect == "postgresql":
        where_sql, params = scope_filter_sql(filters)
        q_literal = "[" + ",".join(str(float(x)) for x in qvec) + "]"
        sql = f"""
            SELECT embedding_key, title, content_type, platform, path, left(body, 240) AS body_preview,
                   account_id, scope_type, scope_id, source_document_id,
                   embedding <=> CAST(:q AS vector) AS distance
            FROM content_embeddings
            WHERE {where_sql}
            ORDER BY embedding <=> CAST(:q AS vector) ASC
            LIMIT :lim
        """
        params.update({"q": q_literal, "lim": limit})
        try:
            rows = session.execute(text(sql), params).mappings().all()
        except SQLAlchemyError:
            return []
        return [{**dict(row), "query_model": model, "distance": float(row["distance"]) if row["distance"] is not None else None} for row in rows]
    from scripts.db.models import ContentEmbedding

    stmt = select(ContentEmbedding)
    rows = list(session.execute(stmt).scalars())
    scored = []
    for row in rows:
        meta = dict(row.metadata_json or {})
        row_account = getattr(row, "account_id", None) or meta.get("account_id")
        row_scope = getattr(row, "scope_type", None) or meta.get("scope_type")
        if filters.get("account_id"):
            if row_account and row_account != filters["account_id"] and row_scope not in {"GLOBAL", "PLATFORM"}:
                continue
        if filters.get("platform"):
            row_platform = getattr(row, "platform", None) or meta.get("platform")
            if row_platform and row_platform != filters["platform"] and row_scope != "GLOBAL":
                continue
        skipped = False
        for key in ("character_id", "world_id", "series_id", "episode_id", "publication_id", "source_document_id", "source_line", "scope_type"):
            wanted = filters.get(key)
            if not wanted:
                continue
            row_value = getattr(row, key, None) if hasattr(row, key) else None
            row_value = row_value or meta.get(key)
            if row_value and row_value != wanted:
                skipped = True
                break
        if skipped:
            continue
        vector = meta.get("vector")
        if not vector:
            continue
        scored.append((cosine(qvec, [float(x) for x in vector]), row, meta))
    scored.sort(key=lambda item: item[0], reverse=True)
    hits = []
    for score, row, meta in scored[:limit]:
        hits.append({
            "embedding_key": row.embedding_key,
            "title": row.title,
            "content_type": row.content_type,
            "platform": row.platform,
            "path": row.path,
            "body_preview": (row.body or "")[:240],
            "account_id": getattr(row, "account_id", None) or meta.get("account_id"),
            "scope_type": getattr(row, "scope_type", None) or meta.get("scope_type"),
            "scope_id": getattr(row, "scope_id", None) or meta.get("scope_id"),
            "source_document_id": getattr(row, "source_document_id", None) or meta.get("source_document_id"),
            "distance": 1.0 - score,
            "query_model": model,
        })
    return hits
