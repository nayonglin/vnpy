# 2026-06-04 22:02 Stage364 实盘 TD/MD 只读登录与行情订阅验证

## 版本改动

- 所属研究线：`futures_trend_drawdown30_preserve_return`
- 当前工作模式：`day`
- 是否重要突破：是，首次确认当前本机正式版 CTP runtime 路径下，实盘行情前置可登录并收到实时 tick；交易前置已完成 front connect 与认证，但交易登录被账户状态阻断。
- 修改正式策略：无。
- 修改实盘版本：无，当前官方实盘版本仍为 `official_live_stage653_20w_force95_to80`。
- 新增参数：无策略参数；执行参数为只读探针等待 `35/45` 秒、行情订阅样例 `MA609/rb2610/ru2609`。
- 修改参数：将本次 CTP runtime 优先级从本地 CP/测评 framework 改为 `vnpy_ctp` site-packages 内正式 framework；不改仓库默认策略逻辑。
- 删除参数：无。
- 下单 API：`send_order_api_called_count=0`，`cancel_order_api_called_count=0`。

## 外部调研与本地判断

- 官方/GitHub/PyPI 调研结论：`vnpy_ctp` 不是没有正式版 API；公开说明为 CTP 期货接口封装，且接口库包含穿透式实盘与评测环境合并版本。
- 本地判断：Stage363 的“缺生产环境 API/runtime”是运行库路径优先级误判，已由 Stage364 修正。当前 site-packages 内正式 framework 可用于本次实盘行情登录；CP framework 仍只适合券商评测/CP 前置，不应优先用于实盘生产前置。

## 交易前置只读登录结果

- 探针：Stage655 TD-only read-only account margin probe。
- 生成时间：`2026-06-04 22:01:25`。
- `tdapi_import_available=true`
- `front_connected=true`
- `auth_ok=true`
- `login_ok=false`
- `settlement_ok=false`
- 登录失败原因：`CTP:用户不活跃`
- `account_rows=0`
- `position_rows=0`
- `explicit_margin_rows=0`
- 结论：交易前置网络与认证已通，阻断点是账户交易登录状态，不是当前网络、App/Auth 或 CTP framework 加载问题。

## 行情前置订阅结果

- 探针：Stage274 MD-only subscribe probe。
- 行情登录：`front_connected=true`，`login_ok=true`。
- 订阅响应：`subscription_response_count=3`，三只合约订阅均返回 `ErrorID=0`。
- tick 数：`tick_count=250`。
- 最新 tick 时间：`2026-06-04 22:02:24`。
- `MA609`：最新价 `2887.0`，买一 `2886.0`，卖一 `2887.0`，成交量 `159420`，持仓量 `721717.0`。
- `rb2610`：最新价 `3152.0`，买一 `3152.0`，卖一 `3153.0`，成交量 `136965`，持仓量 `1713113.0`。
- `ru2609`：最新价 `17945.0`，买一 `17945.0`，卖一 `17950.0`，成交量 `73217`，持仓量 `182665.0`。
- 结论：实盘行情链路可用，可以继续用于只读 tick/盘口验证和后续 TCA 数据准备。

## 输出文件

- TD summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage655_readonly_account_margin_probe_summary_stage655_readonly_account_margin_probe_v1.json`
- TD log：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage655_readonly_account_margin_probe_logs_stage655_readonly_account_margin_probe_v1.csv`
- MD log：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage364_live_md_only_subscribe_pro_20260604_220137.log`

## 结论与后续

- 当前实盘行情登录和订阅已跑通。
- 当前交易登录没有跑通，直接原因是 `CTP:用户不活跃`；需要券商/柜台激活交易账户或确认账户状态后重测。
- 账户未能登录前，不能读取真实账户资金、持仓、`CurrMargin`，也不能进入 dry-run、1 手测试单或任何策略手数提交。
- 下一步：让券商确认账户可交易状态后，重跑 Stage655 只读账户/持仓/保证金探针；只有 `login_ok/settlement_ok/account_rows/explicit_margin_rows` 通过后，才进入 dry-run 与显式人工确认流程。

## 反思

- 过拟合反思：否。本阶段只验证实盘 TD/MD 通信链路，不修改策略、资金、品种、阈值或回测指标。
- 继续价值反思：是。行情链路已经可用，交易链路阻断点收敛到账号状态；继续推进的价值在账户激活后的只读快照、dry-run、1 手测试单和 TCA 闭环，而不是继续优化回测。
