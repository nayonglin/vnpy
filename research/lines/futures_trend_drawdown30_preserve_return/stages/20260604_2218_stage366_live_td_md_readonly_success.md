# 2026-06-04 22:18 Stage366 实盘账号改密后 TD/MD 只读成功

## 版本改动

- 所属研究线：`futures_trend_drawdown30_preserve_return`
- 当前工作模式：`day`
- 是否重要突破：是，首次用当前实盘账号密码完成 TD 交易前置认证、交易登录、结算确认、账户查询与持仓查询。
- 修改正式策略：无。
- 修改实盘版本：无，当前官方实盘版本仍为 `official_live_stage653_20w_force95_to80`。
- 新增参数：无策略参数；执行上复用正式 framework、TD 只读探针等待 `35` 秒、MD 订阅等待 `12` 秒。
- 修改参数：本地 `ctp_live.local.env` 中 `CTP_PASSWORD` 指纹较 Stage365 变化；`CTP_USERID` 指纹不变。
- 删除参数：无。
- 下单 API：`send_order_api_called_count=0`，`cancel_order_api_called_count=0`。

## 脱敏配置确认

- 本地配置文件：`examples/portfolio_backtesting/ctp_live.local.env`
- 文件权限：`0600`
- 文件修改时间：`2026-06-04 22:17:04`
- 当前交易用户号长度：`9`
- 当前密码指纹较 Stage365 已变化。
- 不在记录中写入账号、密码、认证码或前置地址明文。

## 交易前置只读登录结果

- 探针：Stage655 TD-only read-only account margin probe。
- 生成时间：`2026-06-04 22:17:47`。
- `missing_required_env=[]`
- `tdapi_import_available=true`
- `front_connected=true`
- `auth_ok=true`
- `login_ok=true`
- `settlement_ok=true`
- `account_rows=1`
- `position_rows=0`
- `explicit_margin_rows=1`
- 账户快照：`Balance=175279.33`，`Available=175279.33`，`CurrMargin=0.0`
- 持仓快照：当前无持仓。
- 结论：TD 只读链路已满足 fresh read-only 的核心前置；交易账户可登录，结算确认与账户/持仓查询成功。

## 行情前置订阅结果

- 探针：Stage274 MD-only subscribe probe。
- 行情登录：`front_connected=true`，`login_ok=true`。
- 订阅响应：`subscription_response_count=3`，三只合约订阅均返回 `ErrorID=0`。
- tick 数：`tick_count=62`。
- 最新 tick 时间：`2026-06-04 22:18:26-22:18:27`。
- `MA609`：最新价 `2886.0`，买一 `2886.0`，卖一 `2887.0`，成交量 `170768`，持仓量 `722286.0`。
- `rb2610`：最新价 `3152.0`，买一 `3152.0`，卖一 `3153.0`，成交量 `148057`，持仓量 `1713451.0`。
- `ru2609`：最新价 `17940.0`，买一 `17935.0`，卖一 `17940.0`，成交量 `81779`，持仓量 `182366.0`。
- 结论：改密后 MD 行情链路继续可用。

## 输出文件

- TD success snapshot base：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage366_live_td_readonly_success_20260604_221813`
- TD summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage366_live_td_readonly_success_20260604_221813_summary.json`
- TD log：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage366_live_td_readonly_success_20260604_221813_logs.csv`
- TD accounts：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage366_live_td_readonly_success_20260604_221813_accounts.csv`
- TD positions：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage366_live_td_readonly_success_20260604_221813_positions.csv`
- MD log：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage366_live_md_subscribe_after_td_success_20260604_221813.log`

## 结论与后续

- 用户本次改密有效，TD 登录失败已解除。
- 当前真实账户快照为空仓、可用资金约 `17.53` 万，低于当前官方实盘配置 `20` 万口径；后续进入 dry-run 或实际委托前，必须把真实账户权益作为账户状态约束，不能机械按 20 万目标手数执行。
- 下一步若继续推进，应重跑官方最新 signal/gate，并在真实账户快照基础上走 dry-run；任何 1 手测试单或策略提交仍需要显式人工确认。

## 反思

- 过拟合反思：否。本阶段只验证实盘账号 TD/MD 只读链路，不修改 alpha、资金参数、品种、阈值或回测指标。
- 继续价值反思：是。登录、结算、资金、持仓、行情均已闭合到只读层，继续推进的价值在真实账户权益约束下的 signal/gate/dry-run/TCA，而不是继续调策略。
