# Meiti V3 State

- **2026-08-26:** destructive migration to capability-oriented architecture.
- Legacy workspace and platform-specific backend/topology were removed.
- Shared PostgreSQL + pgvector, embeddings, Content KG, evidence, Obsidian,
  and fail-closed publish gate remain.
- Agent layer: orchestrator, research, strategy, content, media, analytics,
  memory, commerce, distribution.
- Integration registry is dynamic. Providers are disabled until a connector is
  implemented and runtime-verified.
- Postiz is isolated distribution infrastructure; no Postiz source or schema
  is copied into Meiti.
- V3.1 provider code is under `integrations/providers/postiz/`; the legacy
  adapter path is a compatibility import only. Postiz and all account mappings
  remain disabled until runtime/API/OAuth verification succeeds.
- Postiz MCP contract is recorded at `config/postiz/mcp.yaml` and targets the
  self-hosted `/mcp` endpoint with Bearer authentication.
- ScrapeCreators research skills are represented as read-only capabilities.

## V3 Distribution External Acceptance — 2026-08-26

- Official Postiz Compose source is present and validates with independent
  Compose v2.27.0.
- Postiz host configuration uses port 4007 and an ignored local `.env`.
- Postiz Adapter maps the official `/public/v1` API contract, including
  integrations, settings, uploads, posts, status, and analytics.
- DistributionService enforces dry-run validation and Meiti Gate before any
  external call; publication responses require an external Postiz ID.
- Analytics normalization preserves unsupported provider metrics as null.
- Local validation: 18 tests passed; PostgreSQL + pgvector, embeddings, KG,
  and gate smoke checks passed.
- External readiness is `NOT_READY`: Docker Hub dependencies timed out during
  image pull, Postiz is not running, and OAuth device authorization was not
  completed. No integration was enabled and no real post was attempted.

Run `python -m pytest` and database/runtime smoke checks after changes.
