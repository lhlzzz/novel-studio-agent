# Distribution Job Gate

## Hard rule

- Output is not publication.
- External actions require evidence, capability, account validation, media
  validation, and explicit owner approval.
- A gate is evaluated against a `DistributionJob` and `Integration`, not a
  provider workspace.
- Any failed check is `BLOCKED`; the gate never bypasses an unsupported
  adapter.

## Commands

```bash
python scripts/publish_gate.py request \
  --action publish \
  --integration-id x \
  --distribution-job-id job-123 \
  --package packages/tweet-package-01-ai-efficiency-profit.md

python scripts/publish_gate.py approve --gate-key '...' --by boss
python scripts/publish_gate.py check --action publish \
  --integration-id x --distribution-job-id job-123
python scripts/publish_gate.py selftest
```

The CLI records and checks approval state. It does not execute external
publishing. `distribution-agent` is the only owner allowed to call a verified
adapter after the gate passes.

Approval artifacts are stored in `.gates/approvals/`.
