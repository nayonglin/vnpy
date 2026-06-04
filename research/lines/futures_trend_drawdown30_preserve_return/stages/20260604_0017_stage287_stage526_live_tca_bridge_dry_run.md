# Stage287 Stage526 live TCA bridge dry-run

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：2026-06-04 00:17 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：dry-run 桥接实现与证据审计；不连接 CTP；不调用下单 API；不修改策略；不做收益回测。
- 是否重要突破：否，但属于 Stage526 实盘无偏差证据链的必要工程推进。
- 是否触发A/B：否。本阶段不是新交易版本，也不改变收益曲线。

## 外部调研与判断

- 参考资料：
  - vn.py/VeighNa 事件系统资料显示 `EVENT_ORDER` 对应 `OrderData`、`EVENT_TRADE` 对应 `TradeData`、`EVENT_TICK` 对应 `TickData`，是订单状态、成交回报和市场行情的自然生命周期入口。
  - tcapy 开源 TCA 框架强调以 order/trade 数据合并市场 tick 数据，计算 arrival/mid/TWAP/VWAP 等 benchmark 与 slippage/impact。
  - implementation shortfall / VWAP 的 TCA 资料均指向同一原则：必须从决策价、提交、成交、未成交和市场窗口 benchmark 建立订单级账本。
- 我的判断：
  - Stage526 若要声明真实成交无偏差，不能用“同日期同品种存在日志”替代订单级映射。
  - 合格证据必须是 `event_id/signal_id -> bridge_signal_id -> vt_orderid -> EVENT_ORDER/EVENT_TRADE/EVENT_TICK -> avg_fill/VWAP/shortfall/participation` 的同一条链。
  - 本阶段只实现 dry-run reducer 和严格 join contract；凡缺显式 `vt_orderid` 的 P0 一律不推断为有效样本。

参考链接：

- https://deepwiki.com/vnpy/vnpy/2.2-main-engine
- https://github.com/cuemacro/tcapy
- https://questdb.com/docs/cookbook/sql/finance/implementation-shortfall/

## 本次变更

- 新增/修改脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage587_stage526_live_tca_bridge_dry_run.py`
- 新增输出：
  - intent ledger、raw source scan、order/trade summary、mechanical reducer summary、live TCA ledger、join attempts、field completeness、gates、bridge contract、decision、report、chart。
- 修改口径：
  - 机械校验表保留原始 order 状态，同时当 `traded >= volume` 且 order 状态仍为 submitting 时，标记 `filled_inferred_from_order_traded`，避免把 SimNow order 回调不完整误读为未成交。
- 删除内容：无。

## 参数与闸门

- P0 符号：`fu2509.SHFE`、`lc2505.GFEX`、`AP505.CZCE`
- 每个 P0 需要有效样本：`3`
- 总 P0 有效样本要求：`9`
- `MAX_VWAP_COST_BPS=50.0`
- `MAX_IMPLEMENTATION_SHORTFALL_BPS=75.0`
- `MAX_PARTICIPATION_PCT=25.0`
- required actual fields：`20` 个，包括 signal、submit、fill、commission、actual slippage、implementation shortfall、VWAP、account equity、broker margin、participation、`bridge_vt_orderid`。

## Stage526 参考口径

- 期末权益：`23,369,505`
- 总收益：`3699.9195%`
- 最大回撤：`-36.2670%`
- Sharpe：`1.6385`
- Ulcer：`14.4691`
- 总滑点：`1,342,190`
- 总交易次数：`905`
- 胜率：非零日胜率 `53.6330%`

## 结果

- 决策：`dry_run_live_tca_bridge_created_no_valid_p0_samples`
- `send_order_api_called_count=0`
- `ctp_connection_attempted=false`
- 闸门：`6/11` 通过
- intent rows：`5`
- P0 intent rows：`3`
- raw CTP/SimNow source files：`78`
- raw CTP/SimNow rows scanned：`680`
- mechanical non-P0 order/trade joins：`2`
- explicit Stage526 vt_orderid mappings：`0`
- P0 joined order/trade rows：`0`
- P0 valid live TCA samples：`0/9`
- zero execution-bias claim allowed：`false`

## 闸门明细

通过项：

- dry_run_no_ctp_connection
- send_order_api_called_count_zero
- stage575_intent_loaded
- p0_intents_loaded
- raw_ctp_event_sources_scanned
- mechanical_non_p0_order_trade_reducer_ok

失败项：

- explicit_stage526_vt_orderid_mapping_present：`0`
- p0_order_trade_joined：`0`
- p0_actual_tca_fields_complete：`0/20`
- p0_valid_live_samples_complete：`0/9`
- zero_execution_bias_claim_allowed：not allowed

## 图表视觉复盘

- 左上 gate 图：前 6 项为绿，说明 dry-run 安全、Stage575 intent、P0 intent、本地 CTP/SimNow raw event 和非 P0 reducer 都成立；后 5 项全红，红灯集中在显式映射、P0 join、actual TCA field、P0 样本和无偏差声明。
- 右上 raw source 图：本地确实有 `accounts=29`、`orders=142`、`positions=338`、`ticks=167`、`trades=4` 的原始事件，不是采集框架完全缺失；但 P0 rows 为 `0`，说明这些材料不能补 Stage526 P0。
- 左下 P0 explicit join 图：`fu2509.SHFE/lc2505.GFEX/AP505.CZCE` 的 order joined、trade joined、valid sample 全为 `0`。关键不是没有图表，而是图上没有任何可以靠同品种同日误推的灰色地带。
- 右下 actual field completeness：all 与 P0 两列全部 `0%`，说明模板和桥字段存在，但真实 submit/fill/VWAP/shortfall/participation 尚未发生或未绑定。

## 输出文件

- script：`examples/portfolio_backtesting/analyze_qmt_roll_stage587_stage526_live_tca_bridge_dry_run.py`
- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage587_stage526_live_tca_bridge_dry_run_report_stage587_stage526_live_tca_bridge_dry_run_v1.md`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage587_stage526_live_tca_bridge_dry_run_chart_stage587_stage526_live_tca_bridge_dry_run_v1.png`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage587_stage526_live_tca_bridge_dry_run_decision_stage587_stage526_live_tca_bridge_dry_run_v1.json`
- gates：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage587_stage526_live_tca_bridge_dry_run_gates_stage587_stage526_live_tca_bridge_dry_run_v1.csv`
- intent ledger：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage587_stage526_live_tca_bridge_dry_run_intent_ledger_stage587_stage526_live_tca_bridge_dry_run_v1.csv`
- live TCA ledger：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage587_stage526_live_tca_bridge_dry_run_live_tca_ledger_stage587_stage526_live_tca_bridge_dry_run_v1.csv`
- join attempts：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage587_stage526_live_tca_bridge_dry_run_join_attempts_stage587_stage526_live_tca_bridge_dry_run_v1.csv`
- bridge contract：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage587_stage526_live_tca_bridge_dry_run_bridge_contract_stage587_stage526_live_tca_bridge_dry_run_v1.md`

## 结论

- 本阶段结论：bridge contract 和 reducer 已经建立，且可以对现有非 P0 SimNow order/trade 证明机械归并能力。
- 但 Stage526 P0 仍没有显式 `event_id/signal_id -> vt_orderid` 映射，没有 P0 order/trade join，没有 actual TCA 字段值，有效样本仍是 `0/9`。
- Stage526 当前仍只能称为正常成本主候选，不能声明“真实交易不存在偏差”。

## 下一步

1. 把 `bridge_signal_id` 写入未来 dry-run/pre-submit adapter 的 intent row。
2. 在 submit 或模拟 submit 时写出 `bridge_signal_id -> vt_orderid` mapping。
3. 归并后续真实 `EVENT_ORDER/EVENT_TRADE/EVENT_TICK`，计算 `avg_fill_price/filled_volume/unfilled_volume/cancelled_volume/VWAP/implementation_shortfall/participation`。
4. 对 `fu2509.SHFE/lc2505.GFEX/AP505.CZCE` 三类 P0 各累计 `3` 个有效样本；未达标前不允许关账执行无偏差。
5. 并行继续扩池 selector 的 point-in-time forward collection，但未达 Stage561 `20/20` 前不做选品收益回测。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段不改交易信号、不改参数、不做收益回测，也没有用 P0 同品种同日材料做宽松推断；相反，它把缺失证据明确保留为红灯。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值。
- 原因：真实可成交策略结构必须证明回测订单能映射到真实订单生命周期。现在桥已经存在，下一步 blocker 收敛为明确的 submit mapping 和真实 P0 样本采集，而不是继续散找证据。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：是，当前线最新关键阶段应刷新到 Stage287。
- 是否追加根目录 `memory.md/back_log.md`：是。该阶段影响 Stage526 是否能声明真实执行无偏差。
