# Evidence · tweet-package-01-ai-efficiency-profit

状态：内部证据索引（非发布证明）

## 已有

| 证据 | 路径 | 说明 |
|------|------|------|
| 内容主稿 | `meiti/xiaoping/reports/tweet-package-01-ai-efficiency-profit.md` | 图文/音频/平台表/出海节 |
| 五检规则 | `meiti/xiaoping/platform_rules_memory/review-gate-5-checks.md` | 发布前 5 项自查 |
| xiaodian SKU 草稿 | `xiaodian/sku_digital_xp_tpl_01.md` | NEED_EVIDENCE 字段 |
| handoff JSON | `meiti/packages/tweet-package-01-ai-efficiency-profit.handoff.json` | 交接协议实例 |
| meiti 包索引 | `meiti/packages/tweet-package-01-ai-efficiency-profit.md` | 根入口 |
| selftest 代理 | `meiti/xiaoping/self_media_profit_agent.py selftest` | 不登录不发布 |

## 刻意缺失（诚实）

- 真实平台后台截图 / 已发布 URL：无（gate locked）
- 真实成交/收款记录：无
- 终稿配图二进制：无（主稿为制作说明级）

## 如何追加证据

1. 文件放入本目录，命名 `YYYY-MM-DD-主题.ext`。  
2. 更新本 README 表格。  
3. 需要可检索时：`python scripts/embeddings.py ingest --file ... --key-prefix tweet-package-01-evidence`。  
4. 仍不自动等于发布授权。
