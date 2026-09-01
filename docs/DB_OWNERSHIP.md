# Meiti Database Ownership

## Single owner

Meiti PostgreSQL + pgvector is the metadata source of truth for content,
creative runs, embeddings, Content KG, analytics, commerce, memory, and
publish gates. Filesystem / object storage is the binary source of truth.
Memory is cache only.

Postiz runs its own PostgreSQL database inside `infrastructure/postiz/`.
Postiz data is distribution infrastructure and is never mixed with Meiti
business tables.

Runtime never creates tables. Schema changes go through migration.

## Creative tables

- `creative_workflows`: immutable workflow versions
- `creative_runs`: durable run + lease + blocked reason
- `creative_tasks`: provider tasks
- `media_assets`: content-addressed asset metadata
- `generation_usage`: per-call cost
- `judge_results`: persisted judge decisions

The configured Meiti URL is `MEITI_DATABASE_URL` or `DATABASE_URL`.
