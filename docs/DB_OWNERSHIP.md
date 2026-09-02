# Meiti Database Ownership

## Single owner

Meiti PostgreSQL + pgvector is the metadata source of truth for content,
creative runs, embeddings, Content KG, analytics, commerce, memory, social
accounts, publications, and publish gates. Filesystem / object storage is the
binary source of truth. Memory is cache only.

Native social credentials are stored in the runtime secret store. Business
tables may store `credential_ref` only.

Runtime never creates tables. Schema changes go through migration.

## Creative tables

- `creative_workflows`: immutable workflow versions
- `creative_runs`: durable run + lease + blocked reason
- `creative_tasks`: provider tasks
- `media_assets`: content-addressed asset metadata
- `generation_usage`: per-call cost
- `judge_results`: persisted judge decisions

## Social tables

- `social_accounts`: native platform account metadata
- `distribution_jobs`: gated publish/schedule jobs
- `publications`: provider/platform identifiers
- `derived_assets`: platform-specific transforms of immutable MediaAsset

The configured Meiti URL is `MEITI_DATABASE_URL` or `DATABASE_URL`.
