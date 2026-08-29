# Meiti V3.3 Next Action

**GOAL:** Authenticate a real Postiz runtime and verify one overseas account
without weakening the fail-closed gate.

**VERIFY:** Only authenticated, runtime-tested integrations become enabled.

1. Start `infrastructure/postiz/docker-compose.yml` and confirm
   `GET /public/v1/is-connected` without an HTTP proxy.
2. Set `POSTIZ_API_KEY` in the operator environment, never in git.
3. Complete X OAuth in Postiz, then record the returned integration_id in
   `config/postiz/integrations.yaml` with `status: pending` until publish
   verification succeeds.
4. Run a Gate-approved `MEITI V3 POSTIZ E2E TEST` to that test account only.
