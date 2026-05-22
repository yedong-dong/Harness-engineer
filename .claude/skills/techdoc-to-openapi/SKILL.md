---
name: techdoc-to-openapi
description: 将技术方案（含 proto 定义）转换为 Bruno 可直接打开的 API 集合文件。当用户提到"生成接口文档"、"生成 API"、"导出 API"、"技术方案转接口"、"proto 转 API"时，必须使用本技能。
hooks:
  PostToolUse:
    # 生成 Bruno 文件后 → 校验 YAML 格式，检查缩进/JSON合法性/必填字段
    - matcher: "Write|Edit"
      hooks:
        - type: command
          command: |
            SKILL_DIR="${CLAUDE_SKILL_DIR:-$HOME/.claude/skills/techdoc-to-openapi}"
            for f in "$@"; do
              case "$f" in
                *.yml)
                  python3 "$SKILL_DIR/scripts/hooks/check_bruno_yaml.py" "$f"
                  ;;
              esac
            done
---

# 技术方案 → Bruno API 集合

## 使用方式

1. 用户提供技术方案.md（含 proto 定义）
2. Agent 解析 proto → 推断请求/响应 → 判断 PB 或 HTTP 类型 → **暂停，用户确认**
3. 确认后生成 Bruno opencollection 集合文件，可直接用 Bruno App 打开

### 两阶段流程

```
技术方案.md（含 proto 定义）
     │
     ▼
┌─ 阶段1：解析 proto + 分类 ─────────────────────────────────┐
│  从技术方案中提取所有 service / rpc / message / HTTP 端点    │
│  判断每个接口类型：PB（有 proto service）还是 HTTP（原 http） │
│  推断请求体字段                                              │
│  ★ 展示提取的接口列表 + 分类 → 用户确认                      │
└──────────────────────────────────────────────────────────┘
     │
     ▼
┌─ 阶段2：生成 Bruno 集合 ───────────────────────────────────┐
│  输出到 Api/<版本名>/（Bruno opencollection 格式）           │
│  生成 opencollection.yml / environments / 各Service目录     │
│  PB 请求 URL=pb/ + x-reqcontrol-bin 路由                    │
│  HTTP 请求 URL=实际路径，无 x-reqcontrol-bin                 │
└──────────────────────────────────────────────────────────┘
```

## 接口分类规则

| 类型 | 判断依据 | URL | 环境 | 额外 Header |
|------|---------|-----|------|------------|
| **PB** | 技术方案含 `service XxxSvc { rpc Method(...) }` | `{{baseUrl}}/` | PB routing | `x-reqcontrol-bin: {"service":"ahchat-api","method":"Svc.Method"}` |
| **HTTP** | 技术方案标注"原http接口"或无 proto service | `{{baseUrl}}/<实际路径>` | HTTP interfaces | 无 x-reqcontrol-bin |

## Bruno 输出结构

```
PRD/<App>/<版本>/output/api/
├── opencollection.yml
├── environments/
│   ├── PB routing.yml          ← baseUrl = ahchat.live:8001/sgw/api
│   └── HTTP interfaces.yml     ← baseUrl = hinchat.live:8001/api/ahchat-api
├── <PRD需求名>/
│   ├── folder.yml
│   ├── ServiceName/
│   │   ├── folder.yml
│   │   ├── 接口中文名1.yml
│   │   └── 接口中文名2.yml
└── ...
```

## 文件模板

详见：[references/bruno-template.md](references/bruno-template.md)

## 核心原则

1. **PB 请求统一 URL**：所有 PB 接口 URL 都是 `{{baseUrl}}/`，靠 `x-reqcontrol-bin` 区分路由
2. **HTTP 请求保留路径**：如 `/user/wallet`、`/user/wallet_flows`，不加 x-reqcontrol-bin
3. **空 message → 空 `{}`**：不编造示例值
4. **请求体写所有字段**：有字段的 message，body data 写出所有字段名和类型占位
5. **中文命名文件**：接口文件名用中文，与参考集合风格一致

## 输出位置

- `PRD/<App>/<版本>/output/api/` — 与其他产出（.xmind、深层分析）统一目录
