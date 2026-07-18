# meiti ↔ xiaodian 交接协议

状态：生效（内部）  
版本：2026-07-18  
原则：meiti 出内容/钩子/listing 文案侧；xiaodian 出 SKU/供应/履约。无 gate 不发布/上架/收款。

## 1. 固定字段（handoff 包必填）

| 字段 | Owner | 说明 | 空值策略 |
|------|-------|------|----------|
| `package_key` | meiti | 内容包稳定 ID | 必填 |
| `package_path` | meiti | 仓库内 markdown 路径 | 必填 |
| `sku` | xiaodian | 正式 SKU；未定则 `NEED_XIAODIAN` | 禁止 meiti 编造正式编码以外的库存号 |
| `product_name` | meiti 起草 / xiaodian 确认 | 商品名 | — |
| `product_type` | 双方 | `digital` / `physical` / `bundle` | 默认 digital |
| `includes` | meiti | 交付物清单（结构） | — |
| `excludes` | meiti | 明确不包含 | 必填，防过度承诺 |
| `cost_floor` | xiaodian | 底价/成本 | 无证据 → `NEED_EVIDENCE` |
| `list_price_sim` | meiti | 内部模拟价（非正式） | 标注 `SIMULATED` |
| `list_price_official` | xiaodian | 正式标价 | 未批 → `NOT_ALLOWED_YET` |
| `fulfillment` | xiaodian | 交付通道 | 未开 → `NEED_EVIDENCE` |
| `category` | xiaodian | 闲鱼/店内类目 | 人工定类 |
| `platforms_content` | meiti | 内容已适配平台列表 | — |
| `platforms_commerce` | xiaodian | 可上架渠道 | gate 后 |
| `compliance_notes` | 双方 | 违禁/承诺风险 | — |
| `gate_status` | meiti `publish_gates` | locked/requested/approved | 默认 locked |
| `evidence_paths` | 双方 | 证据文件相对路径 | — |

## 2. 文件落点

| 角色 | 路径 |
|------|------|
| meiti 内容包 | `meiti/packages/<package_key>.md` 或 `meiti/xiaoping/reports/...` |
| meiti → xiaodian 交接 JSON | `meiti/packages/<package_key>.handoff.json` |
| xiaodian SKU 草稿 | `xiaodian/sku_digital_*.md` 或后续统一 SKU 表 |
| 证据 | `meiti/evidence/`、`xiaodian/` 证据目录 |

## 3. JSON schema（最小）

```json
{
  "protocol_version": "2026-07-18",
  "package_key": "tweet-package-01-ai-efficiency-profit",
  "package_path": "meiti/xiaoping/reports/tweet-package-01-ai-efficiency-profit.md",
  "sku": "XP-DIGI-AI-TPL-01",
  "product_name": "小商家 AI 效率模板包 v0.1",
  "product_type": "digital",
  "includes": ["高频问题回复草稿表", "信息整理表", "7天内容日历结构"],
  "excludes": ["自动回复", "代运营", "效果承诺", "实物"],
  "cost_floor": "NEED_EVIDENCE",
  "list_price_sim": {"currency": "CNY", "trail": 12.9, "standard": 29, "tag": "SIMULATED"},
  "list_price_official": "NOT_ALLOWED_YET",
  "fulfillment": "NEED_EVIDENCE",
  "category": "NEED_EVIDENCE",
  "platforms_content": ["xiaohongshu", "shipinhao", "douyin", "xianyu", "x", "tiktok"],
  "platforms_commerce": [],
  "compliance_notes": ["INTERNAL_ONLY", "no guarantee language"],
  "gate_status": "locked",
  "evidence_paths": ["meiti/evidence/tweet-package-01/"],
  "meiti_one_liner": "请补交付通道与正式 SKU；内容主稿已在 package_path。",
  "xiaodian_next": ["定交付", "定类目", "上架前复核清单（需 gate）"]
}
```

## 4. 流程

1. meiti 产出 `INTERNAL_ONLY` 内容包 + handoff JSON。  
2. meiti 跑五检 + `publish_gate.py request`（默认仍 locked）。  
3. xiaodian 填 `NEED_*` 字段，不发明无证据底价。  
4. 老板 approve gate 后，xiaodian 才可讨论上架/收款；meiti 才可讨论真实发布。

## 5. 禁止

- meiti 编造库存/底价/已开通支付。  
- xiaodian 改写内容主叙事导致与 package 矛盾且不回写 meiti。  
- 把 handoff 当发布授权。
