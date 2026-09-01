# Meiti V4 Next Action

**GOAL:** Extract the official Lechuang API contract from the operator key/docs
surface, then verify one image and one image-to-video task without guessing.

**VERIFY:** `creative_doctor.py` reports Lechuang auth/image/video PASS only
after a real create-task -> poll -> persist cycle.

1. Obtain Lechuang `base_url`, auth, endpoints, models, and schemas from the
   official key/docs surface. Put the key in the operator environment only.
2. Fill `creative/providers/lechuang/models.yaml` with verified=true only after
   runtime evidence.
3. Keep Postiz live publish blocked until `POSTIZ_API_KEY`, a running Postiz
   process, and one verified overseas account exist.
