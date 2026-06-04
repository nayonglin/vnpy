# Stage306 Fresh Live Context Adapter Dry-Run

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-04 04:09 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：code-bearing dry-run validator；不重放策略、不连接 CTP、不调用 `send_order`。
- 是否重要突破：否。Stage305 的 live context 合同已变成可执行校验代码，但仍没有真实快照或真实 `vt_orderid`。
- 是否触发A/B：否。没有新收益候选，也没有实盘/TCA样本。

## 外部调研与判断

- 参考资料：
  - vn.py MainEngine/Gateway source：https://github.com/vnpy/vnpy/tree/master/vnpy/trader
  - vn.py event-driven architecture reference：https://deepwiki.com/vnpy/vnpy/2.1-main-engine-and-event-system
  - vn.py custom gateway order contract reference：https://deepwiki.com/vnpy/vnpy/7.2-creating-custom-gateways
  - doc_knowledge 查询 vn.py live trading/order/event 相关文档：无额外结果。
- 本地源码/实现判断：
  - `qmt_roll_live_context_adapter.py` 只读取已连接 `MainEngine` 的 OMS cache：`get_contract/get_tick/get_all_accounts/get_all_positions`。
  - 模块不调用 `connect/subscribe/send_order/cancel_order`。
  - 空快照时必须 `real_submit_allowed=0`，禁止用历史 reference price 替代 live limit price。
- 我的判断：
  - 当前不应继续做收益回测或宽池选品，应该先把 pre-submit context 变成可复用工程组件。
  - Stage606 的价值在于把 `0/45 live context` 从报告缺口变成 fail-closed 校验代码；但它不等于拿到了真实 live context。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/qmt_roll_live_context_adapter.py`
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage606_fresh_live_context_adapter_dry_run.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数/常量：
  - `REQUIRED_LIVE_CONTEXT_FIELDS = 9` 个字段，沿用 Stage591 合同。
  - `PRE_SUBMIT_HEATMAP_FIELDS = ref/payload + 7 个实盘字段`
  - `allow_historical_reference_price = false`
  - `operator_confirmed = false`
  - `max_snapshot_age_seconds = 300`
  - `max_tick_age_seconds = 10`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：读取 Stage591 submit plan `5` 行。
- 策略版本：无新增策略版本；只检查 Stage591 pre-submit 行是否能被 fresh live context validator 消费。
- 账户规模：不适用；本阶段不做权益回放。
- 成本口径：不适用；本阶段不计算滑点。
- 快照输入：空 snapshots，故预期所有 live context 字段失败。
- 安全约束：
  - `send_order_api_called_count = 0`
  - `ctp_connection_attempted = false`
  - 不生成 synthetic `vt_orderid`
  - 不允许历史参考价作为 live limit price fallback

## 结果

- 新增交易回测：无
- 决策：`fresh_live_context_adapter_code_ready_fail_closed_no_snapshots`
- promotion allowed：`false`
- zero execution bias claim allowed：`false`
- 期末权益：无新增；Stage526 参考 `23,369,505`
- 总收益：无新增；Stage526 参考 `3699.9195%`
- 最大回撤：无新增；Stage526 参考 `-36.2670%`
- Sharpe：无新增；Stage526 参考 `1.6385`
- 总滑点：无新增；Stage526 参考 `1,342,190`
- 总交易次数：无新增；Stage526 参考 `905`
- 胜率：无新增；Stage526 非零日胜率参考 `53.6330%`
- 其他关键指标：
  - submit plan rows：`5`
  - adapter contract checks：`10/10`
  - context rows generated：`45/45`
  - live context present：`0/45`
  - real submit allowed：`0/5`
  - hard gates：`7/11`
  - failed hard gates：`fresh_live_context_ready`、`live_limit_price_ready`、`operator_confirmation_ready`、`p0_live_context_ready`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage606_fresh_live_context_adapter_dry_run_report_stage606_fresh_live_context_adapter_dry_run_v1.md`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage606_fresh_live_context_adapter_dry_run_decision_stage606_fresh_live_context_adapter_dry_run_v1.json`
- adapter contract：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage606_fresh_live_context_adapter_dry_run_adapter_contract_stage606_fresh_live_context_adapter_dry_run_v1.csv`
- context rows：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage606_fresh_live_context_adapter_dry_run_context_rows_stage606_fresh_live_context_adapter_dry_run_v1.csv`
- order readiness：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage606_fresh_live_context_adapter_dry_run_order_readiness_stage606_fresh_live_context_adapter_dry_run_v1.csv`
- heatmap data：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage606_fresh_live_context_adapter_dry_run_pre_submit_heatmap_stage606_fresh_live_context_adapter_dry_run_v1.csv`
- gates：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage606_fresh_live_context_adapter_dry_run_gates_stage606_fresh_live_context_adapter_dry_run_v1.csv`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage606_fresh_live_context_adapter_dry_run_chart_stage606_fresh_live_context_adapter_dry_run_v1.png`

## 图表视觉复盘

- 左上图显示 adapter contract `10/10` 和 dry-run safety `3/3` 为绿，但 live evidence `0/4` 为红，说明代码层已推进，但真实快照层未推进。
- 右上图显示 9 个 live context 字段全部仍为 `0/5`；这符合预期，证明没有注入假快照。
- 左下图显示 5 个订单的 `ref/payload` 全绿，`contract/account/position/limit/band/margin/operator` 全红。这是最关键的视觉结论：validator 保留 Stage591 合同，但从真实执行字段开始 fail-closed。
- 右下图显示所有 blocker 都是 `5` 行全覆盖，说明失败是系统性缺 live context，不是单个产品异常。

## 结论

- 本阶段结论：
  - fresh live context validator 已实现并 dry-run 审计通过。
  - 它能读取未来已连接 MainEngine 的 contract/tick/account/position cache，但当前运行不连接 CTP。
  - 空快照下，所有 Stage591 submit plan 行都被阻断，`real_submit_allowed=0/5`，这是正确行为。
  - Stage079/Stage526 仍不能声明真实交易无偏差，因为 live context 仍为 `0/45`，真实 `vt_orderid` 仍为 `0/5`。
- 是否进入下一步：进入测试环境 read-only snapshot 输入阶段；仍不进入收益回测、P0/P1白名单或A/B。
- 下一步：
  1. 用 SimNow/券商测试 read-only snapshot 填入 validator：contract/account/position/tick。
  2. 在 operator confirmation 仍为 false 时确认继续 fail-closed。
  3. 只有 fresh context 全绿后，才进入明确测试环境、显式确认下的真实 `send_order` 返回 `vt_orderid` 持久化。
  4. 随后接 `EVENT_ORDER/EVENT_TRADE/EVENT_TICK` TCA reducer。

## 过拟合反思

- 运行前判断：否。因为本阶段只写执行校验代码，不改策略、参数、产品池、信号、仓位或历史成交。
- 运行后判断：否。输出没有任何收益改善，且空快照全部 fail，说明没有用历史数据救结果。
- 原因：本阶段只提升真实可成交链路的工程可验证性。

## 继续价值反思

- 运行前判断：有价值。Stage305 已经证明缺口在 live context adapter，本阶段正是补这个缺口。
- 运行后判断：有价值。`0/45` 缺口虽未变成绿色，但已经从人工报告变成可执行 gate；下一步可以直接接 read-only 快照。
- 原因：真实交易无偏差目标必须先有这个 fail-closed 验证器，才能安全地进入 `vt_orderid` 和 TCA。

## 合入建议

- 是否更新本线 `LINE.md`：是，更新当前状态和下一步。
- 是否更新 `research/registry.md`：是，更新本线最新阶段摘要。
- 是否追加根目录 `memory.md/back_log.md`：否。没有正式候选或重要突破。
