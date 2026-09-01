# Lechuang Provider

Lechuang is a generation provider, not an Agent and not a workspace.

Meiti calls a documented HTTP API. It does not drive the Lechuang canvas UI.

## Live status

The public web did not yield a reliable official API document during this
implementation. Until an operator extracts `base_url`, authentication,
endpoints, models, and request/response schema from Lechuang's own key/docs
surface:

- `LECHUANG_API_KEY` / `LECHUANG_API_URL` may be present
- `LechuangAdapter` methods exist
- live calls raise `ProviderBlocked` or `UnsupportedCapability`
- doctor reports `Lechuang Live = BLOCKED`

Do not guess URLs, models, or payloads.

## Contract

`generate_text`, `generate_image`, `edit_image`, `generate_video`,
`extend_video`, `edit_video`, `upload_asset`, `create_task`, `get_task`,
`cancel_task`, `get_result`.

Claimed capabilities live in `models.yaml` with `verified: false`.

## Typed contract

Meiti-side request/response types live in `schemas.py`. HTTP endpoints stay empty
in `models.yaml` until the official Lechuang contract is extracted. `verified: true`
is forbidden without a real create/poll/result cycle.
