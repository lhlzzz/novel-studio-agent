#!/usr/bin/env python3
"""meiti content knowledge-graph helpers (entities + relations)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.db.engine import SessionLocal  # noqa: E402
from scripts.db.models import ContentEntity, ContentRelation  # noqa: E402


def upsert_entity(
    *,
    entity_key: str,
    entity_type: str,
    name: str,
    description: str | None = None,
    source_line: str = "shared",
    properties: dict[str, Any] | None = None,
) -> dict[str, Any]:
    with SessionLocal() as session:
        row = session.execute(
            select(ContentEntity).where(ContentEntity.entity_key == entity_key)
        ).scalar_one_or_none()
        fields = dict(
            entity_type=entity_type,
            name=name,
            description=description,
            source_line=source_line,
            properties=properties or {},
        )
        if row is None:
            row = ContentEntity(entity_key=entity_key, **fields)
            session.add(row)
        else:
            for k, v in fields.items():
                setattr(row, k, v)
        session.commit()
        session.refresh(row)
        return {
            "id": row.id,
            "entity_key": row.entity_key,
            "entity_type": row.entity_type,
            "name": row.name,
        }


def upsert_relation(
    *,
    relation_key: str,
    relation_type: str,
    from_entity_key: str,
    to_entity_key: str,
    weight: float = 1.0,
    properties: dict[str, Any] | None = None,
) -> dict[str, Any]:
    with SessionLocal() as session:
        src = session.execute(
            select(ContentEntity).where(ContentEntity.entity_key == from_entity_key)
        ).scalar_one_or_none()
        dst = session.execute(
            select(ContentEntity).where(ContentEntity.entity_key == to_entity_key)
        ).scalar_one_or_none()
        if src is None or dst is None:
            raise SystemExit(
                f"missing entity: from={from_entity_key!r} to={to_entity_key!r}"
            )
        row = session.execute(
            select(ContentRelation).where(ContentRelation.relation_key == relation_key)
        ).scalar_one_or_none()
        fields = dict(
            relation_type=relation_type,
            from_entity_id=src.id,
            to_entity_id=dst.id,
            weight=weight,
            properties=properties or {},
        )
        if row is None:
            row = ContentRelation(relation_key=relation_key, **fields)
            session.add(row)
        else:
            for k, v in fields.items():
                setattr(row, k, v)
        session.commit()
        return {
            "relation_key": relation_key,
            "relation_type": relation_type,
            "from": from_entity_key,
            "to": to_entity_key,
        }


def list_entities(entity_type: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    with SessionLocal() as session:
        q = select(ContentEntity).order_by(ContentEntity.id.desc()).limit(limit)
        if entity_type:
            q = q.where(ContentEntity.entity_type == entity_type)
        rows = session.execute(q).scalars().all()
        return [
            {
                "entity_key": r.entity_key,
                "entity_type": r.entity_type,
                "name": r.name,
                "source_line": r.source_line,
            }
            for r in rows
        ]


def neighbors(entity_key: str, limit: int = 50) -> list[dict[str, Any]]:
    with SessionLocal() as session:
        ent = session.execute(
            select(ContentEntity).where(ContentEntity.entity_key == entity_key)
        ).scalar_one_or_none()
        if ent is None:
            raise SystemExit(f"unknown entity_key={entity_key}")
        rels = session.execute(
            select(ContentRelation)
            .where(
                (ContentRelation.from_entity_id == ent.id)
                | (ContentRelation.to_entity_id == ent.id)
            )
            .limit(limit)
        ).scalars().all()
        out = []
        for rel in rels:
            other_id = rel.to_entity_id if rel.from_entity_id == ent.id else rel.from_entity_id
            other = session.get(ContentEntity, other_id)
            out.append(
                {
                    "relation_key": rel.relation_key,
                    "relation_type": rel.relation_type,
                    "direction": "out" if rel.from_entity_id == ent.id else "in",
                    "other_key": other.entity_key if other else None,
                    "other_name": other.name if other else None,
                    "weight": float(rel.weight) if rel.weight is not None else None,
                }
            )
        return out


def seed_package_graph(package_key: str) -> dict[str, Any]:
    """Seed a minimal graph for an internal content package."""
    topic = upsert_entity(
        entity_key=f"{package_key}:topic",
        entity_type="topic",
        name="AI efficiency templates for small business",
        description="高频回复草稿 + 信息整理表 + 7天内容日历",
        source_line="xiaoping",
        properties={"package_key": package_key},
    )
    offer = upsert_entity(
        entity_key=f"{package_key}:offer",
        entity_type="offer",
        name="小商家 AI 效率模板包 v0.1",
        source_line="xiaoping",
        properties={"sku": "XP-DIGI-AI-TPL-01", "package_key": package_key},
    )
    hook = upsert_entity(
        entity_key=f"{package_key}:hook",
        entity_type="hook",
        name="小商家别再一条条回客户了",
        source_line="xiaoping",
        properties={"package_key": package_key},
    )
    cta = upsert_entity(
        entity_key=f"{package_key}:cta",
        entity_type="cta",
        name="收藏结构 / 按行业改词（模拟）",
        source_line="xiaoping",
        properties={"package_key": package_key, "hard_sell": False},
    )
    platforms = []
    for p in ("xiaohongshu", "shipinhao", "douyin", "xianyu", "x", "tiktok"):
        platforms.append(
            upsert_entity(
                entity_key=f"{package_key}:platform:{p}",
                entity_type="platform",
                name=p,
                source_line="xiaoping",
                properties={"package_key": package_key},
            )
        )
    package = upsert_entity(
        entity_key=package_key,
        entity_type="package",
        name=package_key,
        description="INTERNAL_ONLY tweet package",
        source_line="xiaoping",
        properties={"status": "INTERNAL_ONLY"},
    )
    rels = [
        upsert_relation(
            relation_key=f"{package_key}:pkg-topic",
            relation_type="derived_from",
            from_entity_key=package_key,
            to_entity_key=f"{package_key}:topic",
        ),
        upsert_relation(
            relation_key=f"{package_key}:pkg-offer",
            relation_type="monetizes_via",
            from_entity_key=package_key,
            to_entity_key=f"{package_key}:offer",
        ),
        upsert_relation(
            relation_key=f"{package_key}:pkg-hook",
            relation_type="uses_hook",
            from_entity_key=package_key,
            to_entity_key=f"{package_key}:hook",
        ),
        upsert_relation(
            relation_key=f"{package_key}:pkg-cta",
            relation_type="has_cta",
            from_entity_key=package_key,
            to_entity_key=f"{package_key}:cta",
        ),
    ]
    for p in platforms:
        rels.append(
            upsert_relation(
                relation_key=f"{package_key}:adapts:{p['name']}",
                relation_type="adapts_to",
                from_entity_key=package_key,
                to_entity_key=p["entity_key"],
            )
        )
    return {"package": package, "topic": topic, "offer": offer, "hook": hook, "cta": cta, "relations": len(rels)}


def main() -> int:
    parser = argparse.ArgumentParser(description="meiti content KG CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_e = sub.add_parser("upsert-entity")
    p_e.add_argument("--key", required=True)
    p_e.add_argument("--type", required=True)
    p_e.add_argument("--name", required=True)
    p_e.add_argument("--description", default=None)
    p_e.add_argument("--source-line", default="shared")
    p_e.add_argument("--properties-json", default="{}")

    p_r = sub.add_parser("upsert-relation")
    p_r.add_argument("--key", required=True)
    p_r.add_argument("--type", required=True)
    p_r.add_argument("--from-key", required=True)
    p_r.add_argument("--to-key", required=True)
    p_r.add_argument("--weight", type=float, default=1.0)

    p_l = sub.add_parser("list-entities")
    p_l.add_argument("--type", default=None)
    p_l.add_argument("--limit", type=int, default=50)

    p_n = sub.add_parser("neighbors")
    p_n.add_argument("--key", required=True)

    p_s = sub.add_parser("seed-package")
    p_s.add_argument("--package-key", required=True)

    args = parser.parse_args()
    try:
        if args.command == "upsert-entity":
            print(
                json.dumps(
                    upsert_entity(
                        entity_key=args.key,
                        entity_type=args.type,
                        name=args.name,
                        description=args.description,
                        source_line=args.source_line,
                        properties=json.loads(args.properties_json),
                    ),
                    ensure_ascii=False,
                    indent=2,
                )
            )
        elif args.command == "upsert-relation":
            print(
                json.dumps(
                    upsert_relation(
                        relation_key=args.key,
                        relation_type=args.type,
                        from_entity_key=args.from_key,
                        to_entity_key=args.to_key,
                        weight=args.weight,
                    ),
                    ensure_ascii=False,
                    indent=2,
                )
            )
        elif args.command == "list-entities":
            print(json.dumps(list_entities(args.type, args.limit), ensure_ascii=False, indent=2))
        elif args.command == "neighbors":
            print(json.dumps(neighbors(args.key), ensure_ascii=False, indent=2))
        elif args.command == "seed-package":
            print(json.dumps(seed_package_graph(args.package_key), ensure_ascii=False, indent=2))
    except SQLAlchemyError as exc:
        print(f"content_kg failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
