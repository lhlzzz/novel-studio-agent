# Meiti V4.2

Meiti is an AI Creator Operating System.

```text
Meiti + Creative Workflow + Lechuang + Postiz
```

```text
User -> MediaAgent -> Creative Runtime -> Workflow Graph -> Node
-> Provider Resolver -> Creative Provider -> MediaAsset
-> Technical QA -> AI Judge -> Policy Gate -> ContentPackage
-> Distribution -> Analytics -> Memory -> Strategy
```

```text
Meiti = Brain + Memory + Workflow + Judgment + Learning
Lechuang = Generation Provider
Postiz = Distribution Provider
```

Media Agent selects a CreativeWorkflow. The runtime container constructs the
engine, store, resolvers, judges, cost, and replay owners. Workers lease runs
from PostgreSQL. Providers are execution backends, never agents. Creative
generation never publishes. Distribution never generates media.

Live Lechuang calls stay BLOCKED until `LECHUANG_API_KEY`, `LECHUANG_API_URL`,
and a verified API contract exist. AI Judge stays BLOCKED without a vision
provider. Real distribution stays BLOCKED without `POSTIZ_API_KEY` and a
verified account. Mock creative is tests-only.

```bash
python -m pytest
python scripts/creative_doctor.py
python scripts/meiti_doctor.py
python scripts/runtime_check.py
python scripts/db/migrate.py verify
```

`Platform = Integration`; `Platform != Workspace`; `Platform != Agent`.
