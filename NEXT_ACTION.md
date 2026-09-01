# Meiti V4.3 Next Action

**GOAL:** Keep Meiti BLOCKED until real operator credentials and the official
Lechuang contract exist, then run one real image plus image-to-video E2E and
one Postiz TEST publication.

**VERIFY:** `python scripts/meiti_doctor.py` prints `Overall: READY` only after
real IDs exist in `docs/audits/meiti-v4.3-production-e2e.json`.

1. Obtain Lechuang `base_url`, auth, endpoints, models, and schemas from the
   official key/docs surface. Put the key in the operator environment only.
2. Set `AI_GATEWAY_API_KEY` / `AI_GATEWAY_API_URL` for vision. Do not merge this
   provider with Lechuang.
3. Start `infrastructure/postiz` and set `POSTIZ_API_KEY`, then verify one
   overseas account before enabling it.
4. Set `SCRAPECREATORS_API_KEY` before treating Research as available.
