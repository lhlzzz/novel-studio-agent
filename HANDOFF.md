# Meiti V4.5 Handoff

Branch `main`. Production activation of V4.4.4 CN social runtime.

```text
Lechuang -> MediaAsset -> ContentPackage -> PlatformVariant
-> PublishGate -> DistributionJob
-> Douyin/Kuaishou Publication or XHS Handoff or Xianyu Listing
-> Reconciliation -> Analytics
```

SocialRuntime.production() is the unique production composition root.
`python scripts/meiti.py bootstrap-production` is the production init entry.
XHS publish returns HandoffOutcome and persists one XHSHandoff per job.
Xianyu returns ListingOutcome. Publication is only for native social posts.
Refresh is account-scoped and is not hidden inside `_credentials()`.
MediaUpload is first-class; variant metadata is not authoritative.
Lechuang remains BLOCKED_EXTERNAL without an official contract.
