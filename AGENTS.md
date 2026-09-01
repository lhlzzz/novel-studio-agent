# Meiti V4 Agent Operating Contract

Meiti is an AI Creator Operating System. Meiti owns Intelligence, Strategy,
Content, Media, Creative Workflow, Memory, Analytics, Commerce, Distribution,
Governance, and Integrations.

`Platform is an integration. Platform is not an agent. Platform is not a workspace.`

`CreativeWorkflow is the canonical media production abstraction.`

`Provider is an execution backend, never an Agent.`

`Agent selects and orchestrates workflows; workflows execute deterministic node graphs.`

`All asynchronous generation is durable and worker-driven.`

`All generated assets are immutable.`

`All generation inputs are reproducible.`

`Provider capabilities must be verified.`

`Generation must respect credit budgets.`

`Distribution is downstream of ContentPackage.`

`Creative generation never directly publishes.`

`Platform integration never becomes an Agent.`

`No workspace architecture.`

Logical agents are `meiti-orchestrator`, `research-agent`, `strategy-agent`,
`content-agent`, `media-agent`, `analytics-agent`, `memory-agent`,
`commerce-agent`, and `distribution-agent`. Resolve them with
`agents.registry.resolve_agent`. YAML is inventory; an importable
implementation is required before status can be `active`.

```text
Research -> Strategy -> Creative Direction -> Creative Workflow
-> Asset Generation -> AI Quality Judgment -> MediaAsset
-> ContentPackage -> Distribution -> Analytics -> Memory -> Strategy
```

Meiti = Brain + Memory + Workflow + Judgment + Learning
Lechuang = Generation Provider
Postiz = Distribution Provider

Media Agent selects and executes workflows. It does not call Lechuang or Postiz
directly. Generation providers live under `creative/providers/`. Distribution
providers live under `integrations/providers/` and are reached only through
ProviderResolver.

All production data is owned by Meiti. PostgreSQL + pgvector, Content KG, and
Obsidian are shared memory infrastructure. There is one Meiti business
database and one distribution database owned by Postiz.

## Distribution Contract

ProviderResolver is the only distribution routing mechanism.
DistributionAgent must never import a concrete provider adapter directly.
CreativeWorkflow must never call Postiz.

All provider capabilities require runtime verification.
Media must be uploaded before publish if the provider requires uploaded media.
Every successful external action must create/update Publication.
Every publish must be idempotent.
Every scheduled/published job is reconciled.
Analytics must flow back into Meiti, including workflow/model/character dimensions.

YAML and registry files may register a provider. They must not set
`enabled: true`. Enabled means runtime-verified.

## Change Rules

- Read source and tests before editing.
- Modify existing owners before creating new ones.
- Keep one implementation per responsibility.
- Fail closed when evidence, capability, account, media, budget, or approval is missing.
- Never claim a connector is enabled without runtime verification.
- Never guess a generation API contract.
- Research output is not publication.
- Generation output is not publication.
- Never hard-code credentials or external tokens.

## Verification

```bash
python -m pytest
python scripts/db/migrate.py verify
python scripts/meiti_doctor.py
python scripts/creative_doctor.py
python scripts/runtime_check.py
```

The authoritative topology is the code under `agents/`, `creative/`, domain
directories, and `integrations/`. The legacy workspace tree must not exist.
