---
name: xiaoleai-image-generation
description: Generate raster images through the XiaoleAI OpenAI-compatible image API and save returned b64_json data as local image files. Use when the user asks to create or regenerate an image with gpt-image-2 or supported Gemini image models, especially when they provide a XiaoleAI API key or request this relay endpoint.
metadata:
  short-description: "Generate images via XiaoleAI gpt-image-2 or Gemini image APIs."
---

# Shared Image Generation

This is the single image-generation owner for all six platform workspaces.
Platforms call this skill by reference; they must not copy the API client, API
key, prompt library, or generated assets into their own workspace.

Prompt construction is provided by the separately installed
`gpt-image-2-style-library` skill from
`freestylefly/awesome-gpt-image-2` at commit
`685469889fb72fd5adefae45e1645d527edcb5e7`. Read its `SKILL.md` and
`references/style-library.md` before selecting a template or style.

Production image generation is owned by the Meiti Creative Engine
(`creative.providers.lechuang`). This skill documents the XiaoleAI
OpenAI-compatible contract, models, and prompt constraints. Do not run a
second production media pipeline from this skill.

The historical `scripts/generate_image.py` is the source of the verified
request/response contract. Creative Provider reuses that contract:

- `XIAOLEAI_API_KEY`
- `XIAOLEAI_BASE_URL` default `https://api.xiaoleai.team/v1`
- `POST /images/generations`
- `response_format=b64_json`
- decode `data[].b64_json`, validate image signature, persist `MediaAsset`

Use `python scripts/meiti.py creative generate-image --prompt "..."` for
production execution.

## Preconditions

- Configure `XIAOLEAI_API_KEY` in the runtime environment. The repository does not contain a fallback key.
- Never print or include the API key in generated logs, reports, commits, or user-facing replies.
- The default base URL is `https://api.xiaoleai.team/v1`.
- The request can take more than 100 seconds; use the script's 600-second default timeout unless the user specifies otherwise.
- Image generation is an external/paid action. Before making a real request, confirm that the user has supplied or configured the key and has asked to generate the image.

## Standard Workflow

1. Normalize the user's prompt without adding unrelated subjects, text, logos, or styling.
2. Choose `gpt-image-2` unless the user names another supported image model.
3. Keep `response_format=b64_json` and `stream=false` behavior.
4. Set `image_size` and `aspect_ratio` from the request. For a vertical master reference, use `2K`, `9:16`, and `n=1` unless the user asks for variants.
5. Save output into the project or the user-specified destination. Do not overwrite an existing file unless explicitly requested.
6. Inspect the generated image for the requested subject, framing, identity anchors, missing limbs, cropping, text artifacts, and negative constraints.
7. Report the saved path, model, size, ratio, image count, and request ID. Do not report the API key.

## Command

```bash
python .agents/skills/media/xiaoleai-image-generation/scripts/generate_image.py \
  --prompt-file /path/to/prompt.txt \
  --output-prefix /path/to/master_front \
  --model gpt-image-2 \
  --image-size 2K \
  --aspect-ratio 9:16 \
  --n 1
```

For a prompt supplied directly:

```bash
python .agents/skills/media/xiaoleai-image-generation/scripts/generate_image.py \
  --prompt "A concise image prompt" \
  --output-prefix ./generated/image
```

For a platform-owned internal asset, pass `--platform`. The shared owner then
chooses a platform default ratio and writes to the root shared asset directory:

```bash
python .agents/skills/media/xiaoleai-image-generation/scripts/generate_image.py \
  --platform xiaohongshu \
  --asset-name elder-care-note-cover \
  --prompt-file /path/to/prompt.txt \
  --model gpt-image-2 \
  --image-size 2K \
  --n 1
```

Supported platforms are `xiaohongshu`, `kuaishou`, `douyin`, `x`,
`shipinghao`, and `xianyu`. Defaults are `3:4` for xiaohongshu, `9:16` for
快手/抖音/视频号, `16:9` for X, and `1:1` for 闲鱼. Pass
`--aspect-ratio` when the brief needs another ratio.

Use `--endpoint created` only when the caller explicitly requests the alternate `/v1/image/created` endpoint. Set `XIAOLEAI_BASE_URL` to override the service base URL. The script accepts `--timeout` and `--overwrite` when needed.

## Supported Request Values

- Models: `gpt-image-2`, `gemini-2.5-flash-image`, `gemini-3.1-flash-image-preview`, `gemini-3-pro-image-preview`
- `image_size`: `512`, `1K`, `2K`, `4K`
- `aspect_ratio`: values such as `1:1`, `16:9`, and `9:16`
- `n`: `1` to `4` for `gpt-image-2`; use `1` for other models

If the API returns a non-2xx response, an empty `data` array, invalid Base64, or unsupported image bytes, stop and surface the actionable error. Do not retry paid requests automatically.

Image generation remains an external/paid action. Platform agents may prepare
prompts and internal assets, but this skill never logs in, publishes, lists,
quotes, collects payment, or bypasses a `meiti` gate.
