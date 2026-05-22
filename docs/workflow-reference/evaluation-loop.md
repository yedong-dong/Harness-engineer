# 评估回修循环

```
  cases.json
      │
      ▼
  ╔═══════════════╗
  ║  Evaluator    ║  ← 独立上下文（PRD + cases.json）
  ║  5 维度评分   ║
  ╚═══╤═══════╤═══╝
      │       │
   通过 ✓   不通过 ✗
      │       │
      │       ▼
      │   regenerate_hint
      │       │
      │       ▼
      │   主 Agent 回修
      │       │
      │       ├─ 按 hint 补充 case
      │       ├─ 合并回 cases.json
      │       └─ 重新提交评估（attempt + 1）
      │              │
      │              ├─ attempt ≤ 3 → 重新评估
      │              └─ attempt > 3 → 标记「人工复核」
      │                                │
      └────────────┬───────────────────┘
                   ▼
                导出
```

## 回修示例

```
  Evaluator 输出：

  {
    "pass": false,
    "attempt": 1,
    "scores": {
      "rule_coverage": {
        "score": 60,
        "pass": false,
        "gaps": ["规则 R3 '并发下单库存扣减' 未覆盖"]
      }
    },
    "regenerate_hint":
      "补充服务端用例：同一权益库存最后1件，2用户同时下单，验证仅1人成功"
  }


  主 Agent 回修：

  · 新增 1 条 P0 服务端 case：并发下单库存幂等验证
  · 合并回 cases.json
  · 重新提交 Evaluator


  第 2 轮评估：

  {
    "pass": true,
    "attempt": 2,
    "scores": {
      "rule_coverage": { "score": 85, "pass": true, "gaps": [] }
    }
  }

  → 进入导出
```

## 评分维度与阈值

```
  维度              权重      阈值      判定依据
  ─────────        ────      ────      ──────────────────────────
  功能覆盖          最高       ≥80%     每个 Feature 至少 1 条 P0/P1
  规则覆盖          高         ≥80%     每条业务规则有验证 case
  边界/异常         中         ≥60%     关键字段边界值 + 并发/幂等
  优先级分布        中         ≥70%     P0 占 15%-40%，无全是 P0/全 P2
  可执行性          低         ≥80%     步骤具体可操作，无模糊词

  ★ 任一维度不通过 → 整批打回
  ★ 不通过的维度给出具体 gap + regenerate_hint
```

## 3 轮超时策略

```
  attempt = 1  →  不通过  →  主 Agent 回修
  attempt = 2  →  不通过  →  主 Agent 回修（加大力度）
  attempt = 3  →  不通过  →  标记「人工复核」
                             ↓
                        不阻塞导出
                        在 workflow.md 中红色标注
                        用户决定是否接受
```
