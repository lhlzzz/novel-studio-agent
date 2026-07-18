# RULES

## Browser research

Codex 已在 2026-05-21 测试确认可通过 Playwright MCP 访问公开网页和番茄小说公开首页，因此本 workspace 不再默认要求 Claude 作为唯一浏览器资料网关。

执行规则：

1. 需要番茄小说、榜单、热门书、评论区、竞品页面或其它公开网页资料时，Codex 可优先使用 Playwright MCP。
2. Chrome DevTools MCP 可作为补充；如 Chrome DevTools MCP 不稳定，优先使用 Playwright MCP。
3. Codex 浏览器调研后必须写入 `RESEARCH.md`，不能只在聊天里口头总结。
4. `RESEARCH.md` 必须包含：查询目标、观察页面/来源、关键结论、对当前章节改造的影响、仍不确定的问题。
5. Codex 不得凭空假设网页、评论、留存率或榜单内容；只能基于浏览器 MCP 实际可见内容、已有资料包或用户/Claude 明确提供的信息。
6. 如果浏览器 MCP 不可用、页面需要登录且无法访问、内容不可见、站点反爬、或资料不足，Codex 必须停下并返回：

```text
BLOCKED: NEED_BROWSER_RESEARCH
原因：当前任务依赖浏览器资料，但 Codex 浏览器 MCP 访问失败或资料不足。
需要 Claude/人工协助：
- 需要查询的页面/问题
- 已经尝试的 MCP 工具
- 失败现象
```

## Novel optimization

1. `enterprise-doctor/正文/chapter-001.md` 到 `chapter-061.md` 全部进入优化范围。
2. 优化目标是提高点开、留存、追读、评论和收藏潜力，不只是补字数。
3. 必须遵守 `enterprise-doctor/最高写作指南.md`。
4. 不得把本书改成真系统、玄幻、万界、快穿或副本流。
5. 旧账本只能做复盘/观察/记录，不派任务、不发奖励、不替主角解决问题。
6. 每轮改稿必须更新 `LOG.md`、`STATE.md`、`NEXT_ACTION.md`。

## New novel final writing workflow

1. 写或改《我欠三百万，修bug续命》前，只强制先读 `写作手法/00_新书最终写作标准_全量全息版.md`。
2. 新读者反馈、用户纠偏或审查结论必须先进入总写作标准，再改正文；反馈台账只做留痕，不再作为第二个必读入口。
3. `我欠三百万，修bug续命/正文/` 只能放可直接复制发布的最终稿；草稿、章节卡、评分和试写过程放草稿区或 `我欠三百万，修bug续命/方向B/`。
4. 学习巅峰榜标杆必须全量全息，覆盖写法、文章推进、世界架构、系统架构、人物工程、商业留存和具体改稿动作；对标卡只在新增对标或版权复核时读取。
5. 正式开书、前两章返修或发布准备前，必须先写/复核四格主线和 100-200 字主线简介；简介说不清这本书看什么，不得继续润色正文。
6. 每章写前必须做章节卡；每章必须新增变量、战利品、代价、系统/世界架构推进和关系变化。
7. 每章按百分制评分，低于 90 分不得进入 `我欠三百万，修bug续命/正文/`；前300字钩子或章末追读低于硬线必须返修。
8. 每轮写作/改稿必须更新 `LOG.md`、`STATE.md`、`NEXT_ACTION.md`，并记录下一章必须承接的规则、关系和情绪。

## External tool reference

1. 外部工具使用以本 workspace 的 `TOOLING.md` 和 `/root/hermes/company-ai-system/tools/external/TOOLING.md` 为准；ComfyUI 仅用于封面、角色概念图、场景图、视觉 moodboard 和封面工作流参考。
2. 使用 ComfyUI 前必须从共享工具区运行 smoke/查官方源码，并把调研结果写入 `RESEARCH.md` 或 `SESSION.md` 明确小节。
3. 发布候选素材必须核对模型来源、素材版权、平台封面规范，并按平台/版权相关规则走 xiaochan + xiaofa。
