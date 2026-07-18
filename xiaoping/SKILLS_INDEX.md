# Skills & MCP Index（供 codebase-memory / 人工快查）

> 因默认索引可能排除 `.claude/` 与 `docs/`，本文件放在仓库根，保证可被检索。

## 强制任务约束

| 名称 | 路径 | 上游 |
|------|------|------|
| karpathy-guidelines | `.claude/skills/karpathy-guidelines/SKILL.md` | https://github.com/multica-ai/andrej-karpathy-skills |
| task-constraints | `docs/agents/task-constraints.md` | 本项目 |

## MCP

| 名称 | 用途 | 仓库 |
|------|------|------|
| codebase-memory-mcp | 结构/符号/调用链 | https://github.com/DeusData/codebase-memory-mcp |
| agentmemory | 跨会话偏好（非代码事实） | 已连接 MCP |

## 采集

| 名称 | 用途 | 仓库 |
|------|------|------|
| CloakBrowser | 稳定浏览/渲染 | https://github.com/CloakHQ/CloakBrowser |
| Scrapy | 批量公开页爬取 | https://github.com/scrapy/scrapy |

## 内容与边界真相源

- `RULES.md` — 平台/盈利/出海/gate
- `TOOLING.md` — 工具命令与仓库
- `TASK.md` / `STATE.md` / `NEXT_ACTION.md` — 当前任务
- `reports/tweet-package-01-ai-efficiency-profit.md` — 推文包 01（含 TikTok 出海节）

## 调用顺序（每次任务）

1. 加载 karpathy-guidelines  
2. 读 RULES + NEXT_ACTION  
3. codebase-memory：`search_graph` / `search_code`  
4. 网页：CloakBrowser + Scrapy  
5. 按 VERIFY 验收，无 gate 不发布  
