# OreateAI 二开部署说明

本项目为 **oreate2api / OreateAI 2API**：自动注册（YYDS Mail 邮箱）、邀请裂变积分、生图、生视频走 OreateAI 真实接口，并对外保留有限的 OpenAI 风格接口。

## 一、认证方式

OreateAI 用 **Cookie JWT** 认证（非 Bearer Token）：
- `ouss`：OAuth SSO 会话 JWT（~30 天），**主凭据，单独即可通过认证**
- `ics_vsid`：身份 JWT（~24h），平台访问部分接口时动态换取（HttpOnly，注册阶段通常只拿到 ouss）

账号入库时保存 `ouss`（+ `ics_vsid` 若有），`access_token` 字段 = `ics_vsid or ouss`。

## 二、注册流程（已端到端验证）

```
1. YYDS Mail 创建邮箱   POST https://maliapi.215.im/v1/accounts  (Bearer api_key)
2. 获取 ticket+公钥      GET  /passport/api/getticket           → {ticketID, pk(RSA)}
3. RSA-PKCS1v15 加密密码
4. 提交注册             POST /passport/api/emailsignupin        {email,ticketID,password[,inviteCode]}
5. 轮询邮箱取验证链接    邮件正文含 ?tokenID={UUID}
6. 确认验证（关键）      POST /passport/api/emailregisterconfirm
                        {email,tokenID,ticketID(新),password(新pk加密),plat,[fr,inviteCode]}
                        → set-cookie ouss/ics_vsid, isLogin:true
```

**要点**：
- confirm 必须用**独立的新 ticket**（不能复用 signupin 的），密码用新 pk 重新加密
- 密码规则：8-16 位，含数字+字母+特殊符号（仅 `@#$%^&*`，不含 `!`）
- **邮箱域名**：`007.hzeg.eu.org` 收不到 OreateAI 验证邮件，务必用 `100811.xyz` 等其它 YYDS 域名

## 三、邀请裂变（已接入号池，已验证双方各 +100）

**核心**：邀请绑定发生在 **`emailregisterconfirm`** 步骤，必须带 `fr=inviteFriend` + `inviteCode`。
仅在 `emailsignupin` 传 inviteCode **不生效**（这是最初失败的原因）。

- `data/register.json` → `invite_enabled: true` 开启
- `invite_daily_limit`: 每个收集号每天可当邀请人的次数（平台规则=1）
- 号池 worker 自动：选一个当天有额度的老号 → 取其邀请码 → 新号带码注册 → 双方 +100
- 限额 key 用账号 email（邀请码带时间戳每次变，不能做 key）
- 收集号判据：正常状态 + 有 ouss/ics_vsid 认证态

实测：邀请人积分 50→150，邀请历史 total=1；被邀请人 50→150。

## 四、生图（已验证产出真实 URL）

```
POST /oreate/create/chat  {type:aiImage}          → chatId
POST /oreate/sse/stream   {chatId,chatType:aiImage,messages:[{role,content,attachments}],imageConfig:{modelName,ratio,resolution}}
SSE data: {event:start|error|end}, 图片 URL 在流中
```

模型（真实 modelName 见 IMAGE_MODEL_NAME_MAP）：
- Nano Banana / Nano Banana 2 / Nano Banana Pro
- GPT Image 2.0 / 1.5（**GPT Image 2.0 1K = 1 积分，最便宜**）
- Seedream 5.0 Lite / 4.5 / 4.0
- Kling3.0 Omini / Kling O1 Image

比例：16:9/1:1/2:3/3:2/3:4/4:3/4:5/5:4/9:16/21:9　分辨率：1K/2K/4K

## 五、生视频

同生图，`chatType:aiVideo` + `videoConfig:{modelName,ratio,resolution,duration}`。
模型：Seedance 2.0/2.0 Fast/2.0 Mini/1.5 Pro、Kling 3.0/3.0 Omni/2.6/2.5/o1、Veo 3.1/3、Pixverse V5、Wan 2.5/2.6/2.7。时长 5/10s。

## 六、已知限制

- **水印**：免费号生成的图/视频带水印，去水印是 VIP 付费功能（`removeWatermark` → 升级弹窗），无参数可绕过。
- **每日额度**：无独立签到 API；daily/bonus 积分桶服务端按活跃自动发放，`getpointdetail` 可查（daily 带 endTime 每日重置）。
- 新号首赠 50 积分，首次生成另有奖励。

## 七、OpenAI 兼容对外接口

- `GET  /v1/models`
- `POST /v1/images/generations`
- `POST /v1/images/edits`
- `POST /v1/video/generations`
- 旧 ChatGPT/OpenAI 兼容入口（chat、responses、messages、search、PPT/PSD 文件任务）已移除，返回 `410 Gone`
- 鉴权：`Authorization: Bearer {auth-key}`（config 里的 auth-key）

## 八、部署

```bash
uv sync                       # 装依赖（含 curl-cffi/cryptography/gitpython/tiktoken/pybase64）
# 配置 config.json 的 auth-key；data/register.json 的邮箱 provider/域名/代理
uv run python main.py         # 或 docker compose up -d
```

关键配置文件：
- `config.example.yaml` 是示例；运行时真实配置文件是本地 `config.json`：auth-key、`oreate-proxy`、配额
- `data/register.json`：YYDS Mail api_key、域名(用 100811.xyz)、invite 开关、`proxy`

## 九、代理策略（重要，与注册/生图分离）

设计：**注册走动态代理换 IP 躲风控，生图/生视频/邀请走服务器固定 IP**（账号长期同 IP 使用更像真人、不易判异常）。

- **注册代理**：`data/register.json` 的 `proxy` 字段
  - 填**动态代理网关**（如住宅代理 `http://user:pass@gateway:port`，每次请求自动换出口 IP）
  - 这样连续注册不会触发 OreateAI 的 `100002` 反刷冷却
- **生图/生视频代理**：`config.json` 的 `oreate-proxy` 字段
  - **留空 = 服务器直连（推荐）**，账号老在同一 IP 使用更稳
  - 真实注册入库的账号 `proxy` 字段为空，**不会继承注册的动态代理**（已在 `_make_session` 处理）
- 上线前务必把 `register.json` 里 `127.0.0.1:10808`（本地调试代理）改成服务器实际的动态代理地址

## 十、纯协议、可无头部署

注册/生图/生视频/邀请**全是 HTTP 协议请求**（curl_cffi 模拟 Chrome TLS 指纹），
不依赖浏览器/GUI，服务器纯 Python 即可运行。调试用的 agent-browser-cli/Chrome 运行时不需要。
curl_cffi 带 C 扩展，用 Debian/Ubuntu 基础镜像最稳（alpine/musl 可能缺 wheel）。
