# Meiti Postiz Provider

Postiz is Meiti's external distribution execution engine. This provider owns
the translation between the provider-neutral distribution contract and the
Postiz Public API.

## Boundary

```text
ContentPackage -> DistributionJob -> Publish Gate -> PostizAdapter -> Postiz
```

Meiti owns content, jobs, approvals, and analytics records. Postiz owns OAuth,
connected channels, uploads, scheduling, publishing, and provider status.
There is no Postiz workspace or platform-specific Meiti agent here.

## Configuration

Set `POSTIZ_API_URL` and `POSTIZ_API_KEY` outside Git. Self-hosted Postiz
defaults to `http://127.0.0.1:4007` in local development.

Populate `config/postiz/integrations.yaml` only with IDs returned by Postiz
after an operator completes OAuth and verifies the account. Keep accounts
`pending` until that runtime verification exists.

The MCP contract is recorded in `config/postiz/mcp.yaml`. The self-hosted MCP
endpoint is `${POSTIZ_API_URL}/mcp` with Bearer authentication.

## Operations

`PostizClient` is the only HTTP owner. `PostizAdapter` implements
`list_integrations`, `get_integration`, `validate_payload`, `prepare_publish`,
`publish`, `schedule`, `get_status`, and `get_analytics`, plus media upload and
platform analytics helpers.
