# XMind 输出结构

## 最终交付

阶段 B 最终交付统一为 `.xmind` 文件，而不是 `.xlsx`。

模板文件：

- `assets/testcase_import_template.xmind`

导出脚本：

- `scripts/export_xmind.py`
- `scripts/validate_coverage_manifest.py`

正式导出前**可选**通过 `coverage_manifest.json` 校验（通过 `--coverage-manifest` 参数启用）。

## 节点语义

- **根节点**：仅作为画布标题，内容本身不参与导入业务语义
- **输出文件名**：按 `requirement_tag` + `root_title` 导出为 `<需求标签>_<需求主题>.xmind`；若无法提取 `requirement_tag`，则退化为 `<需求主题>.xmind`
- **分组节点**：表示目录或功能分组，最多支持 0-8 级，由 `groups` 数组构建
- **用例节点**：标题必须格式化为 `tc-<优先级>: <标题>`（如 `tc-P0: 点击形象秀展示区域可正常跳转展馆页`）
- **优先级字段**：仅允许 `P0`、`P1`、`P2`；若未填写或填写非法值，自动按 `P2` 处理
- **platform 字段**：仅允许 `客户端`、`服务端`、`Web`；导出脚本也兼容 `client`、`server`、`web`、`后台`、`管理端` 等别名
- **labels 字段**：用于承载 XMind 多标签，固定顺序为平台标签 → 需求标签 → 额外标签
  - 平台标签：`【客户端】`、`【服务端】`、`【Web】`
  - 需求标签：`【<requirement_tag>】`
  - 额外标签：自动包裹 `【】` 格式（如 `入口` → `【入口】`）
- **前置条件节点**：标题以 `pc：` 开头；多条前置条件在该节点内按 `1、2、3、` 编号
- **步骤节点**：测试用例的普通子节点，标题为 `步骤 i：{action}`
- **预期结果节点**：步骤节点的子节点

## 推荐 JSON 输入结构

`scripts/export_xmind.py` 接收的 JSON 推荐为：

```json
{
  "root_title": "形象秀展馆重构测试用例",
  "requirement_tag": "profile_show_redesign",
  "cases": [
    {
      "groups": ["1.入口跳转模块", "1.1 Profile 个人主页入口"],
      "title": "点击形象秀展示区域可正常跳转展馆页",
      "priority": "P0",
      "platform": "客户端",
      "labels": ["入口", "路由", "主态"],
      "preconditions": ["用户已登录，背包内至少有 1 个形象秀资产"],
      "steps": [
        {
          "action": "进入 Profile 个人主页",
          "expected": []
        },
        {
          "action": "点击形象秀展示区域",
          "expected": ["成功跳转至形象秀展馆页", "顶部预览区加载当前佩戴效果"]
        }
      ]
    }
  ]
}
```

也允许直接传入 `cases` 数组；此时 `root_title` 默认为 `测试用例`，`requirement_tag` 可选。

## 分组规则

- `groups` 优先表示沿 PRD 目录/章节整理后的路径，不要求固定层级
- `groups` 为空时，脚本会自动归入 `未分组的用例`
- 同一路径下的多个用例共享同一组节点
- 默认保留 PRD 章节语义；如章节名过长，可做轻量压缩，但不要打散原章节归属
- 导出前按完整 `groups` 路径逐级升序排序，保证用例顺序稳定

## 标签规则

- 导出脚本会根据 `platform` 自动补平台 label（如 `【客户端】`）
- 导出脚本会根据 `requirement_tag` 自动补需求标签（如 `【profile_show_redesign】`）
- 导出脚本会把 `labels` 中的自定义标签规范为 `【标签】` 形式
- 相同文本的 label 只保留 1 个，并保留首次出现顺序
- case 标题中的旧平台前缀（如 `【客户端】`）会被自动剥离，避免与 `labels` 重复

## 用例标题格式化

导出脚本自动将 `title` + `priority` 格式化为：

```
tc-{priority}: {title}
```

示例：
- 输入：`{"title": "点击保存", "priority": "P0"}`
- 输出标题：`tc-P0: 点击保存`

> 注意：用例标题中的平台前缀（如 `【客户端】点击保存`）会被自动剥离，避免与 labels 重复

## coverage_manifest.json 映射规则

若启用 `--coverage-manifest` 参数，`mapped_cases` 字段必须使用**格式化后的用例标题**：

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

校验规则：
- 所有 `applicable: true` 的覆盖项必须映射到至少 1 个存在的用例标题
- 映射的用例标题必须与 `cases.json` 中格式化后的标题**完全匹配**（含 `tc-Px:` 前缀）
- 服务端风险类用例（幂等/并发/重试/回滚）必须映射到 `platform: 服务端` 的用例，除非 reason 中注明"客户端主验"

## 使用示例

### 1. 仅导出（不校验 coverage）

```bash
python3 scripts/export_xmind.py \
  --input-json testcases/profile_show_redesign/cases.json \
  --output testcases/profile_show_redesign \
  --template assets/testcase_import_template.xmind
```

### 2. 导出 + coverage 校验（推荐）

```bash
# 先校验
python3 scripts/validate_coverage_manifest.py \
  --payload testcases/profile_show_redesign/cases.json \
  --coverage-manifest testcases/profile_show_redesign/coverage_manifest.json \
  --product-module \
  --product-capability "商城购买=common"

# 校验通过后导出
python3 scripts/export_xmind.py \
  --input-json testcases/profile_show_redesign/cases.json \
  --coverage-manifest testcases/profile_show_redesign/coverage_manifest.json \
  --output testcases/profile_show_redesign \
  --template assets/testcase_import_template.xmind \
  --product-module \
  --product-capability "商城购买=common"
```

上面的命令会导出为：

`testcases/profile_show_redesign/profile_show_redesign_形象秀展馆重构测试用例.xmind`

## 文件名推导规则

输出文件名按以下逻辑推导：

1. 优先使用 `requirement_tag` + `root_title` 组合
2. 若 `requirement_tag` 缺失，尝试从 `root_title` 中提取数字版本号（如 `1.04.00`）
3. 非法字符（`\/:*?"<>|`）自动替换为 `_`
4. 连续空格/下划线合并为单个 `_`

示例：
- `requirement_tag: "profile_show_redesign"` + `root_title: "形象秀展馆重构测试用例"` → `profile_show_redesign_形象秀展馆重构测试用例.xmind`
- `root_title: "1.04.00 房间会员测试用例"`（无 requirement_tag）→ `1.04.00_房间会员测试用例.xmind`
