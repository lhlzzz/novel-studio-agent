# Lechuang / XiaoleAI Creative Provider Contract

Lechuang is a generation execution backend. It is not a Social Provider,
not an Agent, and not a workspace. XiaoleAI and Lechuang share one
Creative credential. Do not add `LECHUANG_API_KEY`.

Evidence owners:

- Official request/response contract: `.agents/skills/media/xiaoleai-image-generation/scripts/generate_image.py`
- Production adapter: `creative/providers/lechuang/`
- Credential owner: `creative/providers/lechuang/credentials.py`

This document distinguishes three layers. Guessed support is never PASS.

1. Officially confirmed (repository evidence of the HTTP contract)
2. Currently supported by Meiti
3. Not verified

## 1. Officially confirmed

These fields are present in the XiaoleAI OpenAI-compatible image contract
checked into this repository.

| Item | Value |
| --- | --- |
| API Base URL | `https://api.xiaoleai.team/v1` (`XIAOLEAI_BASE_URL`) |
| API Key | `XIAOLEAI_API_KEY` |
| API Key Header | `Authorization: Bearer <key>` |
| Content-Type | `application/json` |
| Image endpoint | `POST /images/generations` only. Do not call `/image/created` as fallback. |
| Video create | `POST /videos` multipart/form-data |
| Video poll | `GET /videos/{id}` |
| Video download | `GET /videos/{id}/content` |
| Image request | `model`, `prompt`, `response_format=b64_json`, `image_size`, `aspect_ratio`, `quality`, `n` |
| Image response | `data[].b64_json`; optional `id` / `request_id`, `model`, `usage` |
| Image models | `gpt-image-2`, `gemini-2.5-flash-image`, `gemini-3.1-flash-image-preview`, `gemini-3-pro-image-preview` |
| image_size | `512`, `1K`, `2K`, `4K` |
| aspect_ratio | documented examples `1:1`, `16:9`, `9:16`; Meiti also sends `3:4` for Xiaohongshu |
| n | `1`–`4` for `gpt-image-2`; `1` for other models |
| Timeout | 600 seconds (request can exceed 100 seconds) |
| Auth failure | HTTP 401 / 403 |
| Rate limit | HTTP 429, optional `Retry-After` |
| Provider failure | HTTP 5xx |
| Invalid request | non-2xx, empty `data`, invalid Base64, unsupported image bytes |
| Result payload | inline `b64_json` (not a durable Meiti Asset URL) |

`usage` may appear on a successful image response. The repository does not
document a credit formula. If `usage` is absent, cost is `UNKNOWN`.

## 2. Currently supported by Meiti

| Capability | Status | Owner |
| --- | --- | --- |
| Shared Xiaole/Lechuang credential | supported | `load_creative_credential` |
| Image `POST /images/generations` | verified | `LechuangClient.generate_image` |
| Decode `b64_json` to PNG/JPEG/GIF/WEBP | verified | `decode_image` |
| Content-addressed filesystem persist | supported | `creative.assets.persist_bytes` |
| Asset commit / QA / lineage | supported | `PlatformAssetService.import_asset` |
| Prompt compile → generation request | supported | `PromptCompiler` |
| Creator OS submit (image) | supported | `ContinuityRuntime.submit_generation` |
| Idempotent submit (account+episode+prompt+spec) | supported | `ContinuityRuntime.submit_generation` |
| Fail-closed auth / 429 / 5xx / timeout | supported | `LechuangClient` |
| Video `POST /videos` | documented, live NOT_VERIFIED | `LechuangClient.generate_video` |
| Video poll `GET /videos/{id}` | documented, live NOT_VERIFIED | `LechuangClient.poll_video` |
| Video download `GET /videos/{id}/content` | documented, live NOT_VERIFIED | `LechuangClient._materialize_video` |
| Image-to-video via `input_reference[]` | documented, live NOT_VERIFIED | `LechuangClient.generate_video` |
| Image edit / image-to-image | NOT_VERIFIED | adapter raises `UnsupportedCapability` |
| Remote task poll for images | not applicable | image call is synchronous |
| Webhook | NOT_VERIFIED | no contract evidence |
| Social publish via Lechuang | forbidden | Creative never publishes |

Enabled means runtime-verified. YAML never sets `enabled: true`.

## 3. Not verified

No repository evidence exists for these Lechuang/XiaoleAI capabilities.
They stay `NOT_VERIFIED`. Do not guess endpoints, task ids, or PASS.

| Item | Status |
| --- | --- |
| Text generation interface | NOT_VERIFIED |
| Video live generation | NOT_VERIFIED until a real MediaAsset + TechnicalQA exists |
| Image edit / image-to-image | NOT_VERIFIED (`POST /image/edit` is documented, Meiti does not execute it yet) |
| `/created/video` | documented sync wait; Meiti does not use it. Async `/videos` is the production path |
| `/image/created` | documented image alias; Meiti does not use it as fallback |
| Webhook | NOT_VERIFIED |
| Webhook signature | NOT_VERIFIED |
| Video live MediaAsset + QA | NOT_VERIFIED |
| Video models documented | `grok-video`, `video-ds-2.0`, `video-ds-2.0-fast` |
| Video fields documented | `seconds`, `size`, `resolution_name`, `preset`, `input_reference[]` |
| Negative prompt (API field) | NOT_VERIFIED (Meiti keeps it on PromptPackage only) |
| Seed | NOT_VERIFIED |
| Billing / credits formula | NOT_VERIFIED (`cost_status=UNKNOWN` unless `usage` is returned) |
| Rate-limit quota numbers | NOT_VERIFIED (HTTP 429 is mapped) |
| Max file size | NOT_VERIFIED |
| URL expiry | NOT_VERIFIED |
| Remote cancel | NOT_VERIFIED (local cancel only) |
| `GET /models` or capability discovery API | NOT_VERIFIED |

Lechuang is the only Creative Provider. Image, video, and image-to-video all
execute through `LechuangClient`. There is no parallel xAI creative provider.

## Runtime states

Meiti creative jobs use:

`SUBMITTED`, `QUEUED`, `RUNNING`, `SUCCEEDED`, `FAILED`, `CANCELLED`,
`EXPIRED`, `UNKNOWN`

Image generation is a single HTTP call. Meiti records `SUBMITTED` before
the request and `SUCCEEDED` / `FAILED` after. There is no honest remote
`QUEUED`/`RUNNING` poll for Lechuang image until an async contract exists.

## Credential rules

- Env bootstrap: `XIAOLEAI_API_KEY`, `XIAOLEAI_BASE_URL`
- Production store: `MEITI_SECRET_DIR` via `RuntimeSecretStore`
- Logs must never print the API key
- Doctor reports `CONFIGURED` / `UNVERIFIED` / `VERIFIED` / `BLOCKED` / `ERROR`

## Doctor probes

| Probe | Meaning |
| --- | --- |
| `LECHUANG_API_CONFIGURED` | credential present |
| `LECHUANG_API_REACHABLE` | live HTTP only with `--live` |
| `LECHUANG_IMAGE_CAPABILITY_VERIFIED` | image contract verified |
| `LECHUANG_VIDEO_CAPABILITY_VERIFIED` | VERIFIED only after live video MediaAsset + QA |

`--live` is the only path allowed to spend image credits.
