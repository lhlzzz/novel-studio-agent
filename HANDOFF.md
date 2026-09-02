# Meiti V4.4.3 Handoff

Branch `main`. Baseline `5a57bc2`.

```text
Lechuang -> MediaAsset -> ContentPackage -> PlatformVariant
-> PublishGate -> DistributionJob
-> Douyin/Kuaishou Publication or XHS Handoff or Xianyu Listing
-> Reconciliation -> Analytics
```

SocialRuntime.production() is the unique production composition root.
XHS publish returns READY_FOR_XHS and persists XHSHandoff.
Xianyu requires explicit commerce intent and Jushita.
Lechuang remains BLOCKED_EXTERNAL without an official contract.
