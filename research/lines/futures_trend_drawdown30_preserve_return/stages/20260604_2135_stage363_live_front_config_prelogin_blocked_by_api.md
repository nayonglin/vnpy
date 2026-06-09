# Stage363：实盘 front 配置与登录前置测试

- 时间：2026-06-04 21:35 CST
- 研究线：`futures_trend_drawdown30_preserve_return`
- 当前官方实盘版本：`official_live_stage653_20w_force95_to80`
- 决策：`live_front_configured_tcp_ok_login_blocked_by_missing_production_api`
- 是否重要突破版本：否。本阶段是实盘连接配置与登录前置测试，不是策略 alpha 或参数优化。

## 本次操作

- 已读取 `work-type.txt`、`research/registry.md`、`skills/futures-live-execution-sop/SKILL.md`。
- 已将券商提供的实盘连接信息保存到本地忽略文件：
  - `examples/portfolio_backtesting/ctp_live.local.env`
- 文件权限：`0600`
- 该文件被 `.gitignore` 的 `*.local.env` 覆盖，不进入 git。
- 复用本地已有账号/密码键，只更新实盘 broker、AppID、AuthCode、TD/MD front 配置。
- 未在 stage 文件、报告或聊天中记录明文账号、密码、认证码或 front 地址。

## 脱敏配置检查

- `CTP_USERID`：已配置，长度 `6`
- `CTP_PASSWORD`：已配置，长度 `8`
- `CTP_BROKERID`：已配置，长度 `4`
- `CTP_APPID`：已配置，长度 `19`
- `CTP_AUTH_CODE`：已配置，长度 `16`
- `CTP_TD_ADDRESS`：已配置
- `CTP_MD_ADDRESS`：已配置
- 备份 TD front：`5` 组
- 备份 MD front：`5` 组
- `CTP_EXPECT_PRODUCTION_API=1`

## 前置可达性测试

- 实盘主 TD/MD front：TCP 连接成功。
- 实盘备份 TD front：`5/5` TCP 连接成功。
- 实盘备份 MD front：`5/5` TCP 连接成功。

这和 Stage362 的 CP/测试前置不同：实盘 front 端口当前可达。

## 登录测试结论

- 未进入 `ReqAuthenticate/ReqUserLogin`。
- 原因：本地 `.py311` 当前 `vnpy_ctp` 运行时仍报告 `v6.7.7_MacOS_CP_20240716 15:00:00`，属于 CP/测评版 API，不符合券商“请使用生产环境的 API 版本接入”的要求。
- 已尝试在 `/private/tmp` 隔离安装/检查更高版本 `vnpy_ctp`，但源码构建因本地 Mac CTP 头文件/源码接口不匹配失败；未覆盖当前 `.py311` 环境。
- 按实盘 SOP，缺生产 API runtime 时 fail-closed，不冒用 CP/测评版 API 连接实盘。

## 回测结果

- 本阶段未新增回测。
- 期末权益：不适用
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：不适用
- 总交易次数：不适用
- 胜率：不适用
- order API 调用：`0`

## 反思

- 过拟合反思：否。本阶段只做实盘连接配置、前置 TCP 可达性和 API 版本校验，不修改策略、参数、品种池或交易信号。
- 继续价值反思：有价值。当前已经确认实盘 front 网络层可达，真正阻断点从“前置不可达”收敛为“本机缺生产 API runtime”。下一步应拿到券商/CTP 生产环境 Mac API 包或可用的生产版 `vnpy_ctp` wheel 后，再做只读登录。

## TODO

- 向券商索要生产环境 Mac CTP API 包，至少需要可链接的 `thosttraderapi_se.framework` 与 `thostmduserapi_se.framework`，且不能是 CP/测评版。
- 拿到生产 API 后，先只读登录：front/auth/login/settlement/account/position。
- 只有 fresh read-only 成功，才允许进入 dry-run。
- 只有 dry-run 通过且再次确认测试环境/实盘操作边界，才允许任何 submit 路径。
