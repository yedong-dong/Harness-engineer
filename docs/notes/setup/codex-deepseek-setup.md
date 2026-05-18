# Codex + DeepSeek 部署指南

通过 CCX 代理网关让 Codex CLI / Codex App 使用 DeepSeek API，支持 1M 上下文。

## 架构

```
Codex  --/v1/responses-->  CCX (:3000)  --/v1/chat/completions-->  DeepSeek API
```

CCX 负责将 Codex 的 Responses API 协议翻译为 DeepSeek 的 Chat Completions API，自动处理角色映射和模型名映射。

---

## 准备工作

需要你提供两个信息：

| 变量 | 说明 | 示例 |
|------|------|------|
| `DEEPSEEK_API_KEY` | DeepSeek API Key，从 [platform.deepseek.com](https://platform.deepseek.com/api_keys) 获取 | `sk-xxxxxxxx` |
| `PROXY_ACCESS_KEY` | CCX 代理密码，自己设定，用于 Codex 连接 CCX 时认证 | `my-proxy-password` |

---

## 第一步：部署 CCX

确保 Docker 已安装，然后执行：

```bash
docker run -d --name ccx \
  -p 3000:3000 \
  -e PROXY_ACCESS_KEY="<你的PROXY_ACCESS_KEY>" \
  -e ENABLE_WEB_UI=true \
  -e APP_UI_LANGUAGE=zh-CN \
  crpi-i19l8zl0ugidq97v.cn-hangzhou.personal.cr.aliyuncs.com/bene/ccx:latest
```

验证运行状态：

```bash
docker ps --filter name=ccx
# 应该显示 healthy
```

---

## 第二步：配置 CCX 通道

将以下内容中的 `<DEEPSEEK_API_KEY>` 替换为你的真实 API Key，写入 CCX 容器：

```bash
cat <<'EOF' | docker exec -i ccx tee /app/.config/config.json
{
  "upstream": [],
  "responsesUpstream": [
    {
      "baseUrl": "https://api.deepseek.com",
      "apiKeys": ["<DEEPSEEK_API_KEY>"],
      "serviceType": "openai",
      "name": "DeepSeek",
      "priority": 1,
      "status": "active",
      "supportedModels": ["deepseek-v4-pro", "deepseek-v4-flash"],
      "modelMapping": {
        "deepseek-v4-pro[1m]": "deepseek-v4-pro"
      },
      "normalizeNonstandardChatRoles": true,
      "autoBlacklistBalance": true,
      "normalizeMetadataUserId": true
    }
  ],
  "geminiUpstream": [],
  "fuzzyModeEnabled": true,
  "stripBillingHeader": true
}
EOF
```

**配置项说明：**

| 字段 | 说明 |
|------|------|
| `baseUrl` | DeepSeek API 根路径 |
| `apiKeys` | DeepSeek API Key 列表 |
| `serviceType` | 上游协议类型，`openai` 即 Chat Completions |
| `modelMapping` | `deepseek-v4-pro[1m]` → `deepseek-v4-pro`，兼容 Codex 1M 上下文标识 |
| `normalizeNonstandardChatRoles` | 将 `developer` 等非标角色映射为标准角色 |
| `fuzzyModeEnabled` | 模糊模型匹配，未精确匹配时兜底 |

验证 CCX 是否正常：

```bash
curl -s http://localhost:3000/v1/models \
  -H "Authorization: Bearer <PROXY_ACCESS_KEY>"
# 应返回 deepseek-v4-pro 和 deepseek-v4-flash
```

---

## 第三步：设置环境变量

```bash
echo 'export CCX_PROXY_KEY="<你的PROXY_ACCESS_KEY>"' >> ~/.zshrc
source ~/.zshrc
```

---

## 第四步：配置 Codex

编辑 `~/.codex/config.toml`：

```toml
model_provider = "ccx"
model = "deepseek-v4-pro[1m]"
review_model = "deepseek-v4-flash"
model_reasoning_effort = "xhigh"
disable_response_storage = true
network_access = "enabled"
model_context_window = 1000000
model_auto_compact_token_limit = 950000

[model_providers.OpenAI]
name = "OpenAI Proxy"
base_url = "http://47.236.3.167:8080"
wire_api = "responses"
requires_openai_auth = true

[model_providers.deepseek]
name = "DeepSeek via CCX"
base_url = "http://localhost:3000/v1"
env_key = "CCX_PROXY_KEY"
wire_api = "responses"

[model_providers.ccx]
name = "CCX DeepSeek"
base_url = "http://localhost:3000/v1"
wire_api = "responses"
env_key = "CCX_PROXY_KEY"
```

**配置项说明：**

| 字段 | 说明 |
|------|------|
| `model` | `deepseek-v4-pro[1m]`，CCX 自动映射为 `deepseek-v4-pro` |
| `review_model` | 轻量模型，用于代码审查等低负载任务 |
| `model_reasoning_effort` | 推理深度：`low` / `medium` / `high` / `xhigh` |
| `model_context_window` | 上下文窗口，1M tokens |
| `model_auto_compact_token_limit` | 达到此值自动压缩上下文 |
| `wire_api` | Codex 协议，必须为 `responses`（CCX 负责翻译） |
| `env_key` | 从环境变量读取密码，对应 `CCX_PROXY_KEY` |

---

## 第五步：重启 Codex

重启 Codex 客户端即可使用。

---

## 常见问题

### Error: unknown variant `chat_completions`

Codex 只支持 `wire_api = "responses"` 或 `"messages"`，不能直连 DeepSeek。必须走 CCX 代理。

### Error: unknown variant `developer`

CCX 的 `normalizeNonstandardChatRoles` 未启用，设为 `true` 即可。

### Error: model `deepseek-v4-pro[1m]` not found

在 CCX config 中添加 `modelMapping: {"deepseek-v4-pro[1m]": "deepseek-v4-pro"}`。

### 客户端显示上下文不是 1M

Codex 可能从模型元数据覆盖了 `model_context_window`，一般不影响实际使用。可实际测试确认。

---

## 维护命令

```bash
# 查看 CCX 日志
docker logs ccx

# 重启 CCX
docker restart ccx

# 查看容器状态
docker ps --filter name=ccx

# 修改 CCX 配置后自动热加载，无需重启
```

---

## 参考资料

| 链接 | 说明 |
|------|------|
| [awesome-deepseek-agent PR #55](https://github.com/deepseek-ai/awesome-deepseek-agent/pull/55) | DeepSeek 官方整理的 Codex + DeepSeek 集成方案，包含 CCX 两种通道（Responses / Messages）的配置截图和说明 |
| [BenedictKing/ccx](https://github.com/BenedictKing/ccx) | CCX 代理网关源码，支持 Codex、Claude Code、Gemini CLI 等多客户端协议翻译 |
| [DeepSeek Platform](https://platform.deepseek.com/api_keys) | DeepSeek API Key 申请页面 |
| [Codex 配置文档](https://developers.openai.com/codex/config-advanced) | Codex 高级配置参考（自定义模型提供商、wire_api 等） |
