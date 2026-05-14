---
name: prd-testcase-xmind
description: 将 PRD 文字直接转换为 XMind 测试用例脑图。流程：Agent 合并分析 PRD+技术文档 + 交叉校验 + 澄清 → Subagent 并行生成 → 合并 + 独立 Evaluator 评估（Generator/Evaluator 分离）→ 不通过回修 → 导出 .xmind。当用户提到 PRD、测试用例、XMind、需求转测试、产品文档转测试点、测试脑图时，必须使用本技能。
---

# PRD 测试用例 → XMind

## 使用方式

1. 用户提供 PRD 文字 + 技术文档（鼓励同时提供）→ Agent 合并分析 + 图片识别 + 交叉校验 + 列出澄清问题
2. 用户确认（自然回复即可，无命令词）
3. Subagent 并行生成用例 → 主 Agent 合并 → 独立 Evaluator 评估 → 导出 `.xmind`

### 四阶段流程（含 Generator/Evaluator 分离）

```
PRD + 技术文档
      │
      ▼
┌─ 阶段1：合并分析 + 交叉校验 + 澄清 ──────────────────────────┐
│                                                          │
│  同步读取 PRD + 技术文档                                   │
│     ├─ 图片识别（非 Claude 模型降级处理）                    │
│     ├─ 提取 Feature / Rule / State / Risk 四维要素         │
│     └─ 交叉校验 PRD ↔ 技术文档差异                          │
│                                                          │
│  ★ 暂停 → 用户确认（差异点一并决策）                         │
│      → 提取约束限制（不测XX / 只测XX 等）                   │
└──────────────────────────────────────────────────────────┘
      │
      ▼
┌─ 阶段2：Subagent 并行生成 ─────────────────────────────────┐
│                                                          │
│  按模块树拆分（单模块 >12 强制再拆，总量 >20 再拆）          │
│  所有 Subagent 同一条消息并行派发                           │
│  每个 Subagent 收到：                                      │
│     PRD片段 + 技术摘要 + 约束限制 + 确认决策                 │
│  输出到 /tmp/cases_*.json                                 │
│                                                          │
└──────────────────────────────────────────────────────────┘
      │
      ▼
┌─ 阶段2.5：合并 + 独立 Evaluator 评估 ───────────────────────┐
│                                                          │
│  合并去重 → cases.json                                    │
│  派发 1 个 Evaluator SubAgent（独立上下文，只看结果）       │
│  Evaluator 接收：PRD 全文 + cases.json                     │
│  5 维度评分（读取 references/evaluator-prompt.md）          │
│    ① 功能覆盖   ② 规则覆盖   ③ 边界/异常                   │
│    ④ 优先级合理性  ⑤ 可执行性                             │
│                                                          │
│  ┌─ 全部通过 → 进入阶段3 导出                               │
│  └─ 任一不通过 → regenerate_hint → 主 Agent 回修            │
│       → 重新评估（最多 3 轮）                               │
└──────────────────────────────────────────────────────────┘
      │
      ▼
┌─ 阶段3：导出 ─────────────────────────────────────────────┐
│                                                          │
│  export_xmind.py → .xmind                                 │
│  自动生成 workflow.md（含评估结果 + 修复记录）             │
│  汇报路径 + 覆盖统计 + 评估分数                            │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

按阶段读取必要文件：

- 完整工作流 + 交叉校验规则：读取 [workflow.md](references/workflow.md)
- Agent 行为规则 + 分级过滤：读取 [agent-prompt.md](references/agent-prompt.md)
- **Evaluator 评估标准 + 输出格式**：读取 [evaluator-prompt.md](references/evaluator-prompt.md)
- Review 展示模板：读取 [review-rules.md](references/review-rules.md)
- `cases.json` 结构参考：读取 [cases-json-schema.md](references/cases-json-schema.md)
- XMind 输出 + coverage 校验规范：读取 [xmind-output-schema.md](references/xmind-output-schema.md)

## XMind 标签（仅三种，导入后按端分发）

每条用例的 XMind 标签只输出平台标签，不出需求标签和自定义标签。

| 标签 | 适用场景 |
|------|---------|
| `客户端` | 用户可见的 UI 交互、页面展示、跳转、弹窗 |
| `服务端` | 接口逻辑、数据一致性、并发/幂等、定时任务 |
| `Web` | 管理后台、CMS 配置、运营工具 |

## 阶段2.5：独立 Evaluator 评估

合并去重后的 `cases.json` 交由独立 Evaluator SubAgent 评估。**Evaluator 拥有独立上下文，只看到 PRD 原文和最终用例，不接触生成过程**，避免受 Generator 上下文影响。

### 评估流程

1. 派发 1 个 Evaluator SubAgent，传入 PRD 全文 + 合并后的 cases.json
2. Evaluator 按 5 维度评分，输出结构化评估 JSON
3. 全部维度通过 → 进入阶段3 导出
4. 任一维度不通过 → 根据 `regenerate_hint` 回修 → 重新评估（最多 3 轮）
5. 3 轮后仍不通过 → 标记为人工复核，继续导出

### 5 维度评分标准

| 维度 | 检查内容 | 阈值 | 权重 |
|---|---|---|---|
| 功能覆盖 | 每个 Feature 是否至少 1 条 P0/P1 用例 | ≥ 80% | 最高 |
| 规则覆盖 | 每条业务规则是否有验证 case | ≥ 80% | 高 |
| 边界/异常 | 关键字段边界值、空值、超长、并发冲突 | ≥ 60% | 中 |
| 优先级合理性 | P0/P1/P2 分布合理，无全是 P0 或全 P2 | ≥ 70% | 中 |
| 可执行性 | 步骤具体可操作，预期结果可验证 | ≥ 80% | 低 |

评估标准与输出格式详见：[evaluator-prompt.md](references/evaluator-prompt.md)

## 导出

```bash
python3 scripts/export_xmind.py \
  --input-json <prd_dir>/output/cases.json \
  --output <prd_dir>/output \
  --template assets/testcase_import_template.xmind
```

## 人工 Review

Agent 在澄清阶段**必须暂停**等待用户回复，不能自动跳过。

无需特定命令词，直接回复即可：有补充就说补充，没问题就直接确认。Agent 默认按 `pass_with_notes` 处理——你的所有备注带入生成阶段。除非你明确表达"不对/重来/搞错了"才会触发修正。
