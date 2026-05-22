# Tool Calling 详解：让 AI 能「动手」

## 1. 这是什么

Tool Calling 是让 LLM（大语言模型）不仅能「说话」，还能「调函数」。这是 Agent 能干活的基础——如果 AI 只能生成文本，它就是个聊天机器人；有了 Tool Calling，它才能查数据库、调 API、操作文件。

## 2. 核心原理

### 2.1 它不是 AI 在执行代码

最关键的理解：**Tool Calling 不是 AI 在执行代码，而是 AI 在「说」要调哪个函数、传什么参数**。

```
传统编程：你的代码 → 调用函数 → 得到结果
Tool Calling：你的问题 → AI 说"调这个函数，参数是这些" → 你的代码执行 → 结果告诉 AI → AI 继续回复
```

### 2.2 完整执行流程

```
┌──────────────────────────────────────────────────────────────┐
│                     Tool Calling 全流程                        │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ① 定义工具（Tool Definition）                                │
│     你告诉 AI：「有一个工具叫 search_database，                │
│     参数有 query(必填,string) 和 limit(可选,int,默认10)」     │
│     ↓                                                        │
│  ② 用户提问                                                  │
│     用户：「查一下上周新增用户 Top 5 的渠道」                   │
│     ↓                                                        │
│  ③ AI 决策（Tool Selection）                                  │
│     AI 输出：{ "tool": "search_database",                     │
│                "input": { "query": "上周新增用户按渠道分组",    │
│                           "limit": 5 } }                      │
│     ↓                                                        │
│  ④ 你的代码执行（Tool Execution）                             │
│     你的程序收到这个 JSON，调真正的 search_database 函数      │
│     得到结果：[{"channel":"抖音", "count":1200}, ...]         │
│     ↓                                                        │
│  ⑤ 回传结果（Tool Result → Context）                         │
│     把结果放回对话上下文，AI 看到这个结果                      │
│     ↓                                                        │
│  ⑥ AI 回复用户                                               │
│     「上周新增用户 Top 5 渠道：1.抖音 1200人，2.微信...」      │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 2.3 Tool Definition 的三要素

每个 Tool 必须包含三个关键信息，AI 据此判断是否调用：

```json
{
  "name": "get_user_profile",           // ① 名称：AI 用来标识"我要调这个"
  "description": "根据用户ID查询其个人信息，包括昵称、等级、注册时间。当用户询问某个用户的资料时使用此工具。",  // ② 描述：AI 用来判断"当前场景是否该调这个"
  "parameters": {                       // ③ 参数：AI 用来生成正确的调用参数
    "type": "object",
    "properties": {
      "user_id": {
        "type": "integer",
        "description": "用户唯一ID"
      }
    },
    "required": ["user_id"]
  }
}
```

**关键细节**：`description` 字段是 AI 做决策的核心依据。一个好的 description 要回答三个问题：
- 这个工具做什么？
- 什么场景下使用？
- 参数代表什么意思？

### 2.4 工具选择决策

当你注册了多个 Tool 时，AI 会在每次回复前判断：

```
用户问题
    ↓
AI 分析：这个问题需要调工具吗？
    ├── 不需要 → 直接回复文字
    └── 需要 → 选哪个工具？
              ├── 只调 1 个 → 调哪个？
              └── 需要多个 → 按什么顺序调？
```

不同模型的 Tool Calling 行为差异：

| 特性 | Claude | GPT-4 | Gemini |
|------|--------|-------|--------|
| 并行调用 | 支持（一次返回多个 tool_use） | 支持 | 支持 |
| 强制调用 | 可通过 system prompt 指定 | 支持 tool_choice 参数 | 支持 |
| Tool Selection 稳定性 | 较好，尤其在 Anthropic SDK 中 | 好 | 一般 |

### 2.5 与你已有知识的连接

你在 Claude Code 中用过的每个 Skill、每个 MCP 工具，底层全是 Tool Calling：

```
Claude Code 的 Tool 系统就是 Tool Calling 的完整实现：

你用的 Read 工具：
  name: "Read"
  description: "Reads a file from the local filesystem"
  parameters: { file_path: string, offset?: int, limit?: int }
  execution: Claude Code 的 harness 执行 fs.readFile

你用的 Bash 工具：
  name: "Bash"
  description: "Executes a given bash command"
  parameters: { command: string, description: string }
  execution: Claude Code 的 harness 执行 shell
```

你在 `.mcp.json` 里配置的 `usecase-system` MCP Server——也是一个 Tool Calling 实现：Server 告诉 Claude Code「我有哪些工具」，Claude 需要时调用，Server 执行并返回结果。

## 3. 动手实现：最小 Tool Calling Demo

### 3.1 Python 原生实现（用 Anthropic SDK）

```python
import anthropic

client = anthropic.Anthropic()

# ① 定义工具
tools = [
    {
        "name": "get_weather",
        "description": "获取指定城市的当前天气。当用户询问天气时使用。",
        "input_schema": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "城市名称，如 '北京'、'上海'"
                }
            },
            "required": ["city"]
        }
    }
]

# ② 发消息（带工具定义）
response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=1024,
    tools=tools,
    messages=[
        {"role": "user", "content": "北京今天天气怎么样？"}
    ]
)

# ③ 检查 AI 是否要调工具
for block in response.content:
    if block.type == "tool_use":
        tool_name = block.name
        tool_input = block.input
        print(f"AI 要调: {tool_name}({tool_input})")

        # ④ 执行真正的函数
        if tool_name == "get_weather":
            # 这里是你的真实逻辑——查天气 API
            result = {"city": tool_input["city"], "temp": 25, "weather": "晴"}

            # ⑤ 把结果回传给 AI
            response2 = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1024,
                tools=tools,
                messages=[
                    {"role": "user", "content": "北京今天天气怎么样？"},
                    {"role": "assistant", "content": response.content},   # AI 的 tool_use
                    {"role": "user", "content": [                        # 执行结果
                        {"type": "tool_result", "tool_use_id": block.id, "content": str(result)}
                    ]}
                ]
            )
            print(f"AI 最终回复: {response2.content[0].text}")
```

### 3.2 关键点

1. **Tool Result 必须带 `tool_use_id`**——AI 需要知道这个结果对应哪个调用请求（因为可能并行调了多个工具）
2. **Tool Result 放在 `user` 消息里**——这是 Anthropic API 的约定
3. **同一次对话可以多轮 Tool Calling**——AI 看到第一个工具的结果后，可能又决定调第二个工具

## 4. 练习题

### 题目 1：设计 Tool Definition

你要为测试平台设计一个「查询用例库」的工具。这个工具需要：
- 根据项目名称查该项目下的用例库列表
- 可选过滤：用例库名称关键字
- 返回 JSON 列表

请写出这个 Tool 的完整 Definition（name、description、input_schema）。

---

### 题目 2：理解多轮 Tool Calling

用户问：「对比一下用户A和用户B的充值记录，看看谁更活跃」

你需要哪些工具？AI 会按什么顺序调用它们？画出调用时序。

---

### 题目 3：修复 Tool 定义缺陷

下面是一个有问题的 Tool Definition，找出三个问题：

```json
{
  "name": "run_sql",
  "description": "执行SQL",
  "input_schema": {
    "type": "object",
    "properties": {
      "sql": {"type": "string"}
    }
  }
}
```

---

### 题目 4：实现带错误处理的 Tool Calling

写一个 Python 函数，包装 Tool 调用过程：
- 如果 Tool 执行成功，返回 tool_result
- 如果 Tool 执行失败（例如数据库连接超时），返回错误信息给 AI，让 AI 知道失败了并生成合适的用户回复

---

## 5. 答案

### 答案 1

```json
{
  "name": "list_case_libraries",
  "description": "查询指定项目下的用例库列表。当用户询问某个项目有哪些用例库、或需要选择用例库进行后续操作时使用。可通过关键字过滤用例库名称。",
  "input_schema": {
    "type": "object",
    "properties": {
      "project_name": {
        "type": "string",
        "description": "项目名称，精确匹配，如 'Achat'、'ChaloTalk'"
      },
      "keyword": {
        "type": "string",
        "description": "用例库名称关键字，模糊匹配。可选，不传则返回全部"
      }
    },
    "required": ["project_name"]
  }
}
```

关键设计思路：
- `description` 说明了「是什么」和「什么场景用」——AI 需要这个信息做决策
- `project_name` 是必填的，因为缺少它无法查询
- `keyword` 是可选的，description 中说清楚了不传的默认行为

### 答案 2

需要的工具（假设已有）：
- `get_user_profile(user_id)` — 获取用户信息
- `get_recharge_records(user_id, start_date, end_date)` — 获取充值记录
- `get_login_activity(user_id, start_date, end_date)` — 获取登录活跃度

调用时序：

```
用户：对比用户A和用户B的充值记录，看看谁更活跃

Step 1（并行）：
  ├── get_user_profile("userA")
  └── get_user_profile("userB")

Step 2（并行，拿到两者信息后）：
  ├── get_recharge_records("userA", "近30天")
  ├── get_recharge_records("userB", "近30天")
  ├── get_login_activity("userA", "近30天")
  └── get_login_activity("userB", "近30天")

Step 3：
  AI 汇总所有结果，生成对比分析回复
```

关键理解：Step 1 确认两个用户都存在后，Step 2 的 4 个调用可以并行——因为它们之间没有依赖关系。

### 答案 3

三个问题：

1. **description 太模糊**——「执行SQL」没有说明什么场景使用、可以做什么类型的查询。AI 无法判断什么时候该调用它。应该改为：「在数据库上执行只读 SQL 查询（SELECT），用于回答用户关于业务数据的统计和明细问题。禁止写操作。」

2. **缺少参数约束**——没有说明 SQL 的限制。如果不加限制，AI 可能生成 DELETE/UPDATE。应该加 `description` 到参数说明中。

3. **缺少数据库上下文**——AI 不知道有哪些表、什么字段。应该：
   - 要么在 description 中描述数据库 schema
   - 要么增加 `tables` 参数让 AI 指定要查的表
   - 要么让系统 prompt 提供表结构信息

修正版：

```json
{
  "name": "run_select_query",
  "description": "在项目数据库上执行只读 SQL 查询（SELECT 语句）。当用户需要查询业务统计数据、用户明细、订单记录时使用。数据库包含以下表：users(user_id,name,channel,register_time), orders(order_id,user_id,amount,status,create_time)。禁止任何写操作（INSERT/UPDATE/DELETE/DROP）。",
  "input_schema": {
    "type": "object",
    "properties": {
      "query": {
        "type": "string",
        "description": "要执行的 SELECT 查询语句。只能使用 SELECT，禁止 INSERT/UPDATE/DELETE/DROP/ALTER。建议使用 LIMIT 限制返回行数。"
      }
    },
    "required": ["query"]
  }
}
```

### 答案 4

```python
def execute_tool_with_error_handling(tool_name, tool_input, tool_use_id):
    """
    包装 Tool 执行，处理成功和失败两种情况
    返回 tool_result content block，可以直接放入 messages
    """
    tool_registry = {
        "run_select_query": run_select_query,
        "get_user_profile": get_user_profile,
    }

    func = tool_registry.get(tool_name)
    if not func:
        return {
            "type": "tool_result",
            "tool_use_id": tool_use_id,
            "content": f"错误：未找到工具 '{tool_name}'。可用工具：{list(tool_registry.keys())}",
            "is_error": True
        }

    try:
        result = func(**tool_input)
        return {
            "type": "tool_result",
            "tool_use_id": tool_use_id,
            "content": str(result)
        }
    except TimeoutError:
        return {
            "type": "tool_result",
            "tool_use_id": tool_use_id,
            "content": "数据库查询超时，可能是查询量过大或数据库负载高。建议缩小查询范围或稍后重试。",
            "is_error": True
        }
    except PermissionError:
        return {
            "type": "tool_result",
            "tool_use_id": tool_use_id,
            "content": "权限不足，该操作不被允许。如需执行此类操作，请联系管理员。",
            "is_error": True
        }
    except Exception as e:
        return {
            "type": "tool_result",
            "tool_use_id": tool_use_id,
            "content": f"工具执行失败：{type(e).__name__}: {str(e)}。请检查参数是否正确，或联系技术支持。",
            "is_error": True
        }
```

关键设计考量：
- `is_error: True` 告诉 AI 这是错误结果（Anthropic API 支持这个字段）
- 错误信息应该有可操作性——不只是「失败了」，还要告诉 AI（以及用户）下一步该做什么
- 不同异常类型返回不同建议——超时建议缩小范围，权限问题建议联系管理员
