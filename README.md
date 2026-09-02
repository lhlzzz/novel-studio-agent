# Meiti V4.4

Meiti is an AI Creator Operating System.

```text
Meiti + Creative Workflow + Lechuang + Native Social
```

```text
User -> MediaAgent -> Creative Runtime -> Workflow Graph -> Node
-> Provider Resolver -> Creative Provider -> MediaAsset
-> Technical QA -> AI Judge -> Policy Gate -> ContentPackage
-> Social Account -> Native Platform Adapter -> Publication
-> Analytics -> Memory -> Strategy
```

```text
Meiti
│
├── Intelligence
├── Strategy
├── Content
├── Creative Workflow
│     └── Lechuang / AI Providers
│
├── Memory
├── Analytics
├── Commerce
│
└── Social
      ├── Account Manager
      ├── Provider Resolver
      ├── X
      ├── Instagram
      ├── YouTube
      ├── TikTok
      └── LinkedIn
```

Media Agent selects a CreativeWorkflow. The runtime container constructs the
engine, store, resolvers, judges, cost, and replay owners. Workers lease runs
from PostgreSQL. Providers are execution backends, never agents. Creative
generation never publishes. Social providers never generate media.

Live Lechuang calls stay BLOCKED until `LECHUANG_API_KEY`, `LECHUANG_API_URL`,
and a verified API contract exist. AI Judge stays BLOCKED without a vision
provider. Real social publish stays BLOCKED until native OAuth and a verified
account exist. Mock creative is tests-only.

```bash
python -m pytest
python scripts/creative_doctor.py
python scripts/meiti_doctor.py
python scripts/social_doctor.py
python scripts/runtime_check.py
python scripts/db/migrate.py verify
```

`Platform = Integration`; `Platform != Workspace`; `Platform != Agent`.
