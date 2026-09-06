# Meiti V4.4 Tooling

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
XIAOLEAI_API_KEY=
XIAOLEAI_BASE_URL=https://api.xiaoleai.team/v1
X_CLIENT_ID=
X_CLIENT_SECRET=
X_REDIRECT_URI=
SCRAPECREATORS_API_KEY=
```

Lechuang is the only Creative Provider. Image generation uses the verified
XiaoleAI OpenAI-compatible contract. Video and image-to-video use the official
async `/videos` contract and stay NOT_VERIFIED until live MediaAsset +
TechnicalQA evidence exists. Do not guess endpoints.

## Meiti database

```bash
python scripts/db/migrate.py upgrade
python scripts/db/migrate.py history
python scripts/db/migrate.py verify
```

## Social

```bash
python scripts/meiti.py social accounts
python scripts/meiti.py social verify
python scripts/social_doctor.py
python scripts/meiti_doctor.py
python scripts/runtime_check.py
```

SocialProviderResolver routes native platform adapters. CreativeWorkflow never
calls a social provider. Meiti owns scheduling.

## Control plane

```bash
python -c "from services.control_plane import snapshot; print(snapshot().keys())"
```
