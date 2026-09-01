# Meiti V4 Creative Workflow OS

Status: ACTIVE
Owner: media-agent + creative workflow engine
Date: 2026-09-01

## Goal

Replace isolated media generation with a Creative Workflow Engine.
Lechuang is a generation provider. Postiz remains the distribution provider.
Live generation is BLOCKED until the Lechuang API contract is extracted and
authenticated. Mock creative must pass.

## Tasks

T1. Delete isolated generation (`scripts/generate_xiaoye.py`) and record the cut.
T2. Add `creative/` schemas, errors, assets, judge, prompts, cost, persistence.
T3. Add workflow registry, YAML templates, resolver, and JSON export.
T4. Add node executors, engine, async tasks, worker, idempotency, replay.
T5. Add generation ProviderResolver, mock provider, Lechuang contract (no guessed API).
T6. Refactor MediaAgent onto the engine; wire strategy/content/orchestrator.
T7. Extend analytics experiments, memory write-back, ContentPackage assembly, doctor.
T8. Add `tests/creative/` plus mock E2E; keep distribution tests green.
T9. Rewrite AGENTS/RULES/README/STATE/TASK/TOOLING/DECISIONS/HANDOFF/NEXT_ACTION.
T10. Architecture residue checks, knowledge graph, pytest, honest READY status.

## Constraints

- No guessed Lechuang endpoints, models, or payloads.
- MediaAgent does not import LechuangAdapter.
- DistributionAgent does not import PostizAdapter.
- Creative never publishes.
- Assets are immutable and keyed by sha256.
- Agents do not poll with sleep.
- Do not revert unrelated dirty V3 files.

## Verify

```bash
python -m pytest
python scripts/creative_doctor.py
python scripts/meiti_doctor.py
python scripts/runtime_check.py
```
