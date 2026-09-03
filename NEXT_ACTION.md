# Meiti V4.5.3 Next Action

**GOAL:** Keep live READY blocked until real CN credentials, Jushita, and
the official Lechuang contract exist.

1. Set `MEITI_SECRET_DIR` (0700) and PostgreSQL, then run
   `python scripts/meiti.py bootstrap-production`.
2. Provision the shared Xiaole/Lechuang credential with `python scripts/meiti.py credentials put --provider lechuang` after setting `XIAOLEAI_API_KEY`.
3. Douyin: `DOUYIN_CLIENT_KEY` / `DOUYIN_CLIENT_SECRET` / `DOUYIN_REDIRECT_URI`,
   OAuth, verify, enable, then one real video publish + reconcile.
4. Kuaishou: `KUAISHOU_APP_ID` / `KUAISHOU_APP_SECRET` / `KUAISHOU_REDIRECT_URI`
   with `user_video_publish`.
5. Xianyu: official ISV access + `MEITI_XIANYU_DEPLOYMENT_MODE=JUSHITA`.
6. Xiaohongshu: keep handoff until `write_notes` + official publish E2E exists.
7. Image contract is XiaoleAI `/images/generations`. Video remains NOT_VERIFIED.
8. Real E2E is operator-run: `MEITI_PRODUCTION_E2E=true`.
