# Oreate Register URL Context Design

**问题**

当前 Oreate 注册实现里，`services/register/oreate_register.py` 的注释已经说明
`fr`、`inviteCode`、`fissionCode` 应该来自注册页 URL query，但真实代码没有把这条
上下文贯通到 `referer`、`emailsignupin`、`emailregisterconfirm` 三处。

结果是：

- 本地实现与线上前端 bundle 已分叉
- `emailsignupin` 阶段容易触发 `code=100002, msg=Invalid parameter`
- 邀请链路和裂变链路都依赖隐式手工拼接，行为不可预测

**目标**

增加一个显式的 `register_url` 配置项，后端统一从该 URL 的 query 解析注册上下文，
并把它稳定透传到注册请求链路里。

**方案**

1. 在注册配置中新增 `register_url`
2. 后端新增统一的 register context 解析逻辑：
   - 解析 `fr`
   - 解析 `inviteCode`
   - 解析 `fissionCode`
   - 产出 canonical `referer`
3. `OreateRegistrar` 初始化时固化这份 context
4. `getticket`、`emailsignupin`、`emailregisterconfirm` 全部复用同一个 `referer`
5. `emailsignupin` / `emailregisterconfirm` 共用注册上下文 payload：
   - `jt`: **非空字符串**（前端 banti jsToken；布尔 `true` 或空串会触发 `100002`）
   - `fr`
   - `plat: "wap"`（保留当前移动端链路）
   - `fissionCode` / `inviteCode`（存在时才传）
6. 邀请绑定仍以 `emailregisterconfirm` 为准；signup 即使带 `inviteCode` 也不保证记入邀请
7. 如果运行时启用了自动邀请号池，则邀请号池选出的 `invite_code` 优先覆盖 URL 里的
   `inviteCode`，并强制 `fr=inviteFriend`，同时保留 URL 里的 `fissionCode`

**边界**

- 没配 `register_url` 时，回落到默认 `https://www.oreateai.com/userlogin/register`
- 没带 query 时，默认 `fr=main`
- 不引入额外抓包或页面抓取逻辑，不增加运行时网络依赖
- 仅修补当前注册链路，不扩展成新的注册模式

**测试**

- 新增单测验证 `register_url` 解析结果
- 新增单测验证 signup/confirm payload 使用字符串 `jt` 与 register context，同时 referer 使用 `register_url`
- 新增单测验证 confirm payload / referer
- 保留现有配置路径测试
