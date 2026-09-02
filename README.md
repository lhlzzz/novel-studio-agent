# Meiti V4.4.3

Meiti is an AI Creator Operating System.

```text
Lechuang = Creative Provider
Xiaohongshu = Handoff
Douyin = Native API
Kuaishou = Native API
Xianyu = Native listing + Jushita
Postiz = does not exist
```

```text
User -> MediaAgent -> Creative Workflow -> Provider Resolver -> Lechuang
-> MediaAsset -> Technical QA -> AI Judge -> ContentPackage
-> Platform Variant -> Publish Gate -> DistributionJob
-> CN Social Provider Resolver
-> XHS Handoff / Douyin Publication / Kuaishou Publication / Xianyu Listing
-> Reconciliation -> Analytics -> Memory
```

Creative generates media. Social publishes or hands off. Creative never
publishes. Social never generates media. Handoff is not a Publication.
Content is not commerce.

## Production composition

`SocialRuntime.production()` is the unique production composition root.
CLI, API, workers, Doctor, Control Plane, Scheduler, Reconciliation, and
Analytics take store/secrets from that runtime. Testing uses
`SocialRuntime.testing()`.

## Current production set

- 小红书: official surface is the client share SDK. Meiti prepares a note
  package and persists `XHSHandoff`. Direct server publish is BLOCKED.
  Remote reconciliation is NOT_APPLICABLE. Account status is `HANDOFF_READY`.
- 抖音: official OAuth + video/image upload + create. HTTP 200 create is
  SUBMITTED/PROCESSING, not PUBLISHED. Reconciliation maps remote state.
- 快手: official `user_video_publish` (`start_upload` -> upload -> publish).
  Whole-file threshold follows the official 10MB helper. Publish success is
  PROCESSING until photo query.
- 闲鱼: marketplace listing, not a social post. Production listing requires
  `MEITI_XIANYU_DEPLOYMENT_MODE=JUSHITA` and explicit commerce intent.

Overseas adapters (X/Instagram/YouTube/TikTok/LinkedIn) remain in tree and
are frozen this round.

Do not claim production verified or real E2E unless evidence exists in
`docs/audits/meiti-v4.4.3-cn-e2e.json`.

```bash
python -m pytest
python scripts/social_doctor.py
python scripts/meiti_doctor.py
python scripts/runtime_check.py
python scripts/db/migrate.py verify
python -m scripts.meiti social doctor
```
