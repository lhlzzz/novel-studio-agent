# meiti Skills Index

## 模型：并行双线，共享 skill 层

```
meiti/
  .agents/skills/   ← 共享（两边都可调用）
  .claude/skills/   ← 指向上面的 symlink
  xiaoping/         ← 分发/变现线（可并行跑）
  xiaoshuo/         ← 长内容线（可并行跑）
```

- **并行**：同一时段可一边写章节、一边打推文包；互不阻塞。
- **共享**：营销/社媒/设计 skill 装在 meiti 根，避免在两边各装一套。
- **专属**：story-*、karpathy-guidelines 仍挂在各自子目录/全局。

## 已安装（meiti 根 · 2026-07-18）

### marketingskills（coreyhaines31）

| Skill | 用途 |
|-------|------|
| `product-marketing` | 产品/受众/定位底座，其它营销 skill 先读它 |
| `copywriting` | 落地页/转化文案 |
| `offers` | 卖点/报价结构 |
| `social` | 社媒内容（该仓内对应 social 名，非 social-content） |

### social-media-skills（blacktwist）

| Skill | 用途 |
|-------|------|
| `social-media-context-sms` | 声音/受众/平台上下文 |
| `content-strategy-sms` | 内容柱与定位 |
| `content-calendar-sms` | 发布节奏 |
| `platform-strategy-sms` | 分平台策略 |
| `post-writer-sms` | 单帖 |
| `thread-writer-sms` | 串帖 |
| `caption-writer-sms` | 视觉向 caption |
| `content-repurposer-sms` | 一稿多形态 |
| `hook-writer-sms` | 钩子 |

### design

| Skill | 用途 |
|-------|------|
| `impeccable` | 设计 audit/polish（组合页/落地页） |

安装路径：`meiti/.agents/skills/<name>/`，Claude 侧：`meiti/.claude/skills/<name>` → symlink。

### 子目录既有

| 名称 | 路径 |
|------|------|
| karpathy-guidelines | `xiaoping/.claude/skills/karpathy-guidelines/` |
| gitnexus-* | `xiaoping/.claude/skills/gitnexus/` |
| story-* | 全局（`/story-long-write` 等，见 xiaoshuo AGENTS） |

## 未装（按需）

| 优先级 | 仓库 | 说明 |
|--------|------|------|
| P2 | Leonxlnx/taste-skill | 前端 anti-slop，与 impeccable 重叠，暂不装 |
| 索引 | awesome-shadcn-ui | 组件列表，不当 skill 装 |
| 参考 | langchain social-media-agent | 人在环编排思路，非 skill 文档 |
| 暂缓 | aaron 120 skills / agency-agents 整仓 | 太大，按任务摘取 |

## 调用顺序

1. meiti `RULES` + 任务所在子目录 RULES  
2. 长内容 → story-*；分发 → karpathy + 上表 sms/marketing skill  
3. 设计页 → `impeccable`  
4. codebase-memory → VERIFY  
5. **无 gate 不发布**
