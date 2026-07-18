# 第31-37章快速落正文补验收总报告

- 生成时间：2026-05-15
- 项目：我在破产边缘给老板们当急诊医生
- 范围：正文/chapter-031.md 至 正文/chapter-037.md；第38章只作为第37章后续连续性参照。
- 执行原则：不覆盖正文原文件；补验收文件只落到 草稿/quality_gates、草稿/release、草稿/reports。
- 明确禁令：当前不得宣称“31-37章已发布级 PASS”。本报告是补验收状态，不是终验发布证明。

## 一、章节状态表

| 章节 | 标题 | 正文已存在 | 发布候选已验收 | 草稿补验收中 | 字数 | 当前状态 |
|---|---|---|---|---|---:|---|
| 31 | 第三十一章 烟火气也要办暂住证 | 是 | 是 | 是 | 4928 | KEEP_IN_正文 |
| 32 | 第三十二章 清白不能靠嗓门烤熟 | 是 | 是 | 是 | 4923 | KEEP_IN_正文 |
| 33 | 第三十三章 同批次，最怕不同命 | 是 | 是 | 是 | 4958 | NEED_LIGHT_FIX |
| 34 | 第三十四章 票据会跑，账不会 | 是 | 否 | 是 | 4895 | KEEP_IN_正文 |
| 35 | 第35章 兄弟合伙，最怕只讲义气 | 是 | 否 | 是 | 4128 | KEEP_IN_正文 |
| 36 | 第36章 烤师走了，火候不能跟着走 | 是 | 否 | 是 | 4228 | NEED_LIGHT_FIX |
| 37 | 第37章 探店不是审判，剪辑才是刀 | 是 | 否 | 是 | 3793 | NEED_LIGHT_FIX |

## 二、结论
- KEEP_IN_正文：第031章, 第032章, 第034章, 第035章
- NEED_LIGHT_FIX：第033章, 第036章, 第037章
- NEED_REWRITE：无
- MOVE_TO_DRAFT_REVIEW：无

## 三、三类目录状态区分

- 正文已存在：31-37章均存在于 正文/，但这只代表主线基线存在。
- 发布候选已验收：31-33章存在发布候选文件；34-37章未按本轮补验收口径确认发布候选已验收。
- 草稿补验收中：31-37章均已生成补验收卡与正文快照；第38章已生成关联连续性检查卡。

## 四、文件落点

- 第031章补验收卡：/root/hermes/company-ai-system/workspaces/xiaoshuo/enterprise-doctor/草稿/quality_gates/chapter_031_quick_maintext_acceptance.md
- 第031章正文快照：/root/hermes/company-ai-system/workspaces/xiaoshuo/enterprise-doctor/草稿/release/chapter-031_正文快照_补验收用.md
- 第032章补验收卡：/root/hermes/company-ai-system/workspaces/xiaoshuo/enterprise-doctor/草稿/quality_gates/chapter_032_quick_maintext_acceptance.md
- 第032章正文快照：/root/hermes/company-ai-system/workspaces/xiaoshuo/enterprise-doctor/草稿/release/chapter-032_正文快照_补验收用.md
- 第033章补验收卡：/root/hermes/company-ai-system/workspaces/xiaoshuo/enterprise-doctor/草稿/quality_gates/chapter_033_quick_maintext_acceptance.md
- 第033章正文快照：/root/hermes/company-ai-system/workspaces/xiaoshuo/enterprise-doctor/草稿/release/chapter-033_正文快照_补验收用.md
- 第034章补验收卡：/root/hermes/company-ai-system/workspaces/xiaoshuo/enterprise-doctor/草稿/quality_gates/chapter_034_quick_maintext_acceptance.md
- 第034章正文快照：/root/hermes/company-ai-system/workspaces/xiaoshuo/enterprise-doctor/草稿/release/chapter-034_正文快照_补验收用.md
- 第035章补验收卡：/root/hermes/company-ai-system/workspaces/xiaoshuo/enterprise-doctor/草稿/quality_gates/chapter_035_quick_maintext_acceptance.md
- 第035章正文快照：/root/hermes/company-ai-system/workspaces/xiaoshuo/enterprise-doctor/草稿/release/chapter-035_正文快照_补验收用.md
- 第036章补验收卡：/root/hermes/company-ai-system/workspaces/xiaoshuo/enterprise-doctor/草稿/quality_gates/chapter_036_quick_maintext_acceptance.md
- 第036章正文快照：/root/hermes/company-ai-system/workspaces/xiaoshuo/enterprise-doctor/草稿/release/chapter-036_正文快照_补验收用.md
- 第037章补验收卡：/root/hermes/company-ai-system/workspaces/xiaoshuo/enterprise-doctor/草稿/quality_gates/chapter_037_quick_maintext_acceptance.md
- 第037章正文快照：/root/hermes/company-ai-system/workspaces/xiaoshuo/enterprise-doctor/草稿/release/chapter-037_正文快照_补验收用.md
- 第038章关联检查卡：/root/hermes/company-ai-system/workspaces/xiaoshuo/enterprise-doctor/草稿/quality_gates/chapter_038_related_context_check.md
- JSON状态表：/root/hermes/company-ai-system/workspaces/xiaoshuo/enterprise-doctor/草稿/reports/chapter_031_037_quick_maintext_acceptance_status_2026-05-15.json

## 五、下一步

- 先轻修第033、036、037章的钩子/冲突/章末牵引。
- 第031、032、034、035章可保留在正文，但若要进入发布候选，仍需终验，不可直接标记发布级PASS。
- 若老板要求发布候选包，再从轻修后的文本复制到 发布候选/，并生成终验门卡。