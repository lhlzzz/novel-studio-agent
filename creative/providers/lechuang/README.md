# Xiaole / Lechuang Provider

Lechuang is the only Creative Provider. It is not an Agent and not a workspace.
Image, video, and image-to-video all execute here. XiaoleAI and Lechuang share
one Creative credential.

```text
XIAOLEAI_API_KEY
XIAOLEAI_BASE_URL=https://api.xiaoleai.team/v1
```

Do not create `LECHUANG_API_KEY`. Image generation uses the verified
OpenAI-compatible contract from `.agents/skills/media/xiaoleai-image-generation/`.

## Verified

- Protocol: OpenAI-compatible
- Endpoint: `POST /images/generations`
- Request: `model`, `prompt`, `response_format=b64_json`, `image_size`, `aspect_ratio`, `n`
- Response: `data[].b64_json`
- Output: decoded image bytes persisted as `MediaAsset`

## Documented video contract (live NOT_VERIFIED)

Official docs at `docs.xiaoleai.team` expose:

- `POST /videos` multipart create (`model`, `prompt`, `seconds`, `size`, optional `resolution_name`/`preset`, `input_reference[]`)
- `GET /videos/{id}` status poll
- `GET /videos/{id}/content` MP4 download

Meiti uses that async path only. It does not fall back to `/created/video` or
`/image/created`. Video stays `NOT_VERIFIED` until a live MediaAsset + TechnicalQA
succeeds.

The full contract ledger is `docs/integrations/lechuang.md`. That file
separates official evidence, Meiti-supported capabilities, and unverified
claims. Guessed support is never PASS.
