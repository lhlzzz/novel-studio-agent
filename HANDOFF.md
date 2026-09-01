# Meiti V4.3 Handoff

Branch `main`. Creative Workflow Engine is in `creative/`.

Production path:

```text
resolve_agent -> Strategy.creative_requirement -> MediaAgent
-> WorkflowResolver -> CreativeWorkflowEngine -> ProviderResolver
-> Lechuang (live BLOCKED) or mock -> AI Gateway vision judge -> MediaAsset
-> ContentPackage -> DistributionJob -> Publish Gate
-> ProviderResolver -> Postiz -> Publication
-> analytics snapshots -> workflow performance -> memory
```

Doctor: `python scripts/meiti_doctor.py`
Creative doctor: `python scripts/creative_doctor.py`
Runtime JSON: `python scripts/runtime_check.py`
