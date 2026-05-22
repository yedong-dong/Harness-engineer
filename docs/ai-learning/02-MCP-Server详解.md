# MCP Server 详解：把系统能力包装成 AI 工具

## 1. 这是什么

MCP（Model Context Protocol）是一个**开放协议**，由 Anthropic 提出，用来标准化「AI 如何连接外部系统」。它的核心思想很简单：

```
没有 MCP 之前：
  每个 AI 应用对接每个外部系统 → 都要单独写适配代码 → 碎片化

有了 MCP 之后：
  AI 应用 ──→ MCP 协议 ──→ MCP Server ──→ 外部系统
  统一协议           统一接口         各自实现
```

**MCP Server 的本质**：一个独立运行的服务，通过标准协议暴露「工具」给 AI 调用。你只需要知道这个 Server 提供了什么工具，不需要知道它背后怎么实现的。

## 2. 你已经在用 MCP

看看你的 `.mcp.json`：

```json
{
  "mcpServers": {
    "usecase-system": {
      "type": "http",
      "url": "http://ucs-api.flattest.net:8080/mcp?token=..."
    }
  }
}
```

这就是一个 MCP Server——它跑在 `ucs-api.flattest.net` 上，通过 HTTP 暴露了用例管理平台的工具（查项目、查用例库、导入用例等）。Claude Code 通过 MCP 协议和它通信，你感受不到中间的交互细节。

## 3. MCP 协议详解

### 3.1 通信层次

```
┌─────────────────────────────────────────────┐
│              AI 应用（Client）                │
│              Claude Code / 你的程序           │
├─────────────────────────────────────────────┤
│           MCP 协议层（标准交互）              │
│   初始化 → 发现工具 → 调用工具 → 返回结果      │
├─────────────────────────────────────────────┤
│           传输层（Transport）                 │
│    stdio / HTTP SSE / Streamable HTTP        │
├─────────────────────────────────────────────┤
│           MCP Server（工具实现）              │
│    你的代码：查数据库、调API、读文件...        │
└─────────────────────────────────────────────┘
```

### 3.2 MCP 的核心交互流程

```
Client                              MCP Server
  │                                      │
  │──── initialize ───────────────────→  │  ① 初始化：告诉 Server 我是谁、支持什么
  │←─── capabilities ────────────────   │     Server 返回自己的能力（支持工具/资源/提示词）
  │                                      │
  │──── tools/list ───────────────────→  │  ② 发现工具：问 Server"你有哪些工具？"
  │←─── [{tool1}, {tool2}, ...] ────    │     返回工具列表（名称+描述+参数schema）
  │                                      │
  │──── tools/call(tool1, params) ────→  │  ③ 调用工具：AI 决定调 tool1
  │←─── {result} ──────────────────     │     Server 执行并返回结果
  │                                      │
  │──── tools/call(tool2, params) ────→  │  ④ 可以继续调更多工具
  │←─── {result} ──────────────────     │
```

### 3.3 传输方式对比

| 传输方式 | 适用场景 | 优点 | 缺点 |
|---------|---------|------|------|
| **stdio** | 本地工具、命令行 | 简单、不需要网络配置 | 只能本机用 |
| **HTTP SSE** | 远程服务、团队共享 | 可被多人/多个 AI 应用共享 | 需要部署和维护 |
| **Streamable HTTP** | 新一代推荐 | 支持流式响应，性能更好 | 较新，生态还在完善 |

你的 `usecase-system` 用的就是 HTTP 方式——这是最常见的企业级部署方式。

### 3.4 MCP 不只是 Tool

MCP Server 可以暴露三种能力：

```
MCP Server 能力
├── Tools（工具）       → AI 可以调用的函数
│   例：create_test_case()、query_project()
│
├── Resources（资源）    → AI 可以读取的数据
│   例：项目的文件列表、数据库 schema 描述
│
└── Prompts（提示词模板）→ 预定义的提示词
    例：「帮我对这个项目的需求生成测试用例」模板
```

## 4. 从零写一个 MCP Server

### 4.1 场景

写一个最简单的 MCP Server，提供一个工具：**根据城市名获取天气**（模拟数据，不接真实 API）。

### 4.2 准备

```bash
# 安装 MCP Python SDK
pip install mcp
```

### 4.3 完整代码

```python
# weather_server.py
import asyncio
from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationCapabilities
from mcp.server.stdio import stdio_server

# ① 创建 Server 实例
server = Server("weather-server")

# ② 注册工具列表
@server.list_tools()
async def handle_list_tools():
    return [
        {
            "name": "get_weather",
            "description": "获取指定城市的当前天气信息。当用户询问某个城市的天气情况时使用此工具。",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "城市名称，如 '北京'、'上海'、'深圳'"
                    }
                },
                "required": ["city"]
            }
        }
    ]

# ③ 注册工具调用处理
@server.call_tool()
async def handle_call_tool(name: str, arguments: dict):
    if name == "get_weather":
        city = arguments["city"]

        # 这里是你的真实逻辑——实际项目中换成真正的天气 API 调用
        weather_data = {
            "北京": {"temp": 28, "weather": "晴", "humidity": "45%", "wind": "北风3级"},
            "上海": {"temp": 26, "weather": "多云", "humidity": "65%", "wind": "东风2级"},
            "深圳": {"temp": 32, "weather": "阵雨", "humidity": "80%", "wind": "南风4级"},
            "成都": {"temp": 24, "weather": "阴", "humidity": "70%", "wind": "无持续风向"},
        }

        if city not in weather_data:
            return {"content": [{"type": "text", "text": f"未找到 {city} 的天气信息。目前支持的城市：{list(weather_data.keys())}"}]}

        w = weather_data[city]
        return {"content": [{"type": "text",
            "text": f"{city}当前天气：{w['weather']}，温度 {w['temp']}°C，湿度 {w['humidity']}，风力 {w['wind']}"
        }]}

    raise ValueError(f"未知工具: {name}")

# ④ 启动 Server
async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationCapabilities(
                sampling={},
                roots={},
            ),
        )

if __name__ == "__main__":
    asyncio.run(main())
```

### 4.4 接入 Claude Code

在你的项目 `.mcp.json` 中加入：

```json
{
  "mcpServers": {
    "weather": {
      "type": "stdio",
      "command": "python",
      "args": ["/path/to/weather_server.py"]
    }
  }
}
```

重启 Claude Code 后，你就可以直接问「北京天气怎么样？」，Claude 会通过你的 MCP Server 获取数据。

### 4.5 更真实的例子：测试平台工具 Server

你已经在用的 `usecase-system` Server 可能提供了类似这些工具：

```python
# 一个测试用例管理 MCP Server 示例

@server.list_tools()
async def handle_list_tools():
    return [
        {
            "name": "list_projects",
            "description": "列出所有可访问的测试项目",
            "inputSchema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },
        {
            "name": "list_case_libraries",
            "description": "列出指定项目下的用例库",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "项目ID"}
                },
                "required": ["project_id"]
            }
        },
        {
            "name": "import_test_cases",
            "description": "将测试用例批量导入到指定的用例库中",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "library_id": {"type": "string", "description": "目标用例库ID"},
                    "cases": {
                        "type": "array",
                        "description": "用例列表，每条包含 title/precondition/steps/expected",
                        "items": {"type": "object"}
                    },
                    "directory_name": {
                        "type": "string",
                        "description": "导入到哪个目录下。如果不指定，导入到根目录"
                    }
                },
                "required": ["library_id", "cases"]
            }
        }
    ]
```

看看这个设计：
- `list_projects` → `list_case_libraries` → `import_test_cases` 形成递进调用链
- 参数名和你在 Skill 中用的概念（library_id, directory_name）一致
- 每个 description 都说明了使用场景

## 5. MCP Server 设计原则

### 5.1 工具粒度

```
太粗：
  do_everything(action, params)  ← AI 不知道能做什么，也难生成正确的参数

刚好：
  create_test_case(title, steps, expected)  ← 单一职责，AI 容易理解和调用

太细：
  set_title(text)                   ← 需要太多步骤才能完成一个任务
  add_step(number, text)
  set_expected(text)
  ...
```

### 5.2 Description 决定一切

AI 是靠工具的 `description` 来判断是否调用的。一个好的 description:

```
✅ 好：
"在指定项目和用例库下创建新的测试用例目录。当用户需要批量导入用例前创建分类目录时使用。如果目录已存在则返回提示。

✅ 差：
"创建目录"
```

### 5.3 幂等性设计

同一个工具调用多次，应该产生稳定的结果：

```python
# ✅ 幂等：同名目录已存在时返回成功（不报错也不重复创建）
def create_directory(name):
    if dir_exists(name):
        return {"status": "ok", "message": f"目录'{name}'已存在，无需重复创建"}
    else:
        create_dir(name)
        return {"status": "ok", "message": f"目录'{name}'创建成功"}

# ❌ 非幂等：第二次调用会报错
def create_directory(name):
    create_dir(name)  # 重复调用抛异常
```

## 6. 与你已有知识的连接

### 你的 `.mcp.json` 就是 MCP Client 配置

当你配置了 `usecase-system` MCP Server 后，Claude Code 启动时会：
1. 通过 HTTP 连接这个 Server
2. 调用 `tools/list` 获取所有可用工具
3. 在你的对话中，当你说「导入用例到平台」时，Claude 会调用对应的 import 工具

### 你的 Skill 中可能要调用 MCP 工具

在 `prd-testcase-xmind` Skill 的末尾，导入阶段就是通过 MCP 工具完成的：

```
Skill 流程：
  Agent 生成 XMind → Evaluator 评估 → 人确认
  → Skill 调用 import_test_cases MCP 工具 → 用例进入平台
```

你已经在用 MCP 了，只是你之前没有自己写过 Server 端。

## 7. 练习题

### 题目 1：设计一个测试平台的 MCP Server 工具集

你要为一个测试用例管理平台设计 MCP Server。平台功能包括：
- 管理项目（CRUD）
- 管理用例库（在项目下 CRUD）
- 管理用例目录（在用例库下 CRUD）
- 导入/导出/查询用例

请列出你会在 `list_tools()` 中暴露的工具清单（名称 + 一句话描述），不超过 10 个工具。

---

### 题目 2：补全 MCP Server 代码

下面是一个不完整的 MCP Server，请补全缺失部分：

```python
@server.call_tool()
async def handle_call_tool(name: str, arguments: dict):
    if name == "search_cases":
        keyword = arguments.get("keyword", "")
        # TODO: 补全——从数据库中搜索标题包含 keyword 的用例
        # 要求：返回前 20 条，格式为 JSON 数组

    elif name == "batch_update_priority":
        case_ids = arguments["case_ids"]
        new_priority = arguments["priority"]
        # TODO: 补全——批量为指定用例更新优先级
        # 要求：更新后返回成功/失败计数

    else:
        raise ValueError(f"未知工具: {name}")
```

---

### 题目 3：排查 MCP 连接问题

你的 `.mcp.json` 配置了一个 MCP Server，但 Claude Code 启动后显示「MCP Server 不可用」。列出至少 5 种可能的原因和排查方法。

---

### 题目 4：设计一个有状态的 MCP Server

很多 MCP Server 是无状态的（每次调用独立），但有时候需要状态。设计一个「测试执行」MCP Server：
- 可以启动一个测试执行会话
- 查询当前执行进度
- 获取某条用例的执行结果
- 终止执行

描述你会在 `tools/list` 中定义哪些工具，以及服务端如何管理会话状态。

---

## 8. 答案

### 答案 1

```python
tools = [
    {"name": "list_projects", "description": "列出所有可访问的测试项目"},
    {"name": "list_case_libraries", "description": "列出指定项目下的用例库列表"},
    {"name": "list_directories", "description": "列出指定用例库下的目录树结构"},
    {"name": "search_cases", "description": "在指定用例库中根据关键字搜索用例，返回标题/步骤/预期"},
    {"name": "create_directory", "description": "在指定用例库下创建新目录，用于分类管理用例"},
    {"name": "import_cases", "description": "将用例批量导入到指定目录下。用例格式：[{title, precondition, steps, expected}]"},
    {"name": "export_cases", "description": "导出指定目录下的全部用例为 JSON 格式"},
    {"name": "delete_directory", "description": "删除指定目录（仅当目录为空时可删除）"},
    {"name": "get_case_detail", "description": "获取单条用例的完整信息，包括历史修改记录"},
]
```

设计考量：
- 不超过 10 个，避免 AI 选择困难
- 每个工具单一职责，名称即含义
- 能完成核心流程：查 → 管理目录 → 导用例 → 查用例

### 答案 2

```python
@server.call_tool()
async def handle_call_tool(name: str, arguments: dict):
    if name == "search_cases":
        keyword = arguments.get("keyword", "")
        # 参数校验
        if not keyword:
            return {"content": [{"type": "text", "text": "错误：keyword 参数不能为空"}]}

        # 实际项目中这里是数据库查询
        results = db.search_cases(keyword=keyword, limit=20)
        return {
            "content": [{"type": "text",
                "text": json.dumps(results, ensure_ascii=False, indent=2)
            }]
        }

    elif name == "batch_update_priority":
        case_ids = arguments["case_ids"]
        new_priority = arguments["priority"]

        # 校验优先级合法
        valid_priorities = ["P0", "P1", "P2"]
        if new_priority not in valid_priorities:
            return {"content": [{"type": "text",
                "text": f"错误：优先级必须是 {valid_priorities} 之一，收到 '{new_priority}'"
            }]}

        # 执行更新
        success_count = 0
        fail_count = 0
        failed_ids = []

        for cid in case_ids:
            try:
                db.update_priority(cid, new_priority)
                success_count += 1
            except Exception as e:
                fail_count += 1
                failed_ids.append(cid)

        return {"content": [{"type": "text",
            "text": f"更新完成：成功 {success_count} 条，失败 {fail_count} 条。"
                    + (f"失败ID：{failed_ids}" if failed_ids else "")
        }]}

    raise ValueError(f"未知工具: {name}")
```

### 答案 3

5 种常见原因和排查方法：

1. **Server 进程未启动**
   - 原因：`command` 路径错误或 Python 依赖未安装
   - 排查：手动运行 `python /path/to/server.py` 看是否报错

2. **传输方式配置错误**
   - 原因：stdio Server 用了 HTTP 配置格式（或反之）
   - 排查：检查 `type: "stdio"` 和 `type: "http"` 的配置参数是否正确

3. **网络不通（HTTP 模式）**
   - 原因：Server URL 不可达、防火墙拦截、Token 过期
   - 排查：`curl http://ucs-api.flattest.net:8080/mcp?token=xxx` 看返回

4. **端口冲突**
   - 原因：本地启动的 Server 端口已被占用
   - 排查：`lsof -i :端口号`

5. **JSON 格式错误**
   - 原因：.mcp.json 语法错误（多余逗号、中文引号等）
   - 排查：用 JSON 校验工具检查，或看 Claude Code 的错误日志

### 答案 4

```python
# 工具定义
tools = [
    {
        "name": "start_test_session",
        "description": "启动一个测试执行会话。传入要执行的用例ID列表和执行环境（staging/production）。返回 session_id 用于后续查询。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "case_ids": {"type": "array", "items": {"type": "string"}},
                "environment": {"type": "string", "enum": ["staging", "production"]}
            },
            "required": ["case_ids", "environment"]
        }
    },
    {
        "name": "get_session_progress",
        "description": "查询测试执行会话的当前进度，包括已完成/总计/通过/失败数",
        "inputSchema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "start_test_session 返回的会话ID"}
            },
            "required": ["session_id"]
        }
    },
    {
        "name": "get_case_result",
        "description": "获取某次执行会话中指定用例的执行详情，包括步骤级的结果和日志",
        "inputSchema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string"},
                "case_id": {"type": "string"}
            },
            "required": ["session_id", "case_id"]
        }
    },
    {
        "name": "stop_test_session",
        "description": "终止正在执行的测试会话",
        "inputSchema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string"}
            },
            "required": ["session_id"]
        }
    }
]

# 服务端状态管理（使用内存字典，生产环境应使用 Redis）
sessions = {}  # session_id → {cases, progress, status}

def start_test_session(case_ids, environment):
    session_id = generate_uuid()
    sessions[session_id] = {
        "case_ids": case_ids,
        "environment": environment,
        "status": "running",  # running / completed / stopped
        "total": len(case_ids),
        "completed": 0,
        "passed": 0,
        "failed": 0,
        "results": {},  # case_id → result_detail
        "start_time": now()
    }
    # 异步开始执行（生产环境可能是分布式任务）
    asyncio.create_task(run_tests(session_id))
    return session_id
```

关键设计：
- 每个会话有独立 ID，状态隔离
- `get_session_progress` 提供聚合视图，`get_case_result` 提供明细
- 异步执行 + 状态查询 → 适合长时间运行的测试任务
- 生产环境状态存储应该用 Redis/数据库 而非内存字典
