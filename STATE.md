# Meiti V3.3 State

- Legacy workspace and platform-specific backend/topology remain deleted.
- Agent runtime registry resolves executable implementations.
- ProviderResolver is the only adapter routing mechanism.
- Integration YAML cannot enable a provider; enabled requires runtime verification.
- ContentPackage, Campaign, StrategyPlan, DistributionAttempt, and Publication
  are first-class objects.
- PostizClient owns health, typed errors, retry/backoff, and HTTP.
- Media is hashed and uploaded before create_post; identity is SHA256.
- DistributionJob has a legal state machine, idempotency_key, attempts, and dead-letter.
- Publications persist job id, provider post id, and platform object id separately.
- Reconciliation and analytics workers exist; snapshots are append-only.
- Control Plane and Doctor report PASS/WARN/BLOCKED plus JSON `{ready, checks}`.
- Production migrations do not write demo rows.
- Research skills stay read-only and unavailable without credentials.
- Mock E2E covers dry-run, publish, reconciliation, analytics, and memory.
- Real Postiz runtime is not authenticated in this environment unless an operator
  supplies POSTIZ_API_KEY, a running Postiz stack, and one verified overseas account.

Run `python -m pytest`, `python scripts/meiti_doctor.py`, and
`python scripts/runtime_check.py` after changes.
