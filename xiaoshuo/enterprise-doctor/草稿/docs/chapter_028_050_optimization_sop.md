# 第28-50章优化总SOP

canonical目录：`release/发布前优化稿_第1-50章_2026-05-09`
优化输出目录：`release/发布候选_第28-50章_优化版_2026-05-13`

## 0. 冻结边界
- chapter-001.md 至 chapter-027.md 只读冻结，不改正文。
- 只优化 canonical 目录内 chapter-028.md 至 chapter-050.md 的派生副本。
- 不直接覆盖 canonical；所有优化稿写入新目录。

## 1. 每章输入顺序
1. LiveDoc：读取 `docs/livedoc.md`，对齐当前剧情状态、发布候选和风险。
2. Wiki/Canon：读取 `CONTEXT.md`、`wiki/hot.md`、`wiki/canon/story-rules.md`、人物/伏笔/单元案台账。
3. 已发布上下文：读取 chapter-001 至 chapter-027 作为不可破坏设定。
4. 当前底稿：读取 canonical chapter-028 至 chapter-050。

## 2. 章节目标卡
每章先写：
- 本章主冲突
- 本章爽点
- 本章信息增量
- 人物推进
- 结尾钩子
- 与前文关系
- 不能破坏的设定

## 3. Hot/爽点检查
- 开头5秒是否有具体冲突。
- 800-1200字内是否有微反转。
- 林川是否做了具体动作，而不是讲课。
- 章末是否有下一问。
- 学习价值是否通过后果呈现，不说教。

## 4. 反例检查
如果读者弃文，优先按以下原因排查：
- 模板化开头/模板化结尾。
- 经营知识像课堂。
- 爽点结算太弱。
- 章节只推进事件，不推进林川债务/名声/人情压力。
- 与1-27章已发布设定冲突。

## 5. xiaochan补充
- 每章必须真实调用 `xiaochan` profile。
- 记录 session_id、建议、采纳/拒绝项。
- 未有 xiaochan 记录，不得写“可发布PASS”。

## 6. xiaofa边界
涉及合同、证照、平台规则、监管、公开比选、事故责任、催收等章节，调用 `xiaofa` profile 做边界审查。
- xiaofa 只给边界建议，不替代正文判断。
- 未调用 xiaofa，不得给“无风险”结论。

## 7. diff记录
- 每章 quality gate 记录 original_path、optimized_path、修改说明。
- 保留 canonical 原文，不覆盖不可追溯。
- 新目录生成章节目录与合并稿。
