# Meiti V3 Agent Operating Contract

Meiti is an AI Creator / Media Operating System. Meiti owns Intelligence,
Strategy, Content, Media, Memory, Analytics, Commerce, Distribution,
Governance, and Integrations.

`Platform is an integration. Platform is not an agent. Platform is not a workspace.`

Logical agents are `meiti-orchestrator`, `research-agent`, `strategy-agent`,
`content-agent`, `media-agent`, `analytics-agent`, `memory-agent`,
`commerce-agent`, and `distribution-agent`. Resolve them with
`agents.registry.resolve_agent`. YAML is inventory; an importable
implementation is required before status can be `active`.

All production data is owned by Meiti. PostgreSQL + pgvector, Content KG, and
Obsidian are shared memory infrastructure. There is one Meiti business
database and one distribution database owned by Postiz.

All external actions go through `distribution-agent` and publish gate. Postiz
is the first distribution provider, not the Meiti business brain.

Postiz integration rules: `PostizClient` is the sole HTTP owner; provider
account IDs must come from a verified Postiz runtime; MCP is an execution
surface behind the same Meiti distribution boundary, never a replacement for
the ContentPackage, DistributionJob, or Publish Gate flow.

## Distribution Contract

ProviderResolver is the only provider routing mechanism.

DistributionAgent must never import a concrete provider adapter directly.

All provider capabilities require runtime verification.

Media must be uploaded before publish if provider requires uploaded media.

Every successful external action must create/update Publication.

Every publish must be idempotent.

Every scheduled/published job is reconciled.

Analytics must flow back into Meiti.

YAML and registry files may register a provider. They must not set
`enabled: true`. Enabled means runtime-verified. Job IDs, provider post IDs,
and platform object IDs stay separate.

## Change Rules

- Read source and tests before editing.
- Modify existing owners before creating new ones.
- Keep one implementation per responsibility.
- Fail closed when evidence, capability, account, media, or approval is missing.
- Never claim a connector is enabled without runtime verification.
- Research output is not publication.
- Never hard-code credentials or external tokens.

## Verification

```bash
python -m pytest
python scripts/db/migrate.py verify
python scripts/meiti_doctor.py
python scripts/runtime_check.py
```

The authoritative topology is the code under `agents/`, domain directories,
and `integrations/`. The legacy workspace tree must not exist.
