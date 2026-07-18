# Xiaoping Content Growth Command Center

全社交平台内容增长与变现工作流：选题 → 推文内容包（图+文+音）→ 多平台适配 → 发布前自查 → 可复制变现实验。

> 边界：不只视频号。覆盖小红书、视频号、抖音、快手、公众号等；当前主形态为推文，策略为广撒网。

## Demo

```bash
python self_media_profit_agent.py selftest
python self_media_profit_agent.py package --topic "AI automation prompt kit" --audience "small business owners" --offer digital_product --platform youtube_shorts
```

The CLI uses controlled, evidence-first recommendations and explicitly keeps external publishing disabled by default.

## Workflow

1. Score platform fit for the creator offer and audience (multi-platform).
2. Generate tweet-style package: image plan, captions, audio/TTS notes, titles.
3. Build multi-platform adaptation checklist and stop conditions.
4. Produce a reproduction plan only after the reward threshold is met.

## Validation

```bash
python self_media_profit_agent.py selftest
python scripts/db/migrate.py verify
```

## Limitations

The system helps form and review publishing decisions; it does not promise reach, revenue, or platform approval. Demo content is sample material. Real posts on any platform require explicit boss approval.
