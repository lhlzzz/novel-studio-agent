# Meiti V3.3 Handoff

Branch `main`. Legacy workspace topology is gone.

Production path:

```text
resolve_agent → Campaign → ContentPackage → ContentVariant → DistributionJob
→ Publish Gate → ProviderResolver → Adapter → Publication
→ reconciliation worker → analytics snapshots → memory write-back
```

Mock E2E is in `tests/e2e/`. Real Postiz publish is blocked until an operator
supplies `POSTIZ_API_KEY`, a running Postiz process, and one verified overseas
account.

Doctor: `python scripts/meiti_doctor.py`
Runtime JSON: `python scripts/runtime_check.py`
Control Plane: `services.control_plane.snapshot()`
