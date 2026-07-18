---
name: karpathy-guidelines
description: xiaoping 任务执行约束。任何写代码、改文档边界、爬取、做内容包、重构前必须先加载。包装自 multica-ai/andrej-karpathy-skills，适配 ContentCore 盈利与合规场景。
license: MIT
---

# Karpathy Guidelines（xiaoping 包装版）

上游：https://github.com/multica-ai/andrej-karpathy-skills  
来源思想：Andrej Karpathy 对 LLM 编码失控的观察（乱假设、过度工程、乱动无关代码、无验证目标）。

**Tradeoff：** 偏谨慎与可验证，不偏「先写一堆再说」。琐碎单行修改可酌情压缩流程，但**多步任务必须走约束**。

## 何时必须加载

- 用户新开任务 / 「继续」推进多步工作时
- 修改 `RULES` / `TASK` / 内容包 / 爬虫 / 代码前
- review、重构、对接 xiaodian 前

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

- 先写清假设；不确定就问或标 `UNKNOWN`
- 多种解释并列，不静默选一个
- 有更简方案要说出来
- 混淆时停止：点名哪里不清

**xiaoping 补充：**  
盈利路径、平台 ToS、出海法律、SKU 证据不确定时，禁止编造；标 `NEED_XIAODIAN` / `NEED_EVIDENCE` / `BLOCKED`。

## 2. Simplicity First

**Minimum change that solves the problem. Nothing speculative.**

- 不超范围功能
- 不为一次性逻辑造抽象
- 不平行新建 `engine_v2` / 第二套工具链
- 能改现有 `RULES`/`TOOLING`/内容包就不要新系统

## 3. Surgical Changes

**Touch only what you must.**

- 不顺手「优化」无关文件
- 匹配现有风格
- 发现无关死代码只报告不擅自删

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

多步任务开工前写：

```text
CONSTRAINTS_ACTIVE: karpathy-guidelines
GOAL: ...
VERIFY:
1. ...
2. ...
OUT_OF_SCOPE: 真实发布/上架/收款（除非老板 gate）
```

做完按 VERIFY 勾选；不能勾选则不得宣称完成。

## 5. xiaoping 任务启动清单（复制用）

```text
[ ] 已读 RULES.md 边界与 gate
[ ] 已加载本 SKILL（karpathy-guidelines）
[ ] 已声明 GOAL + VERIFY
[ ] 结构问题优先 codebase-memory-mcp
[ ] 网页研究用 CloakBrowser + Scrapy（见 TOOLING.md）
[ ] 内容含盈利假设；出海含合规自检
[ ] 无真实对外动作除非老板明确批准
```

## 完成标准（本技能自身）

- 智能体在任务开始时显式引用本约束
- diff 无范围外大改
- 有可核对的 VERIFY 结果
