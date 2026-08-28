# Meiti V3

Meiti is an AI Creator / Media Operating System.

```text
Research → Strategy → Create → Distribute → Measure → Learn → Improve
```

Core domains: Intelligence, Strategy, Content, Media, Memory, Analytics,
Commerce, Governance, Distribution, and Integrations.

Capability agents are orchestrator, research, strategy, content, media,
analytics, memory, commerce, and distribution.

## Distribution

Postiz is global distribution infrastructure. It owns verified channel
connections, OAuth, uploads, scheduling, publishing, and distribution status.
Meiti owns the business and intelligence layer.

Custom adapters are used for integrations not verified by Postiz. A provider
may be registered without being enabled; `enabled: true` requires a real
connector and runtime verification.

The Postiz provider lives under `integrations/providers/postiz/`. Its public
API client, adapter contract, account mapping, and MCP contract are kept
separate from Meiti's business database. See its README for the operational
boundary and required environment variables.

## Shared infrastructure

- PostgreSQL + pgvector: Meiti production data
- Content KG: content entities and relations
- Obsidian: operational knowledge graph
- `packages/`: content packages
- `evidence/`: evidence and media assets
- `.gates/`: approval records

```bash
python -m pytest
python scripts/db/migrate.py bootstrap
python scripts/db/migrate.py verify
python scripts/embeddings.py selftest
python scripts/publish_gate.py selftest
```

`Platform = Integration`; `Platform != Workspace`; `Platform != Agent`.
