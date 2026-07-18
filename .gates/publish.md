# Publish / External Action Gate

## Hard rule

- **输出 ≠ 发布**
- 无老板明确批准：禁止真实登录、发布、私信、上架、报价、收款、投流、账号自动化。
- 机器可执行检查：`python scripts/publish_gate.py check --action publish ...`  
  仅当 DB `publish_gates.status=approved` 时 exit 0。

## Five checks（沿用 xiaoping B 模式）

见 `xiaoping/platform_rules_memory/review-gate-5-checks.md`：

1. AI 感  
2. 营销风险  
3. 承接感  
4. 搬运风险  
5. 内容标注  

CLI 会在 `request` 时对 package markdown 做启发式扫描（非替代人工）。

## Commands

```bash
# 申请（五检不过则保持 locked）
python scripts/publish_gate.py request \
  --action publish --platform xiaohongshu \
  --package-key tweet-package-01-ai-efficiency-profit \
  --package packages/tweet-package-01-ai-efficiency-profit.md

# 老板批准（仅 boss/owner/老板）
python scripts/publish_gate.py approve --gate-key '...' --by boss

# 执行前检查（agent 外部动作前必跑）
python scripts/publish_gate.py check --action publish --package-key tweet-package-01-ai-efficiency-profit

# 自检
python scripts/publish_gate.py selftest
```

## Approval artifacts

- `.gates/approvals/*.request.json`
- `.gates/approvals/*.approved.json`
