# Meiti V4.8.2 Production Readiness

This version hardens the human production chain. It does not add a second
creator engine, prompt compiler, asset store, task engine, or analytics store.

## Lanes

- `SYSTEM_CAPABILITY` is schema + unique owners (compiler, asset service, package, handoff).
- `ACCOUNT_CONFIGURATION` is a real ACTIVE account with character, world, series, pool, DNA, learning profile, and operating state.
- `CORE_PRODUCTION=READY` means the human chain can start: Account + Task + Prompt + Manual Creative + Import + QA + Package + Handoff.
- `PRODUCTION_EVIDENCE` requires a complete ProductionRun plus Prompt/Asset/QA/Package/Handoff evidence.
- `POST_PRODUCTION` and `FULL_LOOP` stay `NOT_VERIFIED` until real analytics and learning exist.

## Operator chain

User idea → Account OS → Task OS → Content Planner → Episode → PromptCompiler → COPY READY → Operator / Lechuang → real asset import → Technical QA → lineage → ContentPackage → XHS handoff → task complete.

XHS remains `HANDOFF_ONLY`. Handoff is not publication.

## Fail closed

- Canonical analytics writes first. Projection never continues after canonical failure.
- Unknown analytics stay null / `NOT_VERIFIED`, never forged zeros.
- Learning cannot be `VERIFIED` without episode + analytics.
- Primary import requires `prompt_id` or an audited `NO_PROMPT_REFERENCE`.
- Task `DONE` history is not mutated; reopen creates a new task.

## Not required for CORE_PRODUCTION

Analytics, Learning, Vector, real social E2E, and real video API remain `NOT_VERIFIED` until real external evidence exists.
