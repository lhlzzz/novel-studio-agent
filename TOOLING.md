# Meiti V3.3 Tooling

## Meiti database

```bash
python scripts/db/migrate.py upgrade
python scripts/db/migrate.py history
python scripts/db/migrate.py verify
python scripts/embeddings.py selftest
```

The Meiti database uses `MEITI_DATABASE_URL` or `DATABASE_URL` and remains
separate from Postiz PostgreSQL. `seed` is opt-in demo data, not production.

## Distribution

```bash
docker compose -f infrastructure/postiz/docker-compose.yml up -d
python scripts/meiti_doctor.py
python scripts/runtime_check.py
curl --noproxy '*' "${POSTIZ_API_URL:-http://127.0.0.1:4007}/public/v1/is-connected"
```

Meiti-side Postiz configuration:

- `config/postiz/integrations.yaml` records verified account IDs.
- `config/postiz/mcp.yaml` records the self-hosted `/mcp` endpoint contract.
- `integrations/providers/resolver.py` routes adapters.
- `integrations/providers/postiz/` owns the client and adapter.

Do not mark a provider or account active until health, authentication,
integration discovery, capability verification, and a Gate-approved test
publish have all passed.

## Control plane

```bash
python -c "from services.control_plane import snapshot; print(snapshot().keys())"
```

## Research

Research skills live under `.agents/skills/intelligence/`.
`SCRAPECREATORS_API_KEY` is required for live research and is never committed.
Research remains read-only intelligence, not publication evidence.
