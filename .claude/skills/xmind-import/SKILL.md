---
name: xmind-import
description: 将 XMind 测试用例脑图导入到用例管理平台。流程：解析 XMind → 选项目/用例库/目录名 → 分批导入。当用户提到导入 XMind、上传用例、导入用例到平台时触发。
---

# XMind 用例导入

## 使用方式

1. 用户提供 XMind 文件路径（或 Agent 自动找最近的 .xmind）
2. Agent 解析并展示摘要（case 数、模块数、优先级分布）
3. Agent 调 MCP 查可用项目 → 问用户选哪个
4. Agent 查项目下用例库 → 问用户选哪个
5. 用户命名根目录（默认取 XMind 根节点标题）
6. 用户确认后，脚本转换 + 分批 MCP 导入
7. Agent 汇报结果

## 导入流程

```
用户: "导入这个 XMind"

Agent:
  Step 1 — 解析
    python3 .claude/skills/xmind-import/scripts/xmind_to_mcp.py
      <xmind路径> --requirement-name "占位" --dry-run
    → 展示: "43 cases, 6 modules, P0=18 P1=24 P2=1"

  Step 2 — 选项目
    mcp__usecase-system__ListProjects
    → 展示项目列表 → 问"选哪个项目？"

  Step 3 — 选用例库
    mcp__usecase-system__ListLibrariesByProjectID(project_id={选中})
    → 展示用例库列表 → 问"选哪个用例库？"

  Step 4 — 命名目录
    问"用例挂载在哪个目录下？"
    （默认取 XMind 根节点标题）

  Step 5 — 确认
    展示: "即将导入 43 条用例到 {项目} > {用例库} > {目录名}/"
    → 等待用户确认

  Step 6 — 执行
    python3 .claude/skills/xmind-import/scripts/xmind_to_mcp.py
      <xmind> --requirement-name "{目录名}"
    → 输出 /tmp/xmind_import.json

    读 JSON → 按 batch_size=15 分批
    → 逐批调 mcp__usecase-system__ConvertAndSaveLibraryCaseDataset
      node_id={用例库 tree_id, 如 "lib-17"}
      library_id={用例库 id}
      raw={"case_data": [...每批15条...]}

  Step 7 — 汇报
    "导入完成：43 条 → {项目} > {用例库} > {目录名}/"
```

## 关键约定

- **目录管理**：每个需求的用例挂在一级目录下（如 `Achat3.22-女性权益聚合/1. H5页面/1.1 入口`）
- **node_id**：用例库的 tree_id（如 `lib-17`），不是数字节点ID
- **分批**：每批 ≤15 条，防止 payload 过大
- **不修改 XMind**：只读 XMind 文件，不做任何写入
