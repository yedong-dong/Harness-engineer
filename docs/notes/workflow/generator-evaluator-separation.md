# Generator / Evaluator 分离

## 改前 vs 改后

```
  改前：自检模式（同一上下文）

    Generator ──→ 自我检查 ──→ 导出

    ⚠ 问题：
      · 同一个 Agent 既当运动员又当裁判
      · 倾向于「自信地赞美自己的平庸作品」
      · 无量化标准，输出「我觉得覆盖得差不多了」


  改后：分离评估（上下文隔离）

    Generator ──→ cases.json
                     │
                     ▼
    Evaluator（独立上下文）── 通过 ✓ ──→ 导出
         │
         └── 不通过 ✗ ──→ regenerate_hint ──→ 回修 ──→ 重新评估


    ✓ 上下文隔离：
      Evaluator 只看到 PRD + cases.json，完全不接触生成过程
      避免 Generator 的「思维惯性」污染评估

    ✓ 量化评分：
      不走「我觉得还行」，5 维度各有明确阈值
      每个 gap 附带可执行的 regenerate_hint

    ✓ 不阻塞：
      最多 3 轮评估，超时标记人工复核，继续导出
```

## 设计理念

```
  灵感来源：GAN（生成对抗网络）中的 Generator + Discriminator
            Anthropic 2025 harness 设计原则

  核心发现：
    让一个 Agent 自我评价 → 它会「自信地赞美自己的平庸作品」
    分离出一个独立 Evaluator → 远比调教自检 Prompt 更有效
    "far more tractable than making a generator critical of its own work"
```

## 上下文隔离示意

```
  Generator 的上下文                Evaluator 的上下文
  ════════════════════            ════════════════════
  · PRD 全文                       · PRD 全文
  · 技术文档（分级过滤）             · cases.json（最终产物）
  · 用户澄清决策                    ▸ 仅此两样，多一行都没有
  · 约束限制
  · SubAgent 生成过程
  · 模块拆分策略
  · ...大量中间上下文

  上下文不互通 ──→ Evaluator 不受 Generator 思维惯性的影响
```
