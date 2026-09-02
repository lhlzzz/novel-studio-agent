# Meiti V4.4 Handoff

Branch `main`. Creative Workflow Engine is in `creative/`. Native social is in `social/`.

Production path:

```text
resolve_agent -> Strategy.creative_requirement -> MediaAgent
-> WorkflowResolver -> CreativeWorkflowEngine -> ProviderResolver
-> Lechuang (live BLOCKED) or mock -> AI Gateway vision judge -> MediaAsset
-> ContentPackage -> DistributionJob -> Publish Gate
-> SocialProviderResolver -> Native Adapter -> Publication
-> analytics snapshots -> workflow performance -> memory
```

Doctor: `python scripts/meiti_doctor.py`
Social doctor: `python scripts/social_doctor.py`
Creative doctor: `python scripts/creative_doctor.py`
Runtime JSON: `python scripts/runtime_check.py`
