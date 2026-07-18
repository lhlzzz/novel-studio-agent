#!/usr/bin/env python3
"""meiti content embedding pipeline: chunk → embed → upsert → search.

Default embedder is a local deterministic hash vector (no external API).
Set MEITI_EMBEDDING_PROVIDER=openai and OPENAI_API_KEY to use real embeddings.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.db.engine import DATABASE_URL, SessionLocal, engine  # noqa: E402
from scripts.db.models import DEFAULT_EMBEDDING_DIM, ContentEmbedding  # noqa: E402

DEFAULT_CHUNK_CHARS = 800
DEFAULT_OVERLAP = 100


def _masked_database_url() -> str:
    parts = urlsplit(DATABASE_URL)
    if not parts.netloc or "@" not in parts.netloc:
        return DATABASE_URL
    host = parts.netloc.rsplit("@", 1)[1]
    return urlunsplit((parts.scheme, f"***:***@{host}", parts.path, parts.query, parts.fragment))


def chunk_text(
    text_body: str,
    *,
    chunk_chars: int = DEFAULT_CHUNK_CHARS,
    overlap: int = DEFAULT_OVERLAP,
) -> list[str]:
    body = (text_body or "").strip()
    if not body:
        return []
    # Prefer paragraph splits, then hard windows.
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

    # Split oversized chunks with overlap.
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


def hash_embed(text_body: str, dim: int = DEFAULT_EMBEDDING_DIM) -> list[float]:
    """Deterministic local embedding for offline smoke / bootstrap."""
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
    # L2 normalize
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def openai_embed(texts: list[str], *, model: str, dim: int) -> list[list[float]]:
    api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("MEITI_OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("OPENAI_API_KEY / MEITI_OPENAI_API_KEY required for openai provider")
    try:
        import urllib.request
    except ImportError as exc:  # pragma: no cover
        raise SystemExit("urllib unavailable") from exc

    base = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    payload = json.dumps({"model": model, "input": texts}).encode("utf-8")
    req = urllib.request.Request(
        f"{base}/embeddings",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    out: list[list[float]] = []
    for item in sorted(data["data"], key=lambda x: x["index"]):
        vec = [float(x) for x in item["embedding"]]
        if len(vec) != dim:
            # pad/truncate to configured dim
            if len(vec) < dim:
                vec = vec + [0.0] * (dim - len(vec))
            else:
                vec = vec[:dim]
        out.append(vec)
    return out


def embed_texts(texts: list[str], *, model: str | None = None) -> tuple[list[list[float]], str]:
    provider = os.environ.get("MEITI_EMBEDDING_PROVIDER", "hash").lower()
    dim = DEFAULT_EMBEDDING_DIM
    if provider in {"hash", "local", "deterministic"}:
        model_name = model or "hash-embed-v1"
        return [hash_embed(t, dim) for t in texts], model_name
    if provider in {"openai", "oai"}:
        model_name = model or os.environ.get("MEITI_EMBEDDING_MODEL", "text-embedding-3-small")
        return openai_embed(texts, model=model_name, dim=dim), model_name
    raise SystemExit(f"Unknown MEITI_EMBEDDING_PROVIDER={provider}")


def _upsert_embedding(
    session,
    *,
    embedding_key: str,
    body: str,
    vector: list[float],
    model: str,
    content_type: str,
    source_line: str,
    title: str | None,
    path: str | None,
    platform: str | None,
    language: str,
    metadata: dict[str, Any],
) -> ContentEmbedding:
    row = session.execute(
        select(ContentEmbedding).where(ContentEmbedding.embedding_key == embedding_key)
    ).scalar_one_or_none()
    fields = dict(
        content_type=content_type,
        source_line=source_line,
        title=title,
        body=body,
        path=path,
        platform=platform,
        language=language,
        model=model,
        dim=len(vector),
        embedding=vector,
        metadata_json=metadata,
    )
    if row is None:
        row = ContentEmbedding(embedding_key=embedding_key, **fields)
        session.add(row)
    else:
        for k, v in fields.items():
            setattr(row, k, v)
    session.flush()
    return row


def ingest_text(
    text_body: str,
    *,
    key_prefix: str,
    content_type: str = "chunk",
    source_line: str = "shared",
    title: str | None = None,
    path: str | None = None,
    platform: str | None = None,
    language: str = "zh",
    chunk_chars: int = DEFAULT_CHUNK_CHARS,
    metadata: dict[str, Any] | None = None,
) -> list[str]:
    chunks = chunk_text(text_body, chunk_chars=chunk_chars)
    if not chunks:
        return []
    vectors, model = embed_texts(chunks)
    keys: list[str] = []
    meta = metadata or {}
    with SessionLocal() as session:
        for i, (chunk, vec) in enumerate(zip(chunks, vectors)):
            key = f"{key_prefix}#c{i:04d}"
            _upsert_embedding(
                session,
                embedding_key=key,
                body=chunk,
                vector=vec,
                model=model,
                content_type=content_type,
                source_line=source_line,
                title=title if i == 0 else f"{title or key_prefix} [{i}]",
                path=path,
                platform=platform,
                language=language,
                metadata={**meta, "chunk_index": i, "chunk_total": len(chunks)},
            )
            keys.append(key)
        session.commit()
    return keys


def ingest_file(
    file_path: Path,
    *,
    key_prefix: str | None = None,
    content_type: str = "note",
    source_line: str = "shared",
    platform: str | None = None,
    language: str = "zh",
) -> list[str]:
    path = file_path.resolve()
    body = path.read_text(encoding="utf-8", errors="replace")
    prefix = key_prefix or f"file:{path.name}"
    return ingest_text(
        body,
        key_prefix=prefix,
        content_type=content_type,
        source_line=source_line,
        title=path.name,
        path=str(path),
        platform=platform,
        language=language,
        metadata={"source_path": str(path)},
    )


def search(
    query: str,
    *,
    limit: int = 5,
    source_line: str | None = None,
    platform: str | None = None,
) -> list[dict[str, Any]]:
    vectors, model = embed_texts([query])
    qvec = vectors[0]
    q_literal = "[" + ",".join(str(float(x)) for x in qvec) + "]"
    sql = """
        SELECT embedding_key, title, content_type, source_line, platform, path,
               left(body, 240) AS body_preview,
               embedding <=> CAST(:q AS vector) AS distance
        FROM content_embeddings
        WHERE embedding IS NOT NULL
    """
    params: dict[str, Any] = {"q": q_literal, "lim": limit}
    if source_line:
        sql += " AND source_line = :source_line"
        params["source_line"] = source_line
    if platform:
        sql += " AND platform = :platform"
        params["platform"] = platform
    sql += " ORDER BY embedding <=> CAST(:q AS vector) ASC LIMIT :lim"
    with engine.connect() as conn:
        rows = conn.execute(text(sql), params).mappings().all()
    return [
        {
            **dict(row),
            "query_model": model,
            "distance": float(row["distance"]) if row["distance"] is not None else None,
        }
        for row in rows
    ]


def cmd_ingest(args: argparse.Namespace) -> int:
    if args.file:
        keys = ingest_file(
            Path(args.file),
            key_prefix=args.key_prefix,
            content_type=args.content_type,
            source_line=args.source_line,
            platform=args.platform,
            language=args.language,
        )
    else:
        body = args.text or sys.stdin.read()
        keys = ingest_text(
            body,
            key_prefix=args.key_prefix or "adhoc",
            content_type=args.content_type,
            source_line=args.source_line,
            title=args.title,
            platform=args.platform,
            language=args.language,
        )
    print(f"ingested {len(keys)} chunk(s) into {_masked_database_url()}")
    for k in keys:
        print(f"  - {k}")
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    rows = search(
        args.query,
        limit=args.limit,
        source_line=args.source_line,
        platform=args.platform,
    )
    print(json.dumps(rows, ensure_ascii=False, indent=2))
    return 0


def cmd_selftest(args: argparse.Namespace) -> int:
    """Offline pipeline smoke: ingest two texts and search."""
    try:
        keys_a = ingest_text(
            "小商家用高频问题回复草稿表减少重复打字。AI 效率模板。",
            key_prefix="meiti-embed-selftest-a",
            content_type="selftest",
            source_line="xiaoping",
            title="selftest-a",
            platform="xiaohongshu",
        )
        keys_b = ingest_text(
            "网文章节大纲与人设节奏。长内容叙事结构。",
            key_prefix="meiti-embed-selftest-b",
            content_type="selftest",
            source_line="xiaoshuo",
            title="selftest-b",
        )
        hits = search("小商家 效率 回复模板", limit=3)
        print(
            json.dumps(
                {
                    "status": "ok",
                    "keys_a": keys_a,
                    "keys_b": keys_b,
                    "top_hit": hits[0]["embedding_key"] if hits else None,
                    "distance": hits[0]["distance"] if hits else None,
                    "provider": os.environ.get("MEITI_EMBEDDING_PROVIDER", "hash"),
                    "database": _masked_database_url(),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        if not hits:
            raise SystemExit("selftest search returned no rows")
        return 0
    except SQLAlchemyError as exc:
        print(f"selftest failed: {exc}", file=sys.stderr)
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="meiti embedding pipeline")
    sub = parser.add_subparsers(dest="command", required=True)

    p_ing = sub.add_parser("ingest", help="chunk + embed + upsert text/file")
    p_ing.add_argument("--file", help="path to text/markdown file")
    p_ing.add_argument("--text", help="raw text (or stdin)")
    p_ing.add_argument("--key-prefix", default=None)
    p_ing.add_argument("--title", default=None)
    p_ing.add_argument("--content-type", default="chunk")
    p_ing.add_argument("--source-line", default="shared", choices=["shared", "xiaoping", "xiaoshuo"])
    p_ing.add_argument("--platform", default=None)
    p_ing.add_argument("--language", default="zh")
    p_ing.set_defaults(func=cmd_ingest)

    p_s = sub.add_parser("search", help="semantic search over content_embeddings")
    p_s.add_argument("query")
    p_s.add_argument("--limit", type=int, default=5)
    p_s.add_argument("--source-line", default=None)
    p_s.add_argument("--platform", default=None)
    p_s.set_defaults(func=cmd_search)

    p_t = sub.add_parser("selftest", help="offline ingest+search smoke")
    p_t.set_defaults(func=cmd_selftest)

    args = parser.parse_args()
    return int(args.func(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
