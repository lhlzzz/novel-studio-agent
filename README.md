# Meiti V3.3

Meiti is an AI Creator Operating System.

```text
Research → Intelligence → Strategy → Content → Media → Memory
→ ContentPackage → Distribution → Publish Gate → Provider Resolver
→ Provider Adapter → External Platform → Publication
→ Reconciliation → Analytics → Insight → Memory → Strategy
```

Commerce is independent:

```text
Content → Audience → Commerce Attribution → Product / Offer → Conversion
```

Capability agents: orchestrator, research, strategy, content, media,
analytics, memory, commerce, and distribution.

## Distribution

Postiz is the first external distribution provider. Meiti owns content, jobs,
gates, publications, analytics, and memory. Routing goes through
ProviderResolver to a verified adapter. Publish Gate is fail-closed.
Domestic connectors remain registered and disabled until a real adapter exists.

```text
Campaign → ContentPackage → ContentVariant → DistributionJob
→ Publish Gate → ProviderResolver → Adapter → Publication
→ Reconciliation → Analytics → Memory → Strategy
```

## Shared infrastructure

- PostgreSQL + pgvector: Meiti production data
- Content KG: content entities and relations
- Control Plane: agents, integrations, jobs, workers, database
- Obsidian: operational knowledge
- `packages/`: content packages
- `evidence/`: evidence and media assets
- `.gates/`: approval records

```bash
python -m pytest
python scripts/db/migrate.py upgrade
python scripts/db/migrate.py verify
python scripts/meiti_doctor.py
python scripts/runtime_check.py
```

`Platform = Integration`; `Platform != Workspace`; `Platform != Agent`.
