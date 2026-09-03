# Meiti V4.5.3 Handoff

Branch `main`. Production activation hardening of V4.5.

```text
Lechuang -> MediaAsset -> ContentPackage -> PlatformVariant
-> PublishGate -> DistributionJob
-> Douyin/Kuaishou Publication or XHS Handoff or Xianyu Listing
-> Reconciliation -> Analytics
```

SocialRuntime.production() is the unique production composition root.
`python scripts/meiti.py bootstrap-production` is read-only preflight.
Credentials enter RuntimeSecretStore only via OAuth callback or
`python scripts/meiti.py credentials put --provider lechuang` using `XIAOLEAI_API_KEY`.
Provider get_status/analytics require account_id.
XHS publish returns HandoffOutcome. Xianyu returns ListingOutcome.
CODE_COMPLETE = true. EXTERNAL_READY = false. PRODUCTION_READY = false.
