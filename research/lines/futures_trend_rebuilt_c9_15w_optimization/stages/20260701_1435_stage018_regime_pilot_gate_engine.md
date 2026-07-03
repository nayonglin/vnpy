# Stage018 high-vol/low-efficiency 小风险试探真实引擎

- 记录时间：`2026-07-01T14:35:29`
- line_id：`futures_trend_rebuilt_c9_15w_optimization`
- model_tag：`stage018_regime_pilot_gate_engine_v1`
- 是否重要突破版本：`否`
- 决策：`stage018_goal_not_met_keep_or_reject_after_attribution`

## 本次版本变更

- 新增参数：`enable_stage018_regime_pilot_gate=True`、`stage018_regime_gate_target_regime=high_vol_low_eff`、`stage018_regime_pilot_min_volume=1`。
- 修改参数：无，官方线上 C9/15w 配置未改；本阶段只在独立研究 profile 内覆盖。
- 删除参数：无。
- 规则：前一交易日 causal 市场状态为 `high_vol_low_eff` 时，`flat_entry` 新开仓降到 1 手试探；不按品种、日期、方向黑名单。

## 回测参数

- 起点：`2018-01-01` 起每半年一个独立冷启动，共 `17` 个。
- 终点：`2026-06-30`。
- 资金：`150,000`。
- AI 池：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage182_ai_product_pool_live_inference_combined_stage78_eligibility_stage182_ai_product_pool_live_inference_v1.csv`。
- regime 数据：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_product_suitability_market_walkforward_market_daily_product_suitability_market_wf_v2.csv`；最小历史 `252` 交易日。

## 回测结果

- 正收益起点：`17/17`。
- 期末权益最小/中位/最大：`158,551.60` / `499,793.10` / `11,270,940.50`。
- 总收益最小/中位/最大：`5.7011%` / `233.1954%` / `7413.9603%`。
- 最大回撤最差/中位：`-44.1514%` / `-40.2168%`。
- Sharpe 最小/中位/最大：`0.5748` / `1.2591` / `1.5125`。
- 总滑点：`3,398,650.00`。
- 总交易次数：`6,695`。
- 胜率中位：`51.8666%`。
- Stage018 触发次数：`234`；累计减少手数：`9088`。
- 密集任意结束日 `>1` 年负窗口：`280114` / `7215647`，最差 `-43.7940%`。
- 到 `2026-06-30` 负窗口：`0` / `13267`，最差 `25.8032%`。
- 全周期 `80%` 收益保留：`10/17`。
- AI 月度审计 FAIL：`0`。

## 文件

- summary: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage018_regime_pilot_gate_engine/rebuilt_c9_stage018_regime_pilot_gate_engine_summary_stage018_regime_pilot_gate_engine_v1.csv`
- curves: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage018_regime_pilot_gate_engine/rebuilt_c9_stage018_regime_pilot_gate_engine_curves_stage018_regime_pilot_gate_engine_v1.csv`
- entry_candidates: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage018_regime_pilot_gate_engine/rebuilt_c9_stage018_regime_pilot_gate_engine_entry_candidates_stage018_regime_pilot_gate_engine_v1.csv`
- trades: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage018_regime_pilot_gate_engine/rebuilt_c9_stage018_regime_pilot_gate_engine_trades_stage018_regime_pilot_gate_engine_v1.csv`
- entry_risk: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage018_regime_pilot_gate_engine/rebuilt_c9_stage018_regime_pilot_gate_engine_entry_risk_stage018_regime_pilot_gate_engine_v1.csv`
- trade_events: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage018_regime_pilot_gate_engine/rebuilt_c9_stage018_regime_pilot_gate_engine_trade_events_stage018_regime_pilot_gate_engine_v1.csv`
- intraday_events: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage018_regime_pilot_gate_engine/rebuilt_c9_stage018_regime_pilot_gate_engine_intraday_events_stage018_regime_pilot_gate_engine_v1.csv`
- regime_gate_events: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage018_regime_pilot_gate_engine/rebuilt_c9_stage018_regime_pilot_gate_engine_regime_gate_events_stage018_regime_pilot_gate_engine_v1.csv`
- ai_month_audit: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage018_regime_pilot_gate_engine/rebuilt_c9_stage018_regime_pilot_gate_engine_ai_month_audit_stage018_regime_pilot_gate_engine_v1.csv`
- ai_pool_audit: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage018_regime_pilot_gate_engine/rebuilt_c9_stage018_regime_pilot_gate_engine_ai_pool_audit_stage018_regime_pilot_gate_engine_v1.csv`
- goal_aggregate: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage018_regime_pilot_gate_engine/rebuilt_c9_stage018_regime_pilot_gate_engine_goal_aggregate_stage018_regime_pilot_gate_engine_v1.csv`
- goal_to_final: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage018_regime_pilot_gate_engine/rebuilt_c9_stage018_regime_pilot_gate_engine_goal_to_final_windows_stage018_regime_pilot_gate_engine_v1.csv`
- goal_fixed_horizon: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage018_regime_pilot_gate_engine/rebuilt_c9_stage018_regime_pilot_gate_engine_goal_fixed_horizon_windows_stage018_regime_pilot_gate_engine_v1.csv`
- goal_worst_windows: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage018_regime_pilot_gate_engine/rebuilt_c9_stage018_regime_pilot_gate_engine_goal_worst_windows_stage018_regime_pilot_gate_engine_v1.csv`
- retention: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage018_regime_pilot_gate_engine/rebuilt_c9_stage018_regime_pilot_gate_engine_full_cycle_retention_stage018_regime_pilot_gate_engine_v1.csv`
- regime_table: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage018_regime_pilot_gate_engine/rebuilt_c9_stage018_regime_pilot_gate_engine_causal_regime_table_stage018_regime_pilot_gate_engine_v1.csv`
- absolute_equity_chart: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage018_regime_pilot_gate_engine/rebuilt_c9_stage018_regime_pilot_gate_engine_absolute_equity_chart_stage018_regime_pilot_gate_engine_v1.png`
- performance_chart: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage018_regime_pilot_gate_engine/rebuilt_c9_stage018_regime_pilot_gate_engine_performance_chart_stage018_regime_pilot_gate_engine_v1.png`
- goal_audit_chart: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage018_regime_pilot_gate_engine/rebuilt_c9_stage018_regime_pilot_gate_engine_goal_audit_chart_stage018_regime_pilot_gate_engine_v1.png`
- decision: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage018_regime_pilot_gate_engine/rebuilt_c9_stage018_regime_pilot_gate_engine_decision_stage018_regime_pilot_gate_engine_v1.json`
- report: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage018_regime_pilot_gate_engine/rebuilt_c9_stage018_regime_pilot_gate_engine_report_stage018_regime_pilot_gate_engine_v1.md`

## 后续规划和 TODO

- 若未满足严格任意结束日目标，不能继续扫 regime 分位数、窗口或手数；应归因触发事件是否错杀右尾。
- 鸡蛋仍不能直接塞入共享 AI topN；如果 Stage018 有价值，再单独做非挤占小预算真实引擎。

## 反思

- 过拟合反思：否，但如果继续调整 quantile、min_history、手数或叠加 drawdown/active 条件来贴合最差窗口，就会过拟合。
- 继续价值反思：取决于严格目标与收益保留结果；若不能降低任意结束日负窗口且保留右尾，就应回到只读归因或换新信息源。
