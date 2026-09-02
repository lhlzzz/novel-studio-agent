# Meiti V4.4.2 Handoff

Branch `main`. Baseline `6c6df42`.

```text
Lechuang -> MediaAsset -> ContentPackage -> PlatformVariant
-> PublishGate -> DistributionJob -> Douyin/Kuaishou/XHS/Xianyu
-> Publication -> Reconciliation -> Analytics
```

SocialRuntime.production() is the unique production composition root.
CLI, doctor, worker, and DistributionAgent must take runtime from there.

XHS publish returns HANDOFF_REQUIRED. Xianyu requires explicit commerce
intent and Jushita.
