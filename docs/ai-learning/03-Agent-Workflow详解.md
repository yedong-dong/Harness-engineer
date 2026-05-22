# Agent Workflow 详解：编排多步骤的智能工作流

## 1. 这是什么

Agent Workflow（Agent 工作流编排）解决一个问题：**一个任务需要多个步骤、涉及多次 Tool Calling、有分支逻辑、需要保存中间状态时，怎么组织？**

单次 Tool Calling 简单：用户问 → AI 调工具 → 回结果 → AI 回答。但真实需求比如「分析一份 PRD → 拆解功能点 → 生成测试用例 → 评估质量 → 不通过回修 → 导出 XMind」——需要 6-8 步、有分支、有循环、有状态。

```
简单对话：    用户 → AI → 回复（一步）
Tool Calling：用户 → AI → 调工具 → 回结果 → AI → 回复（两步）
Agent Workflow：用户 → AI → 计划 → 执行 → 评估 → 决策 → 回修 → ...（多步 + 分支 + 循环）
```

## 2. 核心概念

### 2.1 状态（State）

**Agent 是有状态的**——它需要记住「已经做了什么」「现在在哪一步」「中间结果是什么」。

```
无状态 Agent（每次对话独立）：
  对话1: 「用户A是谁？」→ 查了 → 回答了
  对话2: 「他最近买了什么？」→ AI 说「你说的是谁？」← 忘了

有状态 Agent（跨步骤记忆）：
  对话1: 「分析这份 PRD」→ State.step = "analyzed", State.features = [...]
  对话2: 「生成用例」→ Agent 知道 features 已经有了，直接用 ← 记住了
```

状态的结构化定义（以 LangGraph 为例）：

```python
from typing import TypedDict, List

class AgentState(TypedDict):
    # 用户输入
    messages: List[dict]

    # 工作流进度
    current_step: str          # "parsing" | "generating" | "evaluating" | "exporting"

    # 中间产物
    prd_content: str           # 原始 PRD
    features: List[dict]       # 拆解出的功能点
    test_cases: List[dict]     # 生成的用例
    evaluation_score: float    # 评估分数
    retry_count: int           # 重试次数

    # 最终产物
    xmind_path: str
```

### 2.2 节点（Node）

**每个处理步骤是一个节点**。节点可以是：
- 调用 LLM（分析、生成、评估）
- 执行函数（格式转换、写文件）
- 等待人工输入（确认、审批）

```python
def parse_prd(state: AgentState) -> AgentState:
    """节点1：解析 PRD，提取功能点"""
    response = llm.invoke(f"分析以下PRD，提取所有功能点：{state['prd_content']}")
    state["features"] = parse_features(response)
    state["current_step"] = "parsed"
    return state

def generate_cases(state: AgentState) -> AgentState:
    """节点2：根据功能点生成测试用例"""
    cases = []
    for feature in state["features"]:
        case = llm.invoke(f"为功能点生成测试用例：{feature}")
        cases.append(case)
    state["test_cases"] = cases
    state["current_step"] = "generated"
    return state
```

### 2.3 边（Edge）——普通边和条件边

**普通边**：执行完 A 一定到 B
**条件边**：执行完 A 后根据条件判断去 B 还是 C

```python
# 普通边：解析后一定去生成
workflow.add_edge("parse_prd", "generate_cases")

# 条件边：评估后，分数 ≥ 80 去导出，否则回修
def should_retry(state: AgentState) -> str:
    if state["evaluation_score"] >= 80:
        return "export"           # 通过 → 导出
    elif state["retry_count"] < 3:
        return "regenerate"       # 不通过且未超限 → 回修
    else:
        return "export_with_warning"  # 超过重试上限 → 强制导出+告警

workflow.add_conditional_edges("evaluate", should_retry, {
    "export": "export_xmind",
    "regenerate": "generate_cases",
    "export_with_warning": "export_xmind"
})
```

### 2.4 图（Graph）——把节点和边组合成执行流程

```python
from langgraph.graph import StateGraph

# 创建图
workflow = StateGraph(AgentState)

# 添加节点
workflow.add_node("parse_prd", parse_prd)
workflow.add_node("generate_cases", generate_cases)
workflow.add_node("evaluate", evaluate_cases)
workflow.add_node("export_xmind", export_xmind)

# 添加边
workflow.add_edge("parse_prd", "generate_cases")
workflow.add_edge("generate_cases", "evaluate")
workflow.add_conditional_edges("evaluate", should_retry, {...})

# 设置入口
workflow.set_entry_point("parse_prd")

# 编译成可执行的 App
app = workflow.compile()
```

### 2.5 持久化（Persistence）——断点续跑

Agent 执行到一半，如果进程挂了或需要人工确认，必须能保存当前状态、稍后恢复：

```python
from langgraph.checkpoint.memory import MemorySaver

# 创建持久化存储
checkpointer = MemorySaver()

# 编译时注入 checkpointer
app = workflow.compile(checkpointer=checkpointer)

# 执行时可以指定 thread_id，用于后续恢复
config = {"configurable": {"thread_id": "prd-2024-001"}}

# 第一次执行
result = app.invoke({"prd_content": prd_text}, config)

# 即使进程重启，传入相同 thread_id 即可从上次断点继续
result = app.invoke(None, config)  # 从断点恢复
```

### 2.6 Memory——短期 vs 长期

```
短期记忆（当前 Thread）：
  用途：记住当前任务执行到哪里、中间结果是什么
  存储：存在 State 中，Thread 结束时可能清理
  例：当前这份 PRD 的分析中间结果

长期记忆（跨 Thread）：
  用途：记住用户偏好、历史经验、可复用知识
  存储：存在外部 Store（数据库/文件/向量库），跨 Thread 持久化
  例：用户之前说「充值金额边界值用 P0」——这个偏好下次还要用
```

LangGraph 的 Store API：

```python
# 写入长期记忆
store.put(
    namespace=("user_preferences",),
    key="test_style",
    value={"priority_rule": "充值类边界值一律标P0", "owner": "yechu"}
)

# 跨 Thread 读取长期记忆
prefs = store.get(("user_preferences",), "test_style")
```

## 3. 与你已有知识的深度连接

### 3.1 你的三层泳道架构 = LangGraph 的 Graph 模式

```
你的架构                          LangGraph 概念
─────────────────────────────────────────────
调度层（主Agent）              → Entry Node + 条件边
  任务拆分、派发                  路由逻辑 + SubGraph 调用

执行层（SubAgent池）           → 并行 Node 执行
  并行生成各模块用例              Send API 并行派发

质量层（Evaluator）            → 条件边 + Checkpoint
  独立评分、打回修正              分数判断 → 回修 or 导出
  最多3轮                        retry_count < 3
```

你其实已经用 Agent 模式实现了一个完整的 Workflow，只是：
- 你的实现是「靠 Prompt 驱动」的（主 Agent 在 Prompt 中编排逻辑）
- LangGraph 的实现是「靠代码驱动」的（图结构 + 函数节点）

两种方式各有优势：你的方式灵活、快速迭代；LangGraph 方式更结构化、更适合生产环境的确定性执行。

### 3.2 你的 Fan-out Fan-in = LangGraph 的 Send API

```
你的模式：
  主Agent → 同时派发给 5 个 SubAgent → 等待全部返回 → 合并

LangGraph 的 Send：
  def continue_to_generators(state):
      # 为每个模块创建一个并行任务
      return [Send("generate_module", {"module": m}) for m in state["modules"]]

  workflow.add_edge("plan", "generate_module")  # 会并行执行 N 次
```

### 3.3 你的 Generator-Evaluator 分离 = LangGraph 的条件边 + Checkpoint

```
你的模式：
  Generator → 生成 → Evaluator → 评分 < 80 → 回修 → Generator → ...

LangGraph 的等价：
  workflow.add_edge("generate", "evaluate")
  workflow.add_conditional_edges("evaluate", should_retry, {
      "regenerate": "generate",
      "export": "export"
  })
```

## 4. LangGraph vs Claude Code Agent 的适用场景

| 维度 | LangGraph | Claude Code Agent模式（你的方式） |
|------|-----------|-------------------------------|
| 执行确定性 | 高（图定义即执行路径） | 中（依赖 Prompt 指令正确执行） |
| 灵活性 | 中（改流程要改代码） | 高（改 Prompt 即可） |
| 可调试性 | 高（每个节点可单独测试） | 中（SubAgent 输出是中间文件） |
| 适合场景 | 生产环境、固定流程 | 探索阶段、快速迭代 |
| 学习成本 | 高 | 低 |

**建议**：用 Prompt 模式快速验证想法（你现在已经做得很好了），验证通过后，对于高频、固定的流程，用 LangGraph 实现生产级版本。

## 5. 练习题

### 题目 1：画出状态流转图

用你已有的 prd-testcase-xmind Skill 流程，画出完整的「节点 + 边 + 条件边」图。标注每个节点的输入 State 字段和输出 State 字段。

---

### 题目 2：设计一个 Bug 排查 Agent

你要设计一个 Bug 排查 Agent。流程是：
1. 接收 Bug 描述
2. 查日志（3 个不同系统的日志，可并行）
3. 查数据库（用户信息、订单记录，可并行）
4. 汇总分析 → 如果信息不足以定位根因，返回第 2 步补充查询
5. 输出根因报告

设计这个 Agent 的 State 结构、节点列表、边和条件边。

---

### 题目 3：识别图中的问题

下面是一个 Agent Workflow 的节点定义，有什么问题？

```python
workflow.add_node("fetch_data", fetch_data)
workflow.add_node("analyze", analyze)
workflow.add_node("report", report)

workflow.add_edge("fetch_data", "analyze")
workflow.add_edge("analyze", "report")
workflow.set_entry_point("fetch_data")
# 没有条件边
# 没有持久化
# 没有错误处理
```

---

### 题目 4：设计跨会话 Memory

你的 prd-testcase-xmind Skill 每次处理新 PRD 时，用户可能会重复告诉 Agent 「充值类边界值用P0」「UI文案变更类用例不需要」等偏好。设计一个 Memory 方案，让这些偏好跨会话持久化，不需要用户每次都重复。

---

## 6. 答案

### 答案 1

```
prd-testcase-xmind Agent 状态流转图

                         ┌─────────────────┐
                         │  START           │
                         │ input: prd_text  │
                         └────────┬────────┘
                                  │
                         ┌────────▼────────┐
                         │ ① analyze_prd    │
                         │ 提取功能点        │
                         │ output: features │
                         └────────┬────────┘
                                  │
                    ┌─────────────┼─────────────┐
                    │             │             │
           ┌────────▼───┐ ┌──────▼────┐ ┌──────▼────┐
           │② gen_module1│ │② gen_mod2 │ │② gen_mod3 │  并行生成
           │ cases_1    │ │ cases_2   │ │ cases_3   │
           └────────┬───┘ └──────┬────┘ └──────┬────┘
                    │             │             │
                    └─────────────┼─────────────┘
                                  │
                         ┌────────▼────────┐
                         │ ③ merge_cases   │
                         │ 合并所有用例      │
                         │ output: all_cases│
                         └────────┬────────┘
                                  │
                         ┌────────▼────────┐
                         │ ④ evaluate       │
                         │ 评分+生成修改提示 │
                         │ output: score,   │
                         │   regenerate_hint│
                         └────────┬────────┘
                                  │
                    score ≥ 80?   │   retry_count ≥ 3?
                    ┌─────────────┼─────────────┐
                    │ YES         │ NO          │
           ┌────────▼───┐ ┌──────▼─────────┐  │
           │⑤ export    │ │⑥ regenerate    │  │
           │xmind+json  │ │ 按hint回修      │  │
           └────────┬───┘ │ inc retry_count│  │
                    │     └──────┬─────────┘  │
                    │            │  返回②     │
                    └────────────┼─────────────┘
                                 │
                        ┌────────▼────────┐
                        │  END             │
                        │ output: .xmind   │
                        │ output: cases.json│
                        └─────────────────┘
```

### 答案 2

```python
class BugInvestigationState(TypedDict):
    # 输入
    bug_description: str
    bug_time: str
    affected_user_id: str

    # 中间数据
    logs_app: dict | None          # 应用日志
    logs_gateway: dict | None      # 网关日志
    logs_payment: dict | None      # 支付系统日志
    user_info: dict | None         # 用户信息
    order_records: list | None     # 订单记录

    # 分析结果
    clues: list                    # 发现的线索
    missing_info: list             # 还缺什么信息
    investigation_round: int       # 当前排查轮次

    # 输出
    root_causes: list              # 可能的根因（Top 3）
    report: str

# 节点
nodes = [
    "parse_bug",          # 解析 Bug 描述，提取关键信息
    "fetch_logs",         # 并行查3个系统日志
    "fetch_db",           # 并行查用户+订单数据
    "analyze_clues",      # 汇总分析线索
    "check_completeness", # 条件判断：信息是否足够
    "generate_report"     # 生成根因报告
]

# 边
workflow.add_edge("parse_bug", "fetch_logs")
workflow.add_edge("parse_bug", "fetch_db")      # 并行！
workflow.add_edge("fetch_logs", "analyze_clues")
workflow.add_edge("fetch_db", "analyze_clues")   # 等都完成
workflow.add_edge("analyze_clues", "check_completeness")

# 条件边
def should_continue(state):
    if len(state["missing_info"]) == 0:
        return "report"
    elif state["investigation_round"] < 5:
        return "fetch_more"    # 回到 fetch_logs/fetch_db 补充查询
    else:
        return "report_partial" # 已达上限，部分报告

workflow.add_conditional_edges("check_completeness", should_continue, {
    "report": "generate_report",
    "fetch_more": "fetch_logs",     # 循环回去
    "report_partial": "generate_report"
})
```

### 答案 3

四个主要问题：

1. **没有条件边**：这是一个线性流程（fetch → analyze → report），但真实场景中 analyze 可能发现数据不足，需要回到 fetch_data。缺少条件边意味着 Agent 无法根据中间结果调整路径。

2. **没有持久化**：如果 fetch_data 花了 5 分钟拉数据，analyze 时进程挂了，就丢了所有中间数据。加 Checkpointer 可以在任何节点后恢复。

3. **没有错误处理**：fetch_data 可能因为 API 超时失败、analyze 的 LLM 调用可能被限流。缺少错误处理节点会导致整个工作流中断而无法恢复。应该加 `try/except` 或错误状态标记。

4. **State 设计不完整**：没有体现每个节点的输入输出。应该用 TypedDict 明确定义 State 结构。

### 答案 4

```python
# 长期 Memory 方案

# Store 结构设计
store_structure = {
    # 用户偏好
    ("user", "yechu", "preferences"): {
        "test_style": {
            "priority_rules": [
                "充值类边界值一律标P0",
                "UI文案变更不需要异常分支用例",
                "金额相关用例必须包含并发测试"
            ],
            "default_platform_tags": ["客户端", "服务端"],
            "preferred_output": "xmind"
        }
    },

    # 领域知识（从历史 PRD 中积累）
    ("domain", "payment", "patterns"): {
        "common_scenarios": [
            "充值金额边界：0, 1, max, max+1, 负数",
            "支付渠道回调和轮询的数据一致性",
            "退款的状态流转：申请→审核→处理→到账"
        ]
    },

    # 历史评估反馈（哪些 Prompt 修改后效果好）
    ("skill", "prd-testcase-xmind", "improvements"): {
        "effective_hints": [
            "异常分支至少覆盖3个：网络超时、并发冲突、权限不足"
        ]
    }
}

# 每次处理新 PRD 时的使用方式
def build_skill_context(user_id: str, prd_domain: str) -> str:
    prefs = store.get(("user", user_id, "preferences"), "test_style")
    domain = store.get(("domain", prd_domain, "patterns"), "common_scenarios")
    history = store.get(("skill", "prd-testcase-xmind", "improvements"), "effective_hints")

    return f"""
    【用户偏好】{json.dumps(prefs)}
    【领域知识】{json.dumps(domain)}
    【历史优化建议】{json.dumps(history)}
    """
    # 这个 context 注入到 Prompt 中，Agent 就自动遵循了
```

**在你现有架构中的实现方式**：
你已经有了 `memory/` 文件系统！可以增加一个 `memory/domain_knowledge.md` 存储这类信息，在 Skill 的 SKILL.md 中引用它。
