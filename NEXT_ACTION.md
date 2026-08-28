# Meiti V3 Next Action

**GOAL:** Verify real distribution connectors and continue the research to
strategy to content to measurement loop without recreating provider ownership.

**VERIFY:** Only authenticated, runtime-tested integrations become enabled.

1. Configure Postiz credentials in the operator environment and run
   `postiz auth:status` followed by `postiz integrations:list`.
2. Start the official Postiz Compose stack when Docker image access is
   available; check the service health endpoint and isolated dependencies.
3. Keep domestic custom adapters disabled until each connector has real
   capability, authentication, media, analytics, and rate-limit evidence.
4. Expand analytics normalization, memory retrieval, commerce evidence, and
   experiment attribution on the existing Meiti PostgreSQL + pgvector,
   Content KG, and Obsidian surfaces.

## External acceptance blocker

Complete Postiz device authorization or set `POSTIZ_API_KEY`, then retry the
official Compose stack after Docker Hub access is restored. Only after
`postiz integrations:list` returns a real account should one test Integration
be registered and a Gate-approved test post attempted.
