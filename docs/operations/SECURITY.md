# ai_video_create 安全指南

本文档描述 ai_video_create 项目的安全特性、配置建议和安全实践。

## 安全特性概览

项目内置了多层安全防护机制，保护本地部署环境的安全。

### 速率限制

**模块：** `backend/app/middleware.py` — `SecurityMiddleware`

- 基于滑动窗口的 IP 级别速率限制
- 默认每分钟每 IP 最大 200 次请求（通过 `rate_limit=200` 配置）
- 超过限制时返回 HTTP 429 状态码和 `Retry-After` 头
- 适用于所有 API 端点

**配置方式：** 修改 `backend/app/main.py` 中的 `rate_limit` 参数：
```python
app.add_middleware(SecurityMiddleware, rate_limit=200)
```

### CORS 配置

**模块：** `backend/app/main.py`

- 默认仅允许来自前端开发服务器的跨域请求
- 允许的源：`http://127.0.0.1:5173` 和 `http://localhost:5173`
- 支持凭证传递（cookies、Authorization 头）
- 允许所有 HTTP 方法和请求头

**注意事项：**
- 如果修改了前端开发端口，需要同步更新 CORS 配置
- 生产环境部署时应限制 `allow_origins` 为实际域名
- 不要在 CORS 配置中使用 `allow_origins=["*"]` 配合 `allow_credentials=True`

### 请求体大小限制

**模块：** `backend/app/middleware.py` — `SecurityMiddleware`

- 默认最大请求体大小：10MB
- 仅对 POST 和 PUT 请求生效
- 超过限制时返回 HTTP 413 状态码
- 防止恶意大请求耗尽服务器资源

**配置方式：** 修改 `SecurityMiddleware` 构造参数：
```python
app.add_middleware(SecurityMiddleware, max_body_size=10 * 1024 * 1024)  # 10MB
```

### 输入清理

**模块：** `backend/app/middleware.py` — `InputSanitizeMiddleware`

- 检查所有请求的查询参数
- 拦截包含危险模式的输入：
  - `<script` — XSS 攻击
  - `javascript:` — 伪协议
  - `onerror=` / `onload=` — 事件处理器注入
  - `eval(` / `exec(` — 代码执行
- 被拦截时返回 HTTP 400 状态码

### SSRF 防护

**模块：** `backend/app/security/url_policy.py`

- 阻止对内网地址的请求（防止 SSRF 攻击）
- 仅允许 `http` 和 `https` 协议
- 检查范围包括：
  - RFC 1918 私有地址段（`10.x.x.x`、`172.16.x.x`、`192.168.x.x`）
  - 回环地址（`127.x.x.x`、`::1`）
  - 链路本地地址（`169.254.x.x`、`fe80::`）
  - IPv6 本地地址（`fc00::/7`）
- DNS 解析后再次检查，防止 DNS 重绑定攻击
- 最大重定向次数限制：3 次

**使用方式：**
```python
from backend.app.security import is_safe_url

if is_safe_url(url):
    # URL 安全，可以访问
    pass
else:
    # URL 被拦截
    pass
```

### 路径遍历防护

**模块：** `backend/app/security/path_safety.py`

- 防止路径遍历攻击（`../../` 等目录跳转）
- 检测并拦截危险路径模式：
  - `..` 目录跳转
  - `~` 家目录展开
  - `${}` 变量展开
  - URL 编码字符（`%XX`）
- 符号链接逃逸检测
- 文件名清理：移除特殊字符，限制长度 255 字符
- 根目录约束：确保访问路径在允许的目录范围内

**使用方式：**
```python
from backend.app.security import PathSafety, validate_asset_path

# 验证资产路径
safe_path = validate_asset_path(relative_path, asset_dir="data/assets")

# 通用路径安全检查
safety = PathSafety(root_dirs=["data/assets"])
validated = safety.validate_path(user_input_path)
```

### 安全响应头

**模块：** `backend/app/middleware.py` — `SecurityMiddleware`

自动添加以下安全响应头：

| 响应头 | 值 | 作用 |
|-------|---|------|
| `X-Content-Type-Options` | `nosniff` | 防止 MIME 类型嗅探 |
| `X-Frame-Options` | `DENY` | 防止页面被嵌入 iframe |
| `X-XSS-Protection` | `1; mode=block` | 浏览器 XSS 过滤 |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | 限制 Referer 信息泄露 |

### 密钥脱敏

**模块：** `backend/app/security/secrets_mask.py`

- 提供日志和输出中的敏感信息脱敏功能
- 防止 API Key、密码等敏感信息意外泄露到日志中

## 安全配置建议

### 开发环境

开发环境默认配置已足够安全：
- 监听地址为 `127.0.0.1`（仅本机可访问）
- CORS 仅允许本地前端端口
- 速率限制为 200 次/分钟

### 生产环境

如果将 ai_video_create 部署到生产环境，需要额外配置：

1. **HTTPS**：在反向代理（Nginx/Caddy）层启用 TLS
2. **CORS 源限制**：将 `allow_origins` 修改为实际域名
3. **速率限制**：根据实际使用情况调整
4. **认证授权**：当前版本无内置认证，需要通过反向代理添加
5. **日志脱敏**：确保生产日志不包含 API Key 等敏感信息

### 环境变量安全

- `.env` 文件已添加到 `.gitignore`，不会被提交到版本控制
- 切勿在代码中硬编码 API Key
- 切勿将 `.env` 文件发送给其他人
- 定期轮换 API Key

### 数据库安全

- SQLite 数据库文件权限应限制为仅应用用户可读写
- 定期备份数据库（参见 [升级指南](UPGRADE.md)）
- 不要在数据库中存储明文密码

## 已知安全限制

当前版本的安全实现为本地部署场景设计，存在以下限制：

1. **无用户认证**：所有 API 端点无需认证即可访问
2. **无 TLS**：开发服务器不支持 HTTPS，需要通过反向代理实现
3. **简单速率限制**：基于内存的滑动窗口，重启后计数器重置
4. **无审计日志**：当前未记录 API 访问日志

这些限制在本地部署场景下可接受，但如需部署到共享环境应额外加固。

## 报告安全漏洞

如果发现安全漏洞，请通过以下方式报告：

- **联系方式：** 项目仓库的 Issue 系统（使用安全标签）
- **响应时间：** 收到报告后 48 小时内确认，严重漏洞 7 天内修复
- **处理流程：**
  1. 确认漏洞影响范围
  2. 开发修复补丁
  3. 发布安全更新
  4. 在 CHANGELOG 中记录修复（不公开漏洞细节直到修复发布）

请不要在公开 Issue 中包含可直接利用的漏洞细节。
