# Meiti V4.2 Tooling

## Creative

```bash
python scripts/creative_doctor.py
python -m pytest tests/creative tests/e2e/test_creative_loop.py
```

Runtime: `creative.runtime.container.CreativeRuntime`
Templates: `creative/workflow/templates/`
Engine: `creative.workflow.engine.CreativeWorkflowEngine`
Generation resolver: `creative.providers.resolver.GenerationProviderResolver`
Lechuang contract: `creative/providers/lechuang/`
Worker: `services.workers.creative_worker`

Environment (never commit secrets):

```env
DATABASE_URL=
LECHUANG_API_URL=
LECHUANG_API_KEY=
POSTIZ_API_URL=
POSTIZ_API_KEY=
SCRAPECREATORS_API_KEY=
```

Live generation stays BLOCKED while the official request/response schema is
unverified. Do not guess endpoints.

## Meiti database

```bash
python scripts/db/migrate.py upgrade
python scripts/db/migrate.py history
python scripts/db/migrate.py verify
```

## Distribution

```bash
docker compose -f infrastructure/postiz/docker-compose.yml up -d
python scripts/meiti_doctor.py
python scripts/runtime_check.py
```

ProviderResolver routes distribution adapters. CreativeWorkflow never calls
the distribution provider.

## Control plane

```bash
python -c "from services.control_plane import snapshot; print(snapshot().keys())"
```
