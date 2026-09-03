# Xiaole / Lechuang Provider

Lechuang is a generation provider, not an Agent and not a workspace.
XiaoleAI and Lechuang share one Creative credential.

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

## NOT_VERIFIED

Video generation, image-to-video, video extend, video edit, and image editing
are not present in repository evidence. They stay `NOT_VERIFIED`. Do not guess
those endpoints.
