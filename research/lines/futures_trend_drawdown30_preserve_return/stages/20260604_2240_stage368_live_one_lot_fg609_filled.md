# Stage368 实盘 FG609 一手买开成交与对账

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：2026-06-04 22:40 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：真实 CTP 实盘 1 手测试单提交、成交、只读对账
- 是否重要突破：是，首次完成实盘 order API 提交并取得真实成交回报。
- 是否触发A/B：否，本阶段不改策略版本、不做 A/B。

## 外部调研与判断

- 参考资料：本次未新增网上/GitHub 调研；执行依据 `skills/futures-live-execution-sop/SKILL.md`、用户明确授权、fresh Stage655 只读账户/持仓/保证金快照、Stage367 最新盘口 dry-run。
- 我的判断：本次是交易通道验证，不是策略信号；真实提交前已满足 fresh read-only、dry-run、用户确认允许留下 `FG609.CZCE` 1 手真实持仓三个核心条件。

## 本次变更

- 新增脚本：无
- 修改脚本：无
- 删除脚本：无
- 新增参数：无
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：不适用；本阶段为真实 CTP 实盘提交与成交后对账。
- 账户规模：提交前账户权益/可用约 `200,000.33`，当前保证金 `0.0`，持仓 `0` 行。
- 成本口径：真实成交后账户显示手续费约 `6.6064`，当前保证金 `3,087.0`。
- 样本过滤：仅 `FG609.CZCE` 1 手测试单。
- 策略/归因口径：非策略信号，手工授权的通道测试单。

## 结果

- 期末权益：成交后账户权益约 `199,973.7236`。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用；成交价位于最新卖一附近。
- 总交易次数：真实成交 `1` 笔。
- 胜率：不适用。
- 其他关键指标：
  - 提交前 fresh read-only：`front/auth/login/settlement=true`，账户 `1` 行，持仓 `0` 行，显式保证金 `1` 行，快照时间 `2026-06-04 22:38:11`。
  - 提交前 latest dry-run：bid1/ask1 `1028.0/1029.0`，最新价 `1029.0`，草案买开 `1` 手，限价 `1031.0`，估算保证金 `3,093.0`。
  - 真实 submit：`send_order_api_called_count=1`，`cancel_order_api_called_count=0`。
  - 委托：`FG609.CZCE`，买开 `1` 手，限价 `1031.0`。
  - 成交：`FG609.CZCE`，买开 `1` 手，成交价 `1029.0`，成交回报 `1` 行。
  - 成交后只读账户：权益约 `199,973.7236`，可用约 `196,886.7236`，当前保证金 `3,087.0`，手续费约 `6.6064`，持仓盈亏 `-20.0`。
  - 成交后只读持仓：`FG609` 今日仓 `1`，使用保证金 `3,087.0`，持仓成本 `20,580.0`，持仓盈亏 `-20.0`。
  - 残余持仓：存在，符合用户明确接受的“留下 `FG609.CZCE` 1 手多单”。

## 输出文件

- report：无
- summary：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage367_live_one_lot_order_summary_20260604_223847_stage367_live_one_lot_order_v1.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage655_readonly_account_margin_probe_summary_stage655_readonly_account_margin_probe_v1.json`
- orders：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage367_live_one_lot_order_orders_20260604_223847_stage367_live_one_lot_order_v1.csv`
- daily：无
- quality：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage367_live_one_lot_order_trades_20260604_223847_stage367_live_one_lot_order_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage655_readonly_account_margin_probe_accounts_stage655_readonly_account_margin_probe_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage655_readonly_account_margin_probe_positions_stage655_readonly_account_margin_probe_v1.csv`

## 结论

- 本阶段结论：真实 CTP 实盘 1 手测试单已成交，`FG609.CZCE` 留下 `1` 手多单；交易通道从登录、行情、下单、成交回报到账户/持仓对账已闭合。
- 是否进入下一步：可以，但下一步是持仓监控和必要时平仓验证，不是扩大策略手数。
- 下一步：继续监控 `FG609.CZCE` 1 手持仓；若用户要求平仓，必须先 fresh read-only，再生成平仓 dry-run，并取得明确确认后提交平仓单。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段没有优化策略参数或选择历史收益更好的品种，只做用户授权的一手真实交易通道测试。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值，但应限制范围。
- 原因：本阶段证明真实 CTP order API 可提交并成交，且账户/持仓可对账；继续价值在 TCA、平仓验证和实盘执行安全，不在扩大仓位或修改 alpha。

## 合入建议

- 是否更新本线 `LINE.md`：是，登记 Stage368 成交和残余持仓。
- 是否更新 `research/registry.md`：是，最新关键阶段推进到 Stage368。
- 是否追加根目录 `memory.md/back_log.md`：是，属于实盘执行重要里程碑。
