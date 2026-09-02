# Meiti V4.4.2

Meiti is an AI Creator Operating System.

```text
Lechuang = Creative Provider
CN Social = Native Distribution
```

```text
User -> MediaAgent -> Creative Workflow -> Provider Resolver -> Lechuang
-> MediaAsset -> Technical QA -> AI Judge -> ContentPackage
-> Platform Variant -> Publish Gate -> DistributionJob
-> CN Social Provider Resolver -> 小红书 / 抖音 / 快手 / 闲鱼
-> Publication -> Reconciliation -> Analytics -> Memory
```

Creative Provider generates media. Social Provider publishes. Creative never
publishes. Social never generates media.

## Current production set

- 小红书: official surface is the client share SDK. Meiti prepares a note
  package and returns `HANDOFF_REQUIRED`. Direct server publish stays BLOCKED
  until an official server-side API is verified. Public access is currently
  paused; do not fake it.
- 抖音: official OAuth + video/image publish + query. Create success is not
  PUBLISHED; reconciliation maps review/processing.
- 快手: official `user_video_publish` (`start_upload` -> upload -> publish).
  Publish success is SUBMITTED until photo query.
- 闲鱼: marketplace listing, not a social post. Production listing APIs
  require 聚石塔 (`MEITI_XIANYU_DEPLOYMENT_MODE=JUSHITA`). Local mode stays
  BLOCKED.

Overseas adapters (X/Instagram/YouTube/TikTok/LinkedIn) remain in tree and
are frozen this round.

Do not claim all four CN platforms auto-publish unless real E2E evidence
exists in `docs/audits/meiti-v4.4.2-cn-e2e.json`.

```bash
python -m pytest
python scripts/social_doctor.py
python scripts/meiti_doctor.py
python scripts/runtime_check.py
python scripts/db/migrate.py verify
python -m scripts.meiti social doctor
```
