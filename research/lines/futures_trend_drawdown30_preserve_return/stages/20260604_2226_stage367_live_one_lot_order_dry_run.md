# Stage367 实盘最小一手成交候选与 dry-run 闸门

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：2026-06-04 22:26 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：实盘执行链路 dry-run / 最小测试单候选选择
- 是否重要突破：是，实盘 TD/MD 只读成功后首次把“最便宜活跃品种”推进到真实 CTP 盘口 dry-run；但没有真实报单。
- 是否触发A/B：否，本阶段不改策略版本、不进入 A/B。

## 外部调研与判断

- 参考资料：本次未新增网上/GitHub 调研；执行判断依据仓库 `skills/futures-live-execution-sop/SKILL.md`、本地 TqSDK 合约元数据快照、Stage655 实盘只读账户快照，以及实时 CTP 行情订阅。
- 我的判断：用户要的是“成交一单看链路”，不是策略 alpha 优化；因此应按最小风险、最小保证金、盘口活跃和可 dry-run 校验来选品种。`FG609.CZCE` 在当前候选中保证金估算最低且盘口活跃，适合作为 1 手实盘测试候选；但真实 submit 会留下真实持仓，必须再取得用户明确确认。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/run_ctp_stage367_live_one_lot_order.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `--mode dry-run|submit-open`
  - `--vt-symbol`
  - `--direction long|short`
  - `--volume`
  - `--aggressive-ticks`
  - `--max-snapshot-age-seconds`
  - `--confirm-submit`
  - `--confirm-residual-position`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：不适用；本阶段为实盘只读 + 实时行情 dry-run。
- 账户规模：Stage655 最新只读账户快照权益约 `200,000.33`，可用约 `200,000.33`，当前保证金占用 `0.0`，持仓 `0` 行。
- 成本口径：不适用；dry-run 未成交。估算一手 `FG609.CZCE` 每跳价值 `20`，盘口价差 `1` tick，即约 `20`。
- 样本过滤：从本地低保证金候选中订阅实时盘口；淘汰盘口缺失或无成交候选。
- 策略/归因口径：非策略信号；仅用于验证真实 CTP 下单链路的最小一手测试候选。

## 结果

- 期末权益：不适用；实盘只读账户快照约 `200,000.33`。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用，未成交。
- 总交易次数：`0`，dry-run 未调用真实下单。
- 胜率：不适用。
- 其他关键指标：
  - 实盘只读闸门：`front_connected/auth_ok/login_ok/settlement_ok=true`，账户 `1` 行，持仓 `0` 行，显式保证金 `1` 行。
  - 实盘只读快照时间：`2026-06-04 22:23:40`，dry-run 使用时新鲜度约 `102.717` 秒，通过 `300` 秒闸门。
  - 候选行情扫描：`FG609/SA609/rb2610/hc2610/sp2609/CF609/jm2609` 均有有效实时盘口；`SM607/SM609` 盘口为 `0`，不适合测试；`si2609` 未取得可用 tick。
  - 最低可测候选：`FG609.CZCE`，最新 dry-run tick 为 bid1 `1027.0`、ask1 `1028.0`、last `1027.0`。
  - dry-run 委托草案：`FG609.CZCE`，买开 `1` 手，限价 `1030.0`，逻辑为 ask + `2` ticks。
  - 估算名义金额：`20,600.0`。
  - dry-run 脚本当时估算保证金：`1,030.0`，使用的是本地旧元数据参考保证金率 `5%`，该估算偏低。
  - 券商手机 App 实盘保证金口径：约 `3,084.0`，按盘口 `1028.0 * 20 * 15%` 反推；若按 dry-run 限价 `1030.0` 估算约 `3,090.0`。真实保证金以柜台/客户端返回为准。
  - `send_order_api_called_count=0`，`cancel_order_api_called_count=0`。
  - 脚本语法检查：`.py311/bin/python -m py_compile` 通过。

## 输出文件

- report：无
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage367_live_one_lot_order_summary_20260604_222522_stage367_live_one_lot_order_v1.json`
- orders：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage367_live_one_lot_order_orders_20260604_222522_stage367_live_one_lot_order_v1.csv`
- daily：无
- quality：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage367_live_one_lot_order_ticks_20260604_222522_stage367_live_one_lot_order_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage367_live_one_lot_order_accounts_20260604_222522_stage367_live_one_lot_order_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage367_live_one_lot_order_logs_20260604_222522_stage367_live_one_lot_order_v1.csv`

## 结论

- 本阶段结论：当前最便宜且盘口活跃的一手实盘测试候选是 `FG609.CZCE`。dry-run 已通过，只生成买开 `1` 手、限价 `1030.0` 的委托草案，没有真实下单。保证金估算以券商手机 App 口径修正为约 `3,084-3,090`，不再使用本地旧 `5%` 估算。
- 是否进入下一步：可以，但下一步是实盘 submit 前确认，不是自动下单。
- 下一步：如用户明确确认“按最新盘口 ask+2tick 买开 `FG609.CZCE` 1 手，并允许留下真实持仓”，先刷新 Stage655 只读账户/持仓/保证金快照，再执行 `submit-open`。若用户希望不留仓，则应改为开仓成交后再手工/脚本平仓，但那会是至少两笔真实交易，不是“一单”。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段不是收益模型或参数优化，只是按执行安全和最小测试成本做实盘品种筛选；没有根据历史收益调整策略。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值，但边界很窄。
- 原因：这能验证实盘 CTP 从只读、行情到委托生成的关键链路；但它只验证交易通道，不证明 Stage653 策略有效，也不应该扩大成正常策略手数。

## 合入建议

- 是否更新本线 `LINE.md`：是，登记 Stage367 实盘最小一手 dry-run 已通过。
- 是否更新 `research/registry.md`：是，当前执行链路最新关键阶段应推进到 Stage367。
- 是否追加根目录 `memory.md/back_log.md`：是，属于实盘链路重要里程碑。
