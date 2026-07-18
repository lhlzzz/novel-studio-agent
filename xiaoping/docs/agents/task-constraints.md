# 任务启动约束（强制）

每次运行 xiaoping 任务（含「继续」）时，智能体必须：

1. 加载 [karpathy-guidelines](../../.claude/skills/karpathy-guidelines/SKILL.md)
2. 遵守根目录 [RULES.md](../../RULES.md) 的 gate 与出海合规
3. 工具优先序：
   - 代码/文档结构 → codebase-memory-mcp（https://github.com/DeusData/codebase-memory-mcp）
   - 公开网页 → CloakBrowser（https://github.com/CloakHQ/CloakBrowser）+ Scrapy（https://github.com/scrapy/scrapy）
4. 输出带 GOAL/VERIFY；未验证不称完成
5. 默认不做真实发布/上架/收款

上游 Karpathy 技能参考：https://github.com/multica-ai/andrej-karpathy-skills
