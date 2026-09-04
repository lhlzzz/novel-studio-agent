# Meiti V4.8.3 Production Integrity

This version hardens production integrity. It does not add a second creator
engine, prompt compiler, asset store, task engine, or analytics store.

## Lanes

- `CODE_STRUCTURE` is schema + unique owners.
- `SEMANTIC_INVARIANTS` are fail-closed production contracts.
- `REAL_PRODUCTION_EVIDENCE` requires operator Lechuang assets, handoff, and
  verified provider analytics.
- `CORE_PRODUCTION` is computed from `ProductionReadinessService`.
- `POST_PRODUCTION` stays `NOT_VERIFIED` until real provider analytics and
  verified learning exist.

## Fail closed

- Asset import is one transaction: asset, receipt, evidence, lineage, episode
  binding, production run, reference snapshots.
- Episode-level readiness never falls back to the latest episode.
- Current production account must be `ACTIVE`.
- Missing package is `PACKAGE_MISSING`, never PASS.
- Handoff cannot set `last_published_episode`.
- Publish gate blocks `media_uploaded=False` when media is required.
- Manual analytics cannot become `VERIFIED`.
- Unverified learning cannot update `PlatformLearningProfile`.
