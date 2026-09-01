# Creative Runtime API

Meiti V4.1 production API. Agents select workflows; this module executes them.

## Creative API

`creative.api.CreativeAPI`

- `create_run(workflow_id, inputs, budget=None, idempotency_key=None)`
- `get_run(run_id)`
- `resume_run(run_id)`
- `cancel_run(run_id)`
- `replay_run(run_id)`
- `list_runs(status=None)`
- `get_task(task_id)`
- `list_assets(run_id=None)`
- `get_asset(asset_id)`

Replay creates a new run with `replay_of` set. Identical inputs reuse `idempotency_key`.

## Workflow API

`creative.workflow.registry`

- `list_workflows()`
- `resolve_workflow(workflow_id, version=None)`
- `register_workflow(workflow)` — versions are immutable
- `validate_workflow(workflow, inputs)` in `creative.validation`

`creative.workflow.resolver.resolve_from_requirement(requirement)` ranks templates. MediaAgent is the only agent entry.

## Provider API

`creative.providers.resolver.GenerationProviderResolver`

- `resolve(name)` — production never falls back to mock
- `select(requirement)` — `ProviderRanker` scores verified capability, history, cost, latency, preference

Lechuang HTTP lives only in `LechuangClient`: `create_task`, `get_task`, `cancel_task`, `get_result`, `upload_asset`. Live calls stay BLOCKED until the official contract is verified.

## Asset API

`creative.store.CreativeStore` + `creative.assets.AssetStore`

- Content-addressed files at `media/assets/<aa>/<sha256>.<ext>`
- `MediaAsset` rows in PostgreSQL
- `CharacterRepository` persists characters; references must be MediaAssets

## Judge API

`creative.providers.judge.VisionJudgeResolver`

- `judge_image`, `judge_video`, `judge_frames`, `judge_consistency`
- Technical QA uses Pillow / ffprobe
- Missing vision provider => BLOCKED, never PASS
