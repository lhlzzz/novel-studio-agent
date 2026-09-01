# Creative Runtime API

Meiti V4.2 production API. Agents select workflows; CreativeRuntime executes them.

## Composition root

`creative.runtime.container.CreativeRuntime`

MediaAgent, Creative API, Creative Worker, Doctor, and CLI obtain the engine,
store, resolvers, judges, cost, and replay owners from this container.

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

- Git templates: `creative/workflow/templates/`
- User/runtime versions: PostgreSQL `creative_workflows`
- Versions are immutable; edits create a new version
- `creative.workflow.resolver.WorkflowResolver` returns `ResolvedWorkflow`

## Provider API

`creative.providers.resolver.GenerationProviderResolver`

- `resolve(name)` — production never falls back to mock
- `select(requirement)` — ranks capability, model, node type, workflow, content type, health, cost, latency, success rate

Lechuang HTTP lives only in `LechuangClient`. Live calls stay BLOCKED until the official contract is verified.

## Judge API

`creative.judges`

- Technical QA is local
- Vision/video judges require a verified vision provider
- ContentFitJudge is not ContentPolicyGate
- Missing vision provider => BLOCKED, never PASS
