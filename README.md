# Meiti V4

Meiti is an AI Creator Operating System.

```text
Research -> Strategy -> Creative Direction -> Creative Workflow Engine
-> Character / Image / Video -> Judge -> MediaAsset -> ContentPackage
-> Distribution -> Publish Gate -> Provider Resolver -> Postiz
-> Publication -> Analytics -> Insight -> Memory -> Strategy
```

```text
Meiti = Brain + Memory + Workflow + Judgment + Learning
Lechuang = Generation Provider
Postiz = Distribution Provider
```

Capability agents: orchestrator, research, strategy, content, media,
analytics, memory, commerce, and distribution.

Media Agent does not pick models. It selects a CreativeWorkflow and the
engine executes a node graph. Providers are bound per node, never as a
single workflow-wide vendor lock.

## Creative

Templates live in `creative/workflow/templates/`. Runtime, judges, assets,
and generation providers live under `creative/`. Live Lechuang calls stay
BLOCKED until `LECHUANG_API_KEY`, `LECHUANG_API_URL`, and a verified API
contract exist. Mock creative is CI-safe.

## Distribution

Postiz is the first external distribution provider. Routing goes through
ProviderResolver. Publish Gate is fail-closed. Creative generation never
publishes.

## Shared infrastructure

- PostgreSQL + pgvector: Meiti production data
- Content KG: content entities and relations
- Control Plane: agents, integrations, jobs, workers, database
- `media/assets/`: immutable hashed artifacts
- Obsidian: operational knowledge

```bash
python -m pytest
python scripts/creative_doctor.py
python scripts/meiti_doctor.py
python scripts/runtime_check.py
python scripts/db/migrate.py verify
```

`Platform = Integration`; `Platform != Workspace`; `Platform != Agent`.
