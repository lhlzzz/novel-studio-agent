# enterprise-doctor 目录语义纠偏 2026-05-14

profile_invoked=true
profile_name=xiaoshuo

## 当前裁决

当前目录整理结果只算 advisor baseline：`ADVISOR_OVERREACH + CANONICAL_BASELINE_ONLY + HIGH_SPEC_REWRITE_REQUIRED`。

## 目录定义

- `正文/`：当前主线基线，用于保持连续性和已发布参照；不等于发布终稿。当前未经逐章最高规格 gate 验证，因此不可整体作为发布目录。
- `草稿/`：修改件、半稿、候选稿、证据、gate、market_intel、post_publish_fixes、基线正文等沉淀区。
- `发布候选/`：新建。仅允许放通过最高规格 gate 的章节。没有 xiaochan、没有外部证据、字数不足3500、质量门未PASS的章节不得进入。

## 28-30 已发布事实

老板声明：chapter-028 至 chapter-030 已发布。后续不再大改主线；如发现明显瑕疵，只能写入 `草稿/post_publish_fixes/`，不直接覆盖线上正文。

## 当前 正文/ 是否可发布

NO。理由：尚未逐章通过最高规格 gate；并且审计发现低于3500字章节：1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47,48,49,50。

## 下一步

从 chapter-031 开始，按最高规格逐章重写/扩写；每章先生成草稿和 gate，PASS 后才复制到 `发布候选/`。
