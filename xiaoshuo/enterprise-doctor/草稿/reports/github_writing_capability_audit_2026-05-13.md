# GitHub 写作能力落地审计报告 2026-05-13

项目：enterprise-doctor
审计时间：2026-05-13
审计原则：只记录可由本地文件/会话/命令证明的事实；不能把“曾经学习过/声称装过”直接算作真实调用。

## 0. 审计范围

工作区：`/root/hermes/company-ai-system/workspaces/xiaoshuo/enterprise-doctor`
已发布来源目录：`release/发布前优化稿_第1-50章_2026-05-09`
当前发布状态：用户声明已发布至第27章，因此第1-27章只允许低风险勘误。

## 1. REAL_USED：真实被当前写作流程调用

1. 小说工程化方法已落地到项目资产，而不是外部仓库直接运行：
   - `CONTEXT.md`
   - `docs/livedoc.md`
   - `wiki/hot.md`
   - `wiki/canon/story-rules.md`
   - `wiki/characters/lin-chuan.md`
   - `wiki/arcs/*`
   - `wiki/foreshadowing/foreshadowing-ledger.md`
   - `wiki/cases/case-ledger.md`
   - `wiki/meta/lint-report-2026-05-09.md`
2. 本轮已实际读取并用于状态复核：
   - `CONTEXT.md`
   - `docs/livedoc.md`
   - `wiki/hot.md`
   - `release/发布前优化稿_第1-50章_2026-05-09/00_章节目录.md`
3. 已有报告证明 2026-05-09 曾把 GitHub 学到的方法转成小说线技能/模板/wiki/LiveDoc：
   - `reports/xiaoshuo_second_stage_skill_asset_landing_2026-05-09.md`

判定：REAL_USED 主要是“方法论已资产化并被流程引用”，不是“外部 GitHub 仓库脚本被直接调用”。

## 2. INSTALLED_ONLY：仓库存在，但未接入流程

本轮在 `enterprise-doctor` 工作区内未发现 `.git` 目录，未发现外部 GitHub 仓库 clone。

判定：暂无可归类为 INSTALLED_ONLY 的外部仓库。若外部仓库安装在工作区之外，本轮没有证据证明其属于 enterprise-doctor 工作区。

## 3. BROKEN：路径/依赖/脚本失效

1. 工作区内未发现写作辅助脚本目录或可执行脚本：
   - 未发现 `scripts/`、`tools/`、`.py`、`.sh` 等写作脚本。
2. 工作区内未发现 prompt 模板文件：
   - 未发现文件名包含 `prompt/template/模板/提示词` 的本地模板。
3. 因为没有可执行脚本/模板入口，不能证明有脚本依赖失效；更准确地说是“缺少可执行接入点”。

判定：BROKEN 不是“仓库坏了”，而是“所谓 GitHub 写作能力没有形成本项目内可执行脚本/模板链路”。

## 4. UNKNOWN：无法证明

1. 最近一次写作是否实际调用外部 GitHub 仓库脚本：无法证明。
   - 最近文件修改集中在 2026-05-09 的 release/wiki/docs/reports。
   - 没有发现脚本运行日志、命令记录、外部仓库路径或工具调用证据。
2. “GitHub 写作能力”的原始仓库名/URL：当前工作区无法证明。
3. 外部仓库是否安装在其他路径：当前审计限定 enterprise-doctor 工作区，无法证明。

## 5. 应接入第28章写作的能力

优先接入这些已落地且低污染能力：
1. `CONTEXT.md`：锁定都市经营轻爽文边界，防止副本/系统/万界化。
2. `docs/livedoc.md` + `wiki/hot.md`：读取最新候选包、角色状态、开放伏笔。
3. `wiki/characters/lin-chuan.md`、`wiki/arcs/*`、`wiki/cases/case-ledger.md`：校验第28章是否承接甜品入楼案，不破坏第1-27章。
4. `fanqie-chapter-quality-gate`：本章 TDD、钩子、爽点、幽默、章末拉力评分。
5. 新增 xiaochan 旁路记录：`quality_gates/chapter_028_xiaochan_gpt55_supplement.md`。

## 6. 先不要用，避免污染主线

1. 任何未能证明来源/用途的外部 GitHub 仓库脚本。
2. 自动改写 1-27 章的批处理脚本。
3. 生成“系统面板/任务奖励/真副本/万界入口”的通用网文 prompt。
4. 把模拟读者反馈伪装成真实平台数据的评分脚本。
5. 未经 xiaofa 审查就处理版权、合同、平台规则边界的内容。

## 7. 结论

- enterprise-doctor 内部没有发现外部 GitHub clone。
- 已落地的是“GitHub 方法论转化后的小说工程资产”：wiki、LiveDoc、章节质检技能与台账。
- 第28章写作应使用这些已资产化材料，不应调用来历不明的外部脚本自动重写已发布主线。
