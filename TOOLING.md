# Meiti V3 Tooling

## Meiti database

```bash
python scripts/db/migrate.py bootstrap
python scripts/db/migrate.py verify
python scripts/embeddings.py selftest
```

The Meiti database uses `MEITI_DATABASE_URL` or `DATABASE_URL` and remains
separate from Postiz PostgreSQL.

## Distribution

```bash
docker compose -f infrastructure/postiz/docker-compose.yml up -d
postiz --help
postiz integrations:list
curl -I "${POSTIZ_API_URL:-http://127.0.0.1:4007}"
```

The compose file is an operator-owned integration point. It does not copy
Postiz application code into Meiti.

Meiti-side Postiz configuration:

- `config/postiz/integrations.yaml` records verified account IDs.
- `config/postiz/mcp.yaml` records the self-hosted `/mcp` endpoint contract.
- `integrations/providers/postiz/` owns the client and adapter.

Do not mark a provider or account active until `docker ps`, the Postiz UI, API
authentication, and `integrationList` have all been verified.

## Research

Research skills live under `.agents/skills/research/` when installed from the
official source. `SCRAPECREATORS_API_KEY` is required for live research and
is never committed.
