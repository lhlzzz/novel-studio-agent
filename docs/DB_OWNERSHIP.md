# Meiti Database Ownership

## Single owner

Meiti PostgreSQL + pgvector is the sole business and production data store for
content, agent runs, embeddings, Content KG, analytics facts, commerce facts,
memory facts, and publish gates.

Postiz runs its own PostgreSQL database inside `infrastructure/postiz/`.
Postiz data is distribution infrastructure and is never mixed with Meiti
business tables.

## Existing shared surfaces

- `content_embeddings`: semantic retrieval
- `content_entities` / `content_relations`: Content KG
- `publish_gates`: fail-closed approval state
- `agent_*`: auditable capability-agent runs and artifacts

The configured Meiti URL is `MEITI_DATABASE_URL` or `DATABASE_URL`. No provider
database, provider SQLite file, or provider-specific backend is part of the V3
architecture.
