# OreateAI 集成总结

**完成日期**: 2026-07-07
**项目路径**: `E:\A-服务器维护项目\生图维护\二开\chatgpt2api`

> 当前文件保留为集成过程记录。以现有运行代码为准：当前 Oreate-only 构建只对外暴露 `/v1/models`、`/v1/images/generations`、`/v1/images/edits`、`/v1/video/generations`；旧 chat/search/messages/PPT/PSD 入口已移除并返回 410。

---

## ✅ 已完成的集成工作

### 1. 新增文件

| 文件路径 | 说明 |
|---------|------|
| `services/oreate_backend_api.py` | OreateAI 后端 API 实现（生图/生视频；旧聊天入口已移除） |
| `services/register/oreate_register.py` | OreateAI 自动注册逻辑（Cookie JWT 认证） |
| `services/protocol/openai_v1_video_generations.py` | 视频生成 OpenAI 兼容协议层 |

### 2. 修改文件

**`services/register_service.py`**
- 将所有 `openai_register` 替换为 `oreate_register`
- 线程名改为 `"oreate-register"`
- 支持 OreateAI Cookie JWT 认证方式

**`api/ai.py`**
- 新增 `VideoGenerationRequest` 请求模型
- 新增 `POST /v1/video/generations` 视频生成端点
- 导入 `openai_v1_video_generations` 模块

**`services/model_catalog_service.py`**
- 当前 `/v1/models` 只暴露 OreateAI 图片/视频模型
- 旧聊天模型不再对外暴露

---

## 🔍 通过浏览器 CLI 确认的真实 API 端点

### 认证方式

OreateAI 使用 **HttpOnly Secure Cookie JWT** 认证：

| Cookie | 说明 | 有效期 |
|--------|------|--------|
| `ics_vsid` | 主身份 JWT (含 tenant_id, user_id, type:verified) | ~24小时 |
| `ouss` | OAuth SSO 会话 JWT | ~30天 |

### API 流程

#### 图像/视频生成流程

**步骤 1: 创建会话**
```http
POST /oreate/create/chat
Content-Type: application/json

请求体:
{"type":"aiImage","docId":""}  // 图像生成
{"type":"aiVideo","docId":""}  // 视频生成

响应:
{
  "status": {"code": 0, "msg": "success"},
  "data": {"chatId": "6a92ccc188d4b7613c1e59b2"}
}
```

**步骤 2: SSE 流式生成**
```http
POST /oreate/sse/stream
Content-Type: application/json

请求体:
{"jt":"31$eyJrIj4iOCI0Iix5IkciQEdJRUdFS0..."}  // Base64 + XOR 加密的 JSON

响应:
Content-Type: text/event-stream; charset=utf-8
(SSE 流式返回生成结果)
```

**页面导航**: 创建会话后，页面导航到 `/home/chat/aiImage/{chatId}` 或 `/home/chat/aiVideo/{chatId}`

### 辅助端点

- **用户信息**: `GET /oreate/user/getuserinfo`
- **剩余积分**: `GET /bizapi/point/getrestpoints`
- **模型配置**: `GET /oreate/img/getmodelconfig`
- **聊天列表**: `GET /oreate/memory/getchatlist?pn=1&rn=30&updateTime=0`

---

## ⚠️ 待实现：jt 字段加密

### 问题说明

`POST /oreate/sse/stream` 的请求体包含加密的 `jt` 字段：

```json
{"jt":"31$eyJrIj4iOCI0Iix5IkciQEdJRUdFS0lMSE5OUyJJIkFqIjwiNTw+Ojw6QDxDRkRARyI+IjYzIlEiSlFTT1FPVDIxMzw2OSIzIit5IkYiQD9AIj4iOCJQIklHS09KUExQIi0ibSI/Ilw9T292QThCekByLUZDWi08L2NtdS5vUWBRZjdVdi1bUl4rVG4zKz4zdllXXWgrKm1yKXRccj9sN3lSbmRoSjc+VXBgY1JSckBAczVrLGteM0dLKU4+U2xKa1dpeVN6TlNzc2JkWWR3ZGI4S2A1OGhabGNpN21OUmtnTjh2NzQqcW93aylfdmZHLC8xYEgpNTBoa3NfU2A1YEdleVBpUjg8Wyx2dnB1dmZeMlddR2s+enkqSzwzT0JQdilwck9HU1RJQTlkZVpjMTJ6MmRpWWlrLl45Ujs0OTFQblNdSUwsKS10LHpyQz1baThfTGE3Rm5pY19fXXAxaU8xbDZZX142ai8pb3RBRi..."}
```

### 加密格式分析

- **格式**: `31$<Base64编码>`
- **`31`**: 版本号或密钥标识
- **Base64 内容**: XOR 加密的 JSON 数据（加密方式需进一步分析）

### 实现方案

#### 方案 A: 浏览器自动化（推荐）

使用 Playwright/Selenium 控制真实浏览器：
- 保留 Cookie 认证状态（`ics_vsid` + `ouss`）
- 利用前端的加密逻辑生成 `jt` 字段
- 拦截 SSE 响应获取生成结果

#### 方案 B: 逆向工程 JS 加密

分析 `home.js` 等前端文件：
- 找到 `jt` 字段的加密函数
- 在 Python 中实现相同的加密算法
- 直接调用 `/oreate/sse/stream` 端点

#### 方案 C: 抓包复用（临时方案）

- 手动触发一次生成，抓取完整的 `jt` 请求体
- 分析 `jt` 内容与 prompt 的关系
- 尝试修改 `jt` 中的参数并测试

---

## 📊 新增的 API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/v1/video/generations` | POST | 视频生成（OpenAI 兼容格式） |

### 请求格式

```json
POST /v1/video/generations
Authorization: Bearer {your-api-key}

{
  "prompt": "a cat walking",
  "model": "oreate-video",
  "n": 1,
  "size": "1024x576",
  "duration": 5,
  "response_format": "url"
}
```

---

## 🎯 新增模型列表

### 已移除模型
- 旧聊天模型不再对外暴露，因为对应 chat 接口已返回 410

### 图像模型
- `oreate-image` - 基础图像生成
- `oreate-image-pro` - Pro 级图像生成
- `dalle3` - DALL-E 3 兼容模型

### 视频模型
- `oreate-video` - 基础视频生成
- `oreate-video-pro` - Pro 级视频生成

---

## 📝 下一步工作

1. **实现 `jt` 加密**:
   - 优先尝试方案 A（浏览器自动化）
   - 或逆向分析前端 JS 代码实现加密算法

2. **测试注册功能**:
   - 使用 `oreate_register.py` 批量注册账号
   - 验证 Cookie JWT 认证流程

3. **完善错误处理**:
   - 积分不足的提示
   - 生成失败的重试逻辑
   - Cookie 过期的自动刷新

4. **性能优化**:
   - SSE 流的异步处理
   - 多账号负载均衡
   - 积分余额实时监控

---

## 🛠️ 开发工具使用记录

### agent-browser-cli

安装和使用：
```bash
# 安装 CLI
npm install -g @sleepinsummer/agent-browser-cli

# Chrome 扩展位置
E:\A-服务器维护项目\生图维护\二开\chrome-extension\

# 使用示例
agent-browser-cli tabs
agent-browser-cli open "https://www.oreateai.com/"
agent-browser-cli exec --tab <tabId> "return document.title;"
```

**技能文件**: `skills/agent-browser-cli/SKILL.md`

---

## 📚 参考资料

### 原始项目
- **oreateai2api**: `E:\opencode工作区\open code免费额度分析\改oreateai\oreateai2api`
- **chatgpt2api**: `E:\A-服务器维护项目\生图维护\二开\chatgpt2api`

### 分析文档
- **ANALYSIS.md**: OreateAI 抓包分析结果（原始项目）

---

**集成完成度**: 85%
**待实现功能**: jt 加密算法 + SSE 流式处理
**可用性**: 框架已就绪，需补全加密逻辑后即可使用
