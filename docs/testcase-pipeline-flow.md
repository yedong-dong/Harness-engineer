# 测试用例生成 Pipeline — 技术概览

## 全链路

```
PRD + 技术文档 + 图片
        │
        ▼
  阶段1：合并分析 + 交叉校验 + 澄清
        │
        ▼
  阶段2：SubAgent 并行生成（Generator）
        │
        ▼
  阶段2.5：独立 Evaluator 评估（Generator/Evaluator 分离）
        │
        ├─ 通过 → 阶段3 导出
        └─ 不通过 → regenerate_hint 回修（最多 3 轮）
        │
        ▼
  阶段3：导出 .xmind → xmind-import 导入平台
```

---

## 阶段1：合并分析 + 交叉校验 + 澄清

```
  PRD 全文 + 技术文档（有则读）
        │
        ├─ 图片识别（UI 原型/流程图/表格）
        │   └─ ⚠ 非 Claude 模型降级标注 URL，不阻塞流程
        │
        ├─ 四维要素提取
        │   Feature · Rule · State · Risk
        │
        └─ 交叉校验：PRD ↔ 技术文档
            └─ 差异点直接列为澄清问题，附带默认假设
        │
        ▼
  ★ 暂停 → 输出澄清问题，等待用户确认
        │
        ├─ 用户确认决策 → 带入后续阶段
        └─ 自动提取约束限制（不测XX / 只测XX）
```

---

## 阶段2：SubAgent 并行生成（Generator）

```
  按模块树拆分（上限：单模块 >12 强制再拆，总量 >20 再拆）
        │
        ├─ SubAgent-1：模块A（预估 8 条）
        ├─ SubAgent-2：模块B（预估 11 条）
        ├─ SubAgent-3：模块C1（预估 9 条）
        ├─ SubAgent-4：模块C2（预估 7 条）
        └─ SubAgent-N：模块N（预估 N 条）

  每个 SubAgent 收到：
    PRD 片段 + 技术摘要 + 约束限制 + 确认决策

  ★ 所有 SubAgent 同一条消息并行派发
  ★ 输出到 /tmp/cases_*.json，互不依赖
```

---

## 阶段2.5：独立 Evaluator 评估（核心创新点）

```
  合并去重 → cases.json
        │
        ▼
  派发 1 个 Evaluator SubAgent
     ★ 独立上下文：只看 PRD + cases.json，不接触生成过程
     ★ 设计理念：Generator 和 Evaluator 分离，避免「自我赞美」
        │
        ▼
  5 维度量化评分
     ├─ ① 功能覆盖 ≥ 80%    每个 Feature 至少 1 条 P0/P1 用例
     ├─ ② 规则覆盖 ≥ 80%    每条业务规则有验证 case
     ├─ ③ 边界/异常 ≥ 60%    关键字段边界值 + 空值 + 并发冲突
     ├─ ④ 优先级分布 ≥ 70%   P0/P1/P2 分布合理，无全是 P0 或全 P2
     └─ ⑤ 可执行性 ≥ 80%    步骤具体可操作，预期结果可验证
        │
        ├─ ★ 全部通过 → 进入导出
        │
        └─ ★ 不通过 → regenerate_hint（精确回修提示）
                  │
                  ├─ 主 Agent 按提示补充 case → 重新评估
                  ├─ 最多 3 轮
                  └─ 3 轮仍不通过 → 标记人工复核，继续导出
```

### Generator/Evaluator 分离对比

```
  改前：自检模式
    Generator → 同一 Agent 自我检查 → 导出
    ⚠ 问题：Agent 倾向于自信地赞美自己的平庸作品

  改后：分离评估
    Generator → Evaluator（独立上下文）→ 通过 → 导出
                          │
                          └─ 不通过 → regenerate_hint → 回修
    ✓ 上下文隔离：Evaluator 不知道 Generator 怎么生成的
    ✓ 量化评分：不走「我感觉还行」
    ✓ 精确回修：每个 gap 附带可执行的 regenerate_hint
```

---

## 阶段3：导出 + 导入平台

```
  export_xmind.py → .xmind
        │
        ├─ 自动生成 workflow.md（评估结果 + 修复记录）
        └─ 汇报：路径 + P0:X/P1:Y/P2:Z + 各维度评分
        │
        ▼
  xmind-import Skill（可选）
        │
        ├─ xmind_to_mcp.py 解析 → 分批
        ├─ Batch 1/2/3/N → ConvertAndSaveLibraryCaseDataset
        └─ 导入用例管理平台
```

---

## 技术架构总结

```
┌─────────────────────────────────────────────────────────┐
│                    技术关键词                              │
│                                                          │
│  · Generator / Evaluator 分离                            │
│    独立 SubAgent 盲评，5 维度量化，上下文隔离              │
│                                                          │
│  · SubAgent 并行协作                                     │
│    同一条消息派发 N 个 SubAgent，互不依赖，并行生成        │
│                                                          │
│  · 负载均衡拆分                                          │
│    单模块 >12 强制拆，总量 >20 再拆，避免 Agent 过载       │
│                                                          │
│  · 端到端自动化                                          │
│    PRD → 分析 → 澄清 → 生成 → 评估 → 导出 → 导入          │
│                                                          │
│  · SOP 固化                                              │
│    全流程规则封装为可复用 SKILL.md，一次定义重复触发       │
│                                                          │
│  · 交叉校验                                              │
│    PRD ↔ 技术文档差异发现，自动列澄清问题 + 默认假设       │
└─────────────────────────────────────────────────────────┘
```

---

## Pipeline 关键指标

| 指标 | 说明 |
|---|---|
| 阶段数 | 4（分析 → 生成 → 评估 → 导出） |
| SubAgent 并行度 | N 模块 = N 个 SubAgent 同一条消息并行派发 |
| 评估维度 | 5 维度量化（功能/规则/边界/优先级/可执行性） |
| 评估回合上限 | 3 轮，超出标记人工复核 |
| 输出格式 | .xmind + workflow.md |
| 导入方式 | xmind-import → MCP 分批导入平台 |
| 拆分策略 | 单模块 >12 拆，总量 >20 强制拆，自动负载均衡 |
