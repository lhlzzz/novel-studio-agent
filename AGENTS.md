# Meiti V4.4 Agent Operating Contract

Meiti is an AI Creator Operating System. Meiti owns Intelligence, Strategy,
Content, Media, Creative Workflow, Memory, Analytics, Commerce, Distribution,
Governance, and native Social account management.

`Platform is an integration. Platform is not an agent. Platform is not a workspace.`

`CreativeWorkflow is the canonical media production abstraction.`

`Provider is an execution backend, never an Agent.`

`Agent selects and orchestrates workflows; workflows execute deterministic node graphs.`

`All asynchronous generation is durable and worker-driven.`

`All generated assets are immutable.`

`Assets are content-addressed by sha256.`

`Agent selects workflow; workflow executes nodes.`

`All generation inputs are reproducible.`

`Provider capabilities must be verified.`

`Generation must respect credit budgets.`

`Distribution is downstream of ContentPackage.`

`Judge never publishes.`

`Creative generation never directly publishes.`

`Creative never publishes.`

`Platform integration never becomes an Agent.`

`No workspace architecture.`

`Social platforms are native integrations.`

`No third-party social scheduler is required.`

`Meiti owns social account metadata.`

`Provider credentials never enter business tables.`

`Social providers only publish/manage accounts.`

`Creative providers only generate media.`

`Creative never publishes.`

`Social providers never generate media.`

Logical agents are `meiti-orchestrator`, `research-agent`, `strategy-agent`,
`content-agent`, `media-agent`, `analytics-agent`, `memory-agent`,
`commerce-agent`, and `distribution-agent`. Resolve them with
`agents.registry.resolve_agent`. YAML is inventory; an importable
implementation is required before status can be `active`.

```text
User -> MediaAgent -> CreativeWorkflowResolver -> CreativeRun -> DB
-> Worker Lease -> Workflow Engine -> Node -> Provider Resolver
-> Creative Provider -> Provider Task -> MediaAsset
-> Technical QA -> AI Judge -> Policy Gate -> ContentPackage
-> DistributionAgent -> DistributionJob -> SocialProviderResolver
-> Native Social Provider -> Social Account -> Social Platform
-> Publication -> Analytics -> Experiment -> Memory -> Strategy
```

Meiti = Creator Brain + Prompt Compiler + Asset/Continuity/Learning System
Lechuang = manual image / video execution tool unless a verified API adapter exists
Native social adapters = X / Instagram / YouTube / TikTok / LinkedIn
grok-4.6 = engineering agent for this repository, never a video generation model

The unique creative composition root is `creative.runtime.container.CreativeRuntime`.
MediaAgent, Creative API, Creative Worker, Doctor, and CLI obtain runtime
through that container. They do not construct engines, stores, or resolvers
ad hoc.

## Agent constraints

- Agent cannot bypass Workflow
- Agent cannot bypass Provider Resolver
- Agent cannot bypass Publish Gate
- Agent cannot fake PASS
- Agent cannot write credentials
- Agent cannot directly publish
- Agent cannot create duplicate runtime
- Agent cannot call a third-party provider
- Creative Provider cannot publish
- Social Provider cannot generate content

Media Agent selects a CreativeWorkflow, fills inputs, and submits a
CreativeRun. It does not call Lechuang or social platform APIs. Generation
providers live under `creative/providers/`. Social providers live under
`social/providers/` and are reached only through SocialProviderResolver.

PostgreSQL is the metadata source of truth. Filesystem / object storage is
the binary source of truth. Memory is cache only. Schema changes go through
migration. Runtime never creates tables.

BLOCKED is a structured runtime state (`blocked_reason`, `blocked_message`,
`blocked_at`, `retryable`). Missing credentials, unverified contracts, or
missing vision providers are BLOCKED, not PASS.

## Distribution Contract

SocialProviderResolver is the only social routing mechanism.
DistributionAgent must never import a concrete provider adapter directly.
CreativeWorkflow must never call a social provider.

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
python scripts/social_doctor.py
python scripts/creative_doctor.py
python scripts/runtime_check.py
```

The authoritative topology is the code under `agents/`, `creative/`, `social/`,
domain directories, and `integrations/`.
