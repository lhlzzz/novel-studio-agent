# Meiti V3.3 Task

**GOAL:** Operate Meiti as one AI Creator Operating System with
capability agents, registry-driven integrations, governed distribution, and
shared PostgreSQL + pgvector memory.

**VERIFY:** No legacy workspace topology or platform-specific launcher remains.
Registry, contracts, gate, analytics, memory, commerce, Postiz, and research
skill surfaces pass tests and available runtime checks.

## Current boundary

- Enabled distribution: only integrations with verified connectors.
- Postiz: first external distribution provider with an isolated database.
- ScrapeCreators: read-only research skill source until live credentials and
  workflow verification are available.
- Domestic providers: registered as disabled custom adapters until verified.
- Mock E2E is CI-safe. Real publication is opt-in after Postiz auth, account
  discovery, and capability verification.
- Demo rows live in `tests/fixtures/` and are never applied by `upgrade`.
