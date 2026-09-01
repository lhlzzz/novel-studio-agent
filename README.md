# Meiti V4.1

Meiti is an AI Creator Operating System.

```text
Meiti + Creative Workflow + Lechuang + Postiz
```

```text
Research -> Strategy -> Creative Direction -> Creative Workflow
-> Durable Creative Runtime -> Async Provider Execution
-> Real Asset Persistence -> Real AI Quality Judgment
-> Cost Control -> Replay / Resume -> ContentPackage
-> Postiz Distribution -> Analytics -> Memory -> Strategy
```

```text
Meiti = Brain + Memory + Workflow + Judgment + Learning
Lechuang = Generation Provider
Postiz = Distribution Provider
```

Media Agent selects a CreativeWorkflow. The engine executes a durable node
graph. Providers are execution backends, never agents. Creative generation
never publishes. Distribution never generates media.

Live Lechuang calls stay BLOCKED until `LECHUANG_API_KEY`, `LECHUANG_API_URL`,
and a verified API contract exist. Mock creative is tests-only.

```bash
python -m pytest
python scripts/creative_doctor.py
python scripts/meiti_doctor.py
python scripts/runtime_check.py
python scripts/db/migrate.py verify
```

`Platform = Integration`; `Platform != Workspace`; `Platform != Agent`.
