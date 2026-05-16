# buildwithclaude 插件市场完整解析

> 仓库：github.com/davepoon/buildwithclaude | 2900+ stars | MIT

---

## 一、整体架构

```
buildwithclaude/
└── plugins/
    ├── agents-*/agents/*.md          ← 117 个专业 Agent
    ├── commands-*/commands/*.md      ← 175 个斜杠命令
    ├── hooks-*/hooks/*.md            ← 28 个自动化钩子
    ├── all-agents/                   ← 一键安装全量 Agent
    ├── all-commands/                 ← 一键安装全量命令
    ├── all-hooks/                    ← 一键安装全量 Hook
    ├── all-skills/                   ← 一键安装全量 Skill
    ├── msapps-*/                     ← 50 个独立插件包
    └── *.claude-plugin/              ← 每个插件的元数据
```

---

## 二、四种扩展类型对比

```
┌──────────┬──────────────────────┬──────────────────────┬──────────────────────┐
│          │ Agent                │ Command              │ Hook                 │
├──────────┼──────────────────────┼──────────────────────┼──────────────────────┤
│ 触发方式  │ @agent-name          │ /command-name        │ 事件自动触发          │
│ 上下文    │ 独立上下文窗口        │ 当前对话内执行         │ 不可见（后台运行）     │
│ 用途      │ 专业领域专家          │ 快捷操作封装           │ 自动化规则            │
│ 允许工具   │ 由定义指定            │ 由 allowed-tools 限制  │ Bash 脚本            │
│ 安装位置  │ ~/.claude/agents/    │ ~/.claude/commands/   │ settings.json hooks  │
│ 类比      │ 你 SubAgent 的 Prompt │ shell alias           │ 你 SKILL.md 的 hooks │
└──────────┴──────────────────────┴──────────────────────┴──────────────────────┘
```

### 第四种：Skill

你已经很熟了——`SKILL.md` 定义行为 + 可选的 hooks。buildwithclaude 里的 26 个 Skills 本质和你写的 `prd-testcase-xmind` 是同一个东西。

---

## 三、Agent 解析

### 目录结构

```
plugins/agents-development-architecture/
├── .claude-plugin/          ← 插件元数据
└── agents/
    ├── backend-architect.md
    ├── frontend-developer.md
    ├── graphql-architect.md
    ├── ios-developer.md
    ├── nextjs-app-router-developer.md
    └── ...
```

### 文件格式

```yaml
---
name: frontend-developer
description: Build Next.js apps with React, shadcn/ui, Tailwind...
category: development-architecture
---

# 正文：System Prompt

## 角色定义
你是一个 XX 专家...

## 调用规则
PROACTIVELY use for Next.js development...

## 技术规范
- 技术栈版本要求
- 推荐的库/工具
- 禁止的做法

## 工作流程
1. 分析项目
2. 检查版本
3. 生成代码
...

## 输出标准
- TypeScript
- shadcn/ui
- 可访问性
- 响应式
...
```

### Agent 分类（11 大类）

| 类别 | 内容 |
|---|---|
| development-architecture | 前后端架构、GraphQL、Next.js、React |
| language-specialists | 各语言专家（Python/Go/Rust 等） |
| quality-security | 安全审计、代码审查 |
| infrastructure-operations | DevOps、CI/CD |
| data-ai | 数据工程、ML |
| crypto-blockchain | 区块链、Web3 |
| business-finance | 商业分析 |
| design-experience | UX/UI 设计 |
| sales-marketing | 营销内容 |
| specialized-domains | 垂直领域 |
| uc-taskmanager | 任务管理 |

### 对你的学习价值

Agent 的本质是**一个精心编写的 System Prompt + 允许的工具列表**。你的 SubAgent 派发模板已经有这个雏形了——模块专属 Prompt 片段。buildwithclaude 的 Agent 写法值得学的：

- **角色定义要具体到技术栈版本**（不是「前端专家」，而是「Next.js 14+ App Router + shadcn/ui 专家」）
- **Checklist 式规范**（不是「注意性能」，而是「用 next/image / next/font / Suspense / PPR」）
- **输出标准明确**（不是「代码写好」，而是「TypeScript + shadcn/ui + a11y + 响应式」）

---

## 四、Command 解析

### 目录结构

```
plugins/commands-version-control-git/
├── .claude-plugin/
└── commands/
    ├── commit.md
    ├── create-pr.md
    ├── fix-issue.md
    ├── pr-review.md
    ├── bug-fix.md
    └── ...
```

### 文件格式

```yaml
---
description: Create well-formatted git commits with conventional commit messages
category: version-control-git
allowed-tools: Bash, Read, Glob
---

# 正文：操作说明

## 用法
/commit

## 执行步骤
1. 检查包管理器 → 运行 lint/build
2. git status 看暂存区
3. 空暂存区 → 自动 git add
4. git diff 分析改动
5. 多逻辑改动 → 建议拆分提交
6. 生成 emoji + conventional commit message

## 提交规范
- feat: ✨ 新功能
- fix: 🐛 修复
- ...
```

### Command 分类（22 大类）

| 类别 | 示例 |
|---|---|
| version-control-git | `/commit`、`/create-pr`、`/fix-issue` |
| code-analysis-testing | `/lint`、`/test`、`/coverage` |
| documentation-changelogs | `/docs`、`/changelog` |
| CI-deployment | `/deploy`、`/release` |
| project-task-management | `/tdd`、`/plan` |
| workflow-orchestration | `/workflow` |
| monitoring-observability | `/monitor` |
| security-audit | `/audit` |
| 其他 14 类... | |

### 对你的学习价值

Command 把你的常用操作封装成了一条 `/` 命令。你已有的可转化点：

| 你现在做的 | 可以封装成 |
|---|---|
| PRD → XMind 全流程 | `/gen-testcase` |
| XMind → 平台导入 | `/import-xmind` |
| 清空 /tmp/cases_*.json | `/clean-cases` |

比 SKILL.md 更轻量：Command 是**操作封装**，Skill 是**流程编排**。

---

## 五、Hook 解析

### 目录结构

```
plugins/hooks-git/
├── .claude-plugin/
└── hooks/
    ├── auto-git-add.md
    ├── git-add-changes.md
    └── smart-commit.md
```

### 文件格式

```yaml
---
name: auto-git-add
description: Automatically stage modified files after editing
category: git
event: PostToolUse         ← 哪个生命周期事件触发
matcher: Edit|MultiEdit|Write  ← 匹配哪些工具
language: bash             ← 脚本语言
version: 1.0.0
---
```

### Hook 分类

| 类别 | 触发时机 | 例子 |
|---|---|---|
| git | PostToolUse | 写完文件自动 git add |
| notifications | Stop | 会话结束发通知 |
| security | PreToolUse | 拦截危险命令 |
| formatting | PostToolUse | 写代码后自动格式化 |
| testing | PostToolUse | 代码变更后自动跑测试 |
| development | UserPromptSubmit | 自动注入项目上下文 |
| automation | 多种 | 自定义工作流触发 |
| safety | PreToolUse | 敏感操作确认 |

### 对你的学习价值

Hooks 是 buildwithclaude 里你**最应该学**的部分。你的 SKILL.md 目前没有用 hooks：

```yaml
# 你的 prd-testcase-xmind 头部
---
name: prd-testcase-xmind
description: ...
# ❌ 没有 hooks 段
---

# planning-with-files 有：
hooks:
  UserPromptSubmit: [...]
  PreToolUse: [...]
  PostToolUse: [...]
  Stop: [...]
```

你可以为自己的 Skill 加的 hook：

```
事件               能做什么
──────────        ──────────
PostToolUse       写完 /tmp/cases_*.json 后自动校验 JSON 格式
PostToolUse       导出 .xmind 后提醒是否导入平台
Stop              会话结束前检查是否有未导出的 cases
PreToolUse        派发 SubAgent 前自动注入约束条件
```

---

## 六、你已掌握 vs 可扩展

```
已掌握                 可扩展
═══════               ════════
Skill (SKILL.md)      Agent（独立专家 SubAgent Prompt）
CLAUDE.md             Command（斜杠命令操作封装）
SubAgent 并行          Hook（事件驱动自动化）
memory 持久化          Plugin Marketplace（发布给团队复用）
```

---

## 七、值得深入看的插件

| 插件 | 为什么值得看 |
|---|---|
| `claude-code-audit-stack` | 安全审计 Agent 实战 |
| `frontend-design-pro` | UI 设计质量的 Generator/Evaluator |
| `commands-workflow-orchestration` | 工作流编排 Command 写法 |
| `hooks-automation` | Hook 的完整实现参考 |
| `agent-triforce` | 多 Agent 协作模式 |
| `claude-ops` | 运维自动化完整方案 |
| `encode-toolkit` | 编码工具链集成 |

---

## 八、总结：你的学习路线

```
入门（已做）          进阶（立即可做）          高级（长期目标）
──────────          ──────────────          ──────────────
SKILL.md 封装       加 Hook 到现有 Skill      发布插 Plugin Marketplace
SubAgent 并行       写 Command 快捷命令       三 Agent（生成+评估+修复）
memory 记忆体系      写领域 Agent 模板          社区贡献
```

你当前的 `prd-testcase-xmind` + `xmind-import` + Evaluator 架构，按 buildwithclaude 的标准，已经是一个**完整的插件包**了。缺的只是一个 `.claude-plugin/` 元数据目录和一个 Plugin Marketplace 发布动作。
