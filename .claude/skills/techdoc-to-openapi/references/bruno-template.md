# Bruno Collection 模板

## 目录结构

```
PRD/<App>/<版本>/output/api/
├── opencollection.yml
├── environments/
│   ├── PB routing.yml
│   └── HTTP interfaces.yml
├── ServiceName/
│   ├── folder.yml
│   ├── 接口名称.yml
│   └── 接口名称.yml
└── ...
```

## 文件模板

### opencollection.yml

```yaml
opencollection: 1.0.0

info:
  name: <版本名>-API
config:
  proxy:
    inherit: true
    config:
      protocol: http
      hostname: ""
      port: ""
      auth:
        username: ""
        password: ""
      bypassProxy: ""
bundled: false
extensions:
  bruno:
    ignore:
      - node_modules
      - .git
```

### environments/PB routing.yml

```yaml
name: PB routing
variables:
  - name: baseUrl
    value: http://test-api.ahchat.live:8001/sgw/api
```

### environments/HTTP interfaces.yml

```yaml
name: HTTP interfaces
variables:
  - name: baseUrl
    value: http://test-api.hinchat.live:8001/api/ahchat-api
```

### folder.yml

```yaml
info:
  name: <ServiceName>
  type: folder
  seq: <序号>

request:
  auth: inherit
```

### PB 请求文件（.yml）

```yaml
info:
  name: <接口中文名>
  type: http
  seq: <序号>
  tags:
    - <ServiceName>

http:
  method: POST
  url: "{{baseUrl}}/"
  headers:
    - name: x-reqcontrol-bin
      value: '{"service":"ahchat-api","method":"<ServiceName>.<MethodName>"}'
    - name: x-debug-uid
      value: "337303068"
    - name: x-pubpara-bin
      value: "{ }"
    - name: x-nozip
      value: "true"
    - name: Content-Type
      value: application/json
  body:
    type: json
    data: |-
      <JSON 请求体>
  auth: inherit

settings:
  encodeUrl: true
  timeout: 0
  followRedirects: true
```

### HTTP 请求文件（.yml）

与 PB 的区别：
- `url` 为实际路径（如 `/user/wallet`），不是 `pb/`
- **不包含** `x-reqcontrol-bin` header
- 如果是 GET 请求，`method: GET`，无 body

```yaml
info:
  name: <接口中文名>
  type: http
  seq: <序号>
  tags:
    - <ServiceName>

http:
  method: GET
  url: "{{baseUrl}}/user/wallet"
  headers:
    - name: x-debug-uid
      value: "337303068"
    - name: Content-Type
      value: application/json
  auth: inherit

settings:
  encodeUrl: true
  timeout: 0
  followRedirects: true
```

## 生成规则

### 判断 PB vs HTTP

| 条件 | 类型 | URL | 环境 |
|------|------|-----|------|
| 技术方案中定义了 `service` + `rpc` | PB | `{{baseUrl}}/pb/` | PB routing |
| 技术方案中标注为 "原http接口" 或无 proto service 定义 | HTTP | `{{baseUrl}}/<实际路径>` | HTTP interfaces |
| 请求体为空 message `{}` → body data 为 `{}` | - | - | - |
| 请求体有字段 → body data 写出所有字段及类型占位 | - | - | - |

### 序号分配

按 tag 分组，每个 tag 内从 1 开始递增 seq。tag 的排序按技术方案在 PRD 中的出现顺序。
