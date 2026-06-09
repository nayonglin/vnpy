# Stage369 实盘 FG609 一手卖平成交与空仓对账

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：2026-06-04 22:45 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：真实 CTP 实盘 1 手持仓平仓、成交、空仓对账
- 是否重要突破：是，开仓、平仓、成交回报、保证金释放和空仓对账完成闭环。
- 是否触发A/B：否，本阶段不改策略版本、不做 A/B。

## 外部调研与判断

- 参考资料：本次未新增网上/GitHub 调研；执行依据 `skills/futures-live-execution-sop/SKILL.md`、用户明确要求平仓、fresh Stage655 持仓快照。
- 我的判断：用户已明确要求把 Stage368 留下的 `FG609.CZCE` 1 手多单平仓；这是降低风险的动作，核心要求是确认持仓存在、平仓成交、保证金释放、账户回到空仓。

## 本次变更

- 新增脚本：无
- 修改脚本：`examples/portfolio_backtesting/run_ctp_stage367_live_one_lot_order.py`
- 删除脚本：无
- 新增参数/模式：
  - `dry-run-close`
  - `submit-close`
  - `--confirm-close-position`
- 修改参数：无
- 删除参数：无
- 重要修复：`dry-run-close` 初始实现遗漏 dry-run return，导致本次本应 dry-run 的卖平请求实际进入提交路径；平仓结果符合用户“把这个平仓”的明确要求，但这是执行流程缺陷。已修复为 `dry-run-close` 只返回草案，不再调用 `send_order`，并通过 `py_compile`。

## 回测/归因参数

- 数据区间：不适用；本阶段为真实 CTP 实盘平仓与对账。
- 账户规模：平仓前账户权益约 `199,993.7236`，可用约 `196,906.7236`，当前保证金 `3,087.0`，持仓 `FG609` 1 手。
- 成本口径：真实账户回报；开平两笔手续费合计约 `13.2129`，价差损益 `-20.0`。
- 样本过滤：仅 `FG609.CZCE` 1 手持仓。
- 策略/归因口径：非策略信号，用户授权的通道测试平仓。

## 结果

- 期末权益：平仓后账户权益约 `199,967.1171`。
- 总收益：本次开平测试相对 `200,000.33` 约 `-33.2129`。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用；卖平实际成交 `1028.0`。
- 总交易次数：平仓成交 `1` 笔；本轮开平合计真实成交 `2` 笔。
- 胜率：不适用。
- 其他关键指标：
  - 平仓前 fresh read-only：`front/auth/login/settlement=true`，账户 `1` 行，持仓 `1` 行，显式保证金 `1` 行。
  - 平仓前持仓：`FG609` 多单 `1` 手，当前保证金 `3,087.0`。
  - 平仓卖出盘口：bid1/ask1 `1028.0/1029.0`，卖平限价 `1026.0`，用于主动成交。
  - 平仓成交：`FG609.CZCE`，卖平 `1` 手，成交价 `1028.0`。
  - 平仓后账户：权益约 `199,967.1171`，可用约 `199,967.1171`，当前保证金 `0.0`，平仓盈亏 `-20.0`，总手续费约 `13.2129`。
  - 平仓后持仓：`FG609` 返回 `position=0` 的空行，使用保证金 `0.0`，账户风险已释放。
  - `dry-run-close` 缺陷影响：本次卖平实际已经提交并成交；缺陷已修复，后续 `dry-run-close` 不会再提交。

## 输出文件

- report：无
- summary：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage367_live_one_lot_order_summary_20260604_224333_stage367_live_one_lot_order_v1.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage655_readonly_account_margin_probe_summary_stage655_readonly_account_margin_probe_v1.json`
- orders：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage367_live_one_lot_order_orders_20260604_224333_stage367_live_one_lot_order_v1.csv`
- daily：无
- quality：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage367_live_one_lot_order_trades_20260604_224333_stage367_live_one_lot_order_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage655_readonly_account_margin_probe_accounts_stage655_readonly_account_margin_probe_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage655_readonly_account_margin_probe_positions_stage655_readonly_account_margin_probe_v1.csv`

## 结论

- 本阶段结论：`FG609.CZCE` 1 手多单已卖平，账户当前空仓，保证金释放为 `0.0`；真实开平仓链路已经闭合。
- 是否进入下一步：可以，但下一步应先做执行缺陷复盘、TCA 和保证金口径校准，不应扩大策略手数。
- 下一步：修复后的 close dry-run 脚本只作为工具保留；后续如再做真实委托，必须先 dry-run 并检查 `send_order_api_called_count=0` 后再进入 submit。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段没有优化策略参数，只验证真实交易通道和平仓链路。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值，但需要提高执行纪律。
- 原因：实盘开平仓闭环完成，证明 CTP 通道可用；同时暴露了 dry-run-close 工具缺陷，必须在扩大任何实盘动作前先修复和复核执行工具。

## 合入建议

- 是否更新本线 `LINE.md`：是，登记 Stage369 平仓、空仓和脚本修复。
- 是否更新 `research/registry.md`：是，最新关键阶段推进到 Stage369。
- 是否追加根目录 `memory.md/back_log.md`：是，属于实盘执行重要里程碑和缺陷复盘。
