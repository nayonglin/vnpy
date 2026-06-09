# 2026-06-04 22:15 Stage365 实盘账号密码变更后 TD/MD 只读复测

## 版本改动

- 所属研究线：`futures_trend_drawdown30_preserve_return`
- 当前工作模式：`day`
- 是否重要突破：是，确认用户更新后的本地实盘账号密码已经被加载，并把交易登录阻断从 Stage364 的 `用户不活跃` 收敛为 `不合法的登录`。
- 修改正式策略：无。
- 修改实盘版本：无，当前官方实盘版本仍为 `official_live_stage653_20w_force95_to80`。
- 新增参数：无策略参数；执行上复用正式 framework、只读 TD 探针等待 `35` 秒、MD 订阅等待 `20` 秒。
- 修改参数：本地 `ctp_live.local.env` 中 `CTP_USERID/CTP_PASSWORD` 已变化；经纪商、AppID、认证码、TD/MD 前置指纹保持不变。
- 删除参数：无。
- 下单 API：`send_order_api_called_count=0`，`cancel_order_api_called_count=0`。

## 脱敏配置确认

- 本地配置文件：`examples/portfolio_backtesting/ctp_live.local.env`
- 文件权限：`0600`
- 文件修改时间：`2026-06-04 22:13:06`
- 当前交易用户号长度：`9`
- 当前交易用户号与密码指纹均较 Stage364 前的本地旧值发生变化。
- 不在记录中写入账号、密码、认证码或前置地址明文。

## 交易前置只读登录结果

- 探针：Stage655 TD-only read-only account margin probe。
- 生成时间：`2026-06-04 22:14:03`。
- `missing_required_env=[]`
- `tdapi_import_available=true`
- `front_connected=true`
- `auth_ok=true`
- `login_ok=false`
- `settlement_ok=false`
- 登录失败原因：`CTP:不合法的登录`
- `account_rows=0`
- `position_rows=0`
- `explicit_margin_rows=0`
- 结论：交易前置网络与 App/Auth 认证仍正常；当前阻断点是交易用户号/密码或柜台账户归属/权限不匹配，而不是前置网络或 CTP framework 加载问题。

## 行情前置订阅结果

- 探针：Stage274 MD-only subscribe probe。
- 日志：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage365_live_md_only_subscribe_changed_account_20260604_221417.log`
- 行情登录：`front_connected=true`，`login_ok=true`。
- 订阅响应：`subscription_response_count=3`，三只合约订阅均返回 `ErrorID=0`。
- tick 数：`tick_count=108`。
- 最新 tick 时间：`2026-06-04 22:14:39`。
- `MA609`：最新价 `2885.0`，买一 `2885.0`，卖一 `2886.0`，成交量 `168815`，持仓量 `722160.0`。
- `rb2610`：最新价 `3153.0`，买一 `3152.0`，卖一 `3153.0`，成交量 `146244`，持仓量 `1713035.0`。
- `ru2609`：最新价 `17950.0`，买一 `17945.0`，卖一 `17950.0`，成交量 `79605`，持仓量 `182489.0`。
- 结论：行情链路继续可用；MD 登录成功不等价于 TD 交易登录成功。

## 输出文件

- TD summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage655_readonly_account_margin_probe_summary_stage655_readonly_account_margin_probe_v1.json`
- TD log：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage655_readonly_account_margin_probe_logs_stage655_readonly_account_margin_probe_v1.csv`
- MD log：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage365_live_md_only_subscribe_changed_account_20260604_221417.log`

## 结论与后续

- 用户更新后的账号密码已经被当前运行加载。
- 交易登录仍失败，当前返回 `CTP:不合法的登录`，比 `用户不活跃` 更倾向于账号/密码、交易账号归属、柜台权限或经纪商绑定不匹配。
- 需要向券商核对：该交易用户号是否属于当前经纪商与当前 AppID/AuthCode，是否开通 CTP 生产交易权限，密码是否为 CTP 交易密码而非资金/客户端密码。
- 未取得 TD `login_ok=true`、结算确认、账户/持仓/保证金快照前，不进入 dry-run、1 手测试单或策略提交。

## 反思

- 过拟合反思：否。本阶段只验证更新后的实盘账号通信链路，不修改 alpha、资金、品种、阈值或回测指标。
- 继续价值反思：是。MD 已持续可用，TD 阻断点进一步收敛到账户凭据/权限匹配；继续推进的价值在券商确认凭据后重跑 fresh read-only，而不是调整策略。
