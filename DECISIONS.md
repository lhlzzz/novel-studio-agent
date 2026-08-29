# Meiti V3 Decisions

- **2026-08-26:** Platform is an integration, not an agent or workspace.
- **2026-08-26:** Meiti owns business and intelligence data; Postiz owns
  distribution infrastructure and its own database.
- **2026-08-26:** Registry entries may be disabled. Enabled means a connector
  passed runtime verification.
- **2026-08-26:** Existing PostgreSQL + pgvector, Content KG, evidence, gate,
  and Obsidian surfaces are reused; no second memory database is introduced.
- **2026-08-28:** ProviderResolver is the only provider routing mechanism.
- **2026-08-28:** YAML cannot set enabled=true. Capabilities need runtime
  verification. Media upload precedes create_post. Publish is idempotent.
- **2026-08-28:** Job id, provider post id, and platform object id are
  distinct. Analytics snapshots are append-only. Research stays read-only.
- **2026-08-29:** Keep `scripts/db/migrate.py` as the single migration owner
  with `schema_migrations` rather than adding a parallel Alembic tree.
- **2026-08-29:** ContentPackage, Campaign, Publication, MediaUploadResult,
  and DistributionAttempt are first-class. Postiz field names stay inside
  `integrations/providers/postiz/`.
