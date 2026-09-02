# Meiti V4.4.4 Handoff

Branch `main`. Production closure of V4.4.3 CN social runtime.

```text
Lechuang -> MediaAsset -> ContentPackage -> PlatformVariant
-> PublishGate -> DistributionJob
-> Douyin/Kuaishou Publication or XHS Handoff or Xianyu Listing
-> Reconciliation -> Analytics
```

SocialRuntime.production() is the unique production composition root.
XHS publish returns HandoffOutcome and persists one XHSHandoff per job.
Xianyu returns ListingOutcome. Publication is only for native social posts.
Refresh is account-scoped and is not hidden inside `_credentials()`.
Lechuang remains BLOCKED_EXTERNAL without an official contract.
