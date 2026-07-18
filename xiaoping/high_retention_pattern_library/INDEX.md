# high_retention_pattern_library

用途：建立高停留结构数据库，研究用户为什么停留、为什么划走，只服务 B 模式 P1 的样片审查、内容结构验证和模式沉淀。

## 当前阶段

- 阶段名：High Retention Pattern Research v0.1
- 当前对象：06/07 内部样片
- 当前目标：找到高停留、高信任、低风险的内容结构
- 当前边界：先研究、先记录、先验证，禁止优化到商业目标

## 核心研究问题

1. 用户为什么在前 3 秒停留或划走？
2. 用户为什么在前 5 秒继续看或失去兴趣？
3. 用户为什么在前 10 秒建立信任或产生排斥？
4. 哪些结构制造好奇但不制造营销感？
5. 哪些结构增加真人感、信任感并降低平台风险？

## 单条样片固定字段

- `retention_score`
- `drop_point`
- `attention_curve`
- `emotion_curve`
- `trust_curve`
- `hook_strength`
- `curiosity_gap`
- `human_presence`
- `story_density`
- `subtitle_density`
- `editing_density`
- `trust_signal_strength`
- `humanity_score`
- `trust_score`
- `platform_risk_score`

## 时间窗口

每条样片必须拆成：

- 前 3 秒
- 前 5 秒
- 前 10 秒

每个窗口记录：

- 是否停留
- 是否划走
- 是否产生好奇
- 是否产生信任
- 是否产生情绪波动

## 高停留模式候选

当前只允许记录候选，不允许直接下结论。

- 问题钩子
- 反差钩子
- 故事钩子
- 冲突钩子
- 结果前置钩子
- 真实经历钩子

## 评分系统

### humanity_score：真人感评分，0-10

- 真实感
- 自然感
- 生活感
- 表达感
- 人格感

### trust_score：信任感评分，0-10

- 真实性
- 可信度
- 专业度
- 自然度
- 平台安全度

### platform_risk_score：风险评分，0-10

- AI 痕迹
- 营销痕迹
- 承接感
- 搬运风险
- 标注风险

## 禁止边界

- 不研究成交
- 不研究收款
- 不研究引流
- 不研究接单
- 不研究报价
- 不研究转化
- 不把样片审查结论直接升级为发布建议
- 不把结构优化升级为商业承接闭环

## 文件

- `retention-template.md`：单条样片高停留结构记录模板。
- `retention-log.md`：06/07 样片高停留结构记录日志。
