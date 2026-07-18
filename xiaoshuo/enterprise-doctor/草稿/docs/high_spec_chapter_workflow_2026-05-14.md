# enterprise-doctor 最高规格章节写作流程 2026-05-14

## 0. 冻结与边界

- chapter-001 至 chapter-030：已发布/发布参照，不大改主线。
- chapter-028 至 chapter-030：老板声明已发布；只允许 post_publish_fixes 建议，不直接覆盖线上正文。
- chapter-031 起：进入最高规格重写/扩写流程。

## 1. 每章硬标准

- 正文字数：目标 ≥3500中文字；不足自动 FAIL。
- 前300字：必须有可见事故、冲突或强问题，不慢铺背景。
- 主角动作：林川必须亲自拆局、验证、谈判、设计机制或承担代价。
- 多轮冲突：至少外部压力 → 现场动作 → 反转/加码。
- 爽点：来自可验证动作，如证据链、现场测试、账本、流程、授权、公开验收、数据反杀、规则反用。
- 人物推进：林川有现实压力；配角因事件改变行为；阻力方升级手段。
- 章末钩子：下一章非看不可，优先倒计时、公开验收、损失风险、身份暴露、订单/合同/舆论危机。

## 2. 外部信息要求

涉及市场、平台、竞品、热点、读者反馈、榜单、职业流程、合规表达时，必须调用 `creative-market-research-toolchain`。

输出：`草稿/market_intel/chapter_XXX_external_intel.md`

必须区分：REAL_PUBLIC / BOSS_BACKEND / SIMULATED / UNKNOWN。

## 3. xiaochan Gate

每章必须真实调用 xiaochan profile。

输出：`草稿/quality_gates/chapter_XXX_xiaochan_supplement.md`

必须记录：session_id、核心建议、采纳点、拒绝点、拒绝原因、正文对应位置。

无 xiaochan，不得进入发布候选。

## 4. xiaofa Gate

涉及平台、合同、证照、拍摄授权、实名、食品安全、医疗合规、劳动争议、法务定性时，必须调用或参考 xiaofa gate。

不得把小说桥段写成现实法律结论。

## 5. 每章产物

1. 草稿正文：`草稿/chapters/chapter-XXX_high_spec_draft.md`
2. xiaochan补充：`草稿/quality_gates/chapter_XXX_xiaochan_supplement.md`
3. 外部信息证据：`草稿/market_intel/chapter_XXX_external_intel.md`
4. 质量门：`草稿/quality_gates/chapter_XXX_high_spec_gate.md`
5. 通过后才复制：`发布候选/chapter-XXX.md`

## 6. 发布候选准入

只有同时满足以下条件，才能进入 `发布候选/`：

- 字数≥3500。
- 实质重写/扩写，不灌水。
- xiaochan session_id 与采纳证明存在。
- 必要外部信息证据存在。
- 必要 xiaofa 风险边界存在。
- 不破坏1-30已发布主线。
- 质量门 PASS。
