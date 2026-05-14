# cases.json Schema

## 顶层结构

```json
{
  "root_title": "需求测试用例",
  "requirement_tag": "profile_show_redesign",
  "cases": []
}
```

## 顶层字段

- `root_title`：脑图根节点标题（必填，非空字符串）
- `requirement_tag`：需求标识（可选，用于生成文件名和标签）
- `cases`：测试用例数组（必填）

## cases[] 结构

每条测试用例结构如下：

```json
{
  "groups": [
    "1.入口跳转模块",
    "1.1 Profile 个人主页入口"
  ],
  "title": "点击形象秀展示区域可正常跳转展馆页",
  "priority": "P0",
  "platform": "客户端",
  "labels": [
    "入口",
    "路由",
    "主态"
  ],
  "preconditions": [
    "用户已登录，背包内至少有 1 个形象秀资产"
  ],
  "steps": [
    {
      "action": "进入 Profile 个人主页",
      "expected": []
    },
    {
      "action": "点击形象秀展示区域",
      "expected": [
        "成功跳转至形象秀展馆页",
        "顶部预览区加载当前佩戴效果"
      ]
    }
  ]
}
```

## 必填字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `groups` | `string[]` | 模块路径数组，用于构建 XMind 树状结构 |
| `title` | `string` | 用例标题，非空字符串 |
| `priority` | `string` | 优先级，必须为 `P0`/`P1`/`P2` 之一 |
| `preconditions` | `string[]` | 前置条件列表（可为空数组） |
| `steps` | `Step[]` | 步骤数组，至少包含 1 个步骤 |

## 可选字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `platform` | `string` | 平台标识：`客户端`/`服务端`/`Web`（或别名 `client`/`server`/`web`） |
| `labels` | `string[]` | 标签数组，自动包裹 `【】` 格式输出到 XMind |

## groups 规则

- `groups` 必须为字符串数组
- 优先表示从 PRD 目录/章节读取并整理后的路径
- 不强制固定长度，通常为 `2-4` 层
- 前几项优先对应 PRD 原始章节
- 最后一项建议落到可直接展开 case 的测试点
- 用例将按 `groups` 顺序归并到相同路径的叶子节点下

## steps 规则

- `steps` 必须为对象数组，且至少包含 1 个元素
- 每个步骤对象必须包含：
  - `action`（`string`）：操作步骤描述，非空
  - `expected`（`string[]`）：预期结果列表（可为空）
- 示例：
  ```json
  {
    "action": "点击保存按钮",
    "expected": ["调用保存接口", "返回成功后更新配置"]
  }
  ```

## priority 规则

必须使用以下固定值之一：

- `P0`：核心流程阻断项，必须 100% 覆盖
- `P1`：重要功能 + 用户体验，高优先级覆盖
- `P2`：边界/兼容/安全场景，抽样覆盖

> 注意：不支持 `P3`，若传入非标准值将自动降级为 `P2`

## platform 规则

支持以下值（大小写不敏感）：

| 输入值 | 标准化输出 |
|--------|-----------|
| `客户端` / `client` | `客户端` |
| `服务端` / `server` | `服务端` |
| `Web` / `web` / `后台` / `管理端` / `后台管理端` | `Web` |

> 若提供非法值，导出时将抛出校验错误

## labels 规则

- `labels` 必须为字符串数组
- 每个标签会自动包裹 `【】` 格式输出到 XMind（如 `入口` → `【入口】`）
- 若标签本身已包含 `【】` 或 `[]`，会自动去重包裹
- 支持平台标签自动识别：`【客户端】`/`【服务端】`/`【Web】`

## XMind 转换约束

转换脚本按以下规则消费 `cases.json`：

1. **根节点**：使用 `root_title` 作为脑图根节点标题
2. **模块树**：使用 `groups` 数组构建层级路径，相同路径的用例归并到同一叶子节点
3. **用例标题**：格式化为 `tc-{priority}: {title}`（如 `tc-P0: 点击形象秀展示区域可正常跳转展馆页`）
4. **用例内容**：
   - 前置条件：格式化为 `pc：{条件文本}` 子节点（多条件时编号 `1、2、3、`）
   - 步骤：每个 `steps[i]` 生成 `步骤 i：{action}` 子节点，`expected` 作为其子节点
5. **标签**：合并 `platform` + `requirement_tag` + `labels`，去重后输出到 XMind 标签区
6. **文件名**：自动推导为 `{requirement_tag}_{root_title}.xmind`（非法字符自动替换为 `_`）

## coverage_manifest.json 映射规则

- `mapped_cases` 字段必须使用**格式化后的用例标题**（即 `tc-{priority}: {title}`）
- 示例：
  ```json
  {
    "features": [
      {
        "name": "入口跳转",
        "applicable": true,
        "reason": "PRD 明确要求双入口路径",
        "mapped_cases": [
          "tc-P0: 点击形象秀展示区域可正常跳转展馆页",
          "tc-P0: 跳转时正确携带用户身份参数"
        ]
      }
    ]
  }
  ```

## 完整示例

```json
{
  "root_title": "形象秀展馆重构测试用例",
  "requirement_tag": "profile_show_redesign",
  "cases": [
    {
      "groups": ["1.入口跳转模块", "1.1 Profile 个人主页入口"],
      "title": "点击形象秀展示区域可正常跳转展馆页",
      "priority": "P0",
      "preconditions": ["用户已登录，背包内至少有 1 个形象秀资产"],
      "steps": [
        {"action": "进入 Profile 个人主页", "expected": []},
        {"action": "点击形象秀展示区域", "expected": ["成功跳转至形象秀展馆页"]}
      ],
      "labels": ["入口", "路由", "主态"]
    }
  ]
}
```

## 校验工具

使用 `validate_coverage_manifest.py` 校验 `cases.json` 与 `coverage_manifest.json` 的映射关系：

```bash
python3 scripts/validate_coverage_manifest.py \
  --payload testcases/profile_show_redesign/cases.json \
  --coverage-manifest testcases/profile_show_redesign/coverage_manifest.json
```

校验通过标准：
- 所有 `applicable: true` 的覆盖项必须映射到至少 1 个存在的用例标题
- 映射的用例标题必须与 `cases.json` 中格式化后的标题完全匹配
- 服务端风险类用例（幂等/并发/重试/回滚）必须映射到 `platform: 服务端` 的用例

> 详见：`references/coverage-manifest-schema.md`
