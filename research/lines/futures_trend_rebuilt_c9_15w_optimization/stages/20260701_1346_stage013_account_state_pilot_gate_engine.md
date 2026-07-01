# Stage013 账户状态小风险试探真实引擎候选

- 记录时间：`2026-07-01T13:46:08`
- line_id：`futures_trend_rebuilt_c9_15w_optimization`
- model_tag：`stage013_account_state_pilot_gate_engine_v1`
- 是否重要突破版本：`否`
- 决策：`stage013_goal_not_met_keep_research_candidate_for_attribution`

## 本次版本变更

- 新增参数：`enable_stage013_account_state_pilot_gate=True`、`stage013_pilot_drawdown_trigger_pct=0.3`、`stage013_pilot_active_positions_max=1`、`stage013_pilot_min_volume=1`。
- 修改参数：无，官方线上 C9/15w 配置未改；本阶段只在独立研究 profile 内覆盖。
- 删除参数：无。
- 规则：深回撤且有效空仓/低活跃状态下，`flat_entry` 新开仓先降到 1 手试探；不按品种、日期、方向黑名单。

## 回测参数

- 起点：`2018-01-01` 起每半年一个独立冷启动，共 `17` 个。
- 终点：`2026-06-30`。
- 资金：`150,000`。
- AI 池：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage182_ai_product_pool_live_inference_combined_stage78_eligibility_stage182_ai_product_pool_live_inference_v1.csv`。

## 回测结果

- 正收益起点：`17/17`。
- 期末权益最小/中位/最大：`152,851.60` / `507,553.10` / `14,970,195.30`。
- 总收益最小/中位/最大：`1.9011%` / `238.3687%` / `9880.1302%`。
- 最大回撤最差/中位：`-43.7940%` / `-36.7684%`。
- Sharpe 最小/中位/最大：`0.2860` / `1.2722` / `1.5580`。
- 总滑点：`5,042,750.00`。
- 总交易次数：`6,691`。
- 胜率中位：`52.2353%`。
- Stage013 触发次数：`639`；累计减少手数：`67514`。
- 密集任意结束日 `>1` 年负窗口：`330947` / `7215647`，最差 `-43.7940%`。
- 到 `2026-06-30` 负窗口：`0` / `13267`，最差 `26.6753%`。
- 全周期 `80%` 收益保留：`17/17`。
- AI 月度审计 FAIL：`0`。

## 文件

- summary: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage013_account_state_pilot_gate_engine/rebuilt_c9_stage013_account_state_pilot_gate_engine_summary_stage013_account_state_pilot_gate_engine_v1.csv`
- curves: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage013_account_state_pilot_gate_engine/rebuilt_c9_stage013_account_state_pilot_gate_engine_curves_stage013_account_state_pilot_gate_engine_v1.csv`
- entry_candidates: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage013_account_state_pilot_gate_engine/rebuilt_c9_stage013_account_state_pilot_gate_engine_entry_candidates_stage013_account_state_pilot_gate_engine_v1.csv`
- trades: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage013_account_state_pilot_gate_engine/rebuilt_c9_stage013_account_state_pilot_gate_engine_trades_stage013_account_state_pilot_gate_engine_v1.csv`
- entry_risk: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage013_account_state_pilot_gate_engine/rebuilt_c9_stage013_account_state_pilot_gate_engine_entry_risk_stage013_account_state_pilot_gate_engine_v1.csv`
- trade_events: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage013_account_state_pilot_gate_engine/rebuilt_c9_stage013_account_state_pilot_gate_engine_trade_events_stage013_account_state_pilot_gate_engine_v1.csv`
- intraday_events: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage013_account_state_pilot_gate_engine/rebuilt_c9_stage013_account_state_pilot_gate_engine_intraday_events_stage013_account_state_pilot_gate_engine_v1.csv`
- pilot_gate_events: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage013_account_state_pilot_gate_engine/rebuilt_c9_stage013_account_state_pilot_gate_engine_pilot_gate_events_stage013_account_state_pilot_gate_engine_v1.csv`
- ai_month_audit: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage013_account_state_pilot_gate_engine/rebuilt_c9_stage013_account_state_pilot_gate_engine_ai_month_audit_stage013_account_state_pilot_gate_engine_v1.csv`
- ai_pool_audit: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage013_account_state_pilot_gate_engine/rebuilt_c9_stage013_account_state_pilot_gate_engine_ai_pool_audit_stage013_account_state_pilot_gate_engine_v1.csv`
- goal_aggregate: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage013_account_state_pilot_gate_engine/rebuilt_c9_stage013_account_state_pilot_gate_engine_goal_aggregate_stage013_account_state_pilot_gate_engine_v1.csv`
- goal_to_final: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage013_account_state_pilot_gate_engine/rebuilt_c9_stage013_account_state_pilot_gate_engine_goal_to_final_windows_stage013_account_state_pilot_gate_engine_v1.csv`
- goal_fixed_horizon: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage013_account_state_pilot_gate_engine/rebuilt_c9_stage013_account_state_pilot_gate_engine_goal_fixed_horizon_windows_stage013_account_state_pilot_gate_engine_v1.csv`
- goal_worst_windows: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage013_account_state_pilot_gate_engine/rebuilt_c9_stage013_account_state_pilot_gate_engine_goal_worst_windows_stage013_account_state_pilot_gate_engine_v1.csv`
- retention: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage013_account_state_pilot_gate_engine/rebuilt_c9_stage013_account_state_pilot_gate_engine_full_cycle_retention_stage013_account_state_pilot_gate_engine_v1.csv`
- absolute_equity_chart: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage013_account_state_pilot_gate_engine/rebuilt_c9_stage013_account_state_pilot_gate_engine_absolute_equity_chart_stage013_account_state_pilot_gate_engine_v1.png`
- performance_chart: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage013_account_state_pilot_gate_engine/rebuilt_c9_stage013_account_state_pilot_gate_engine_performance_chart_stage013_account_state_pilot_gate_engine_v1.png`
- goal_audit_chart: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage013_account_state_pilot_gate_engine/rebuilt_c9_stage013_account_state_pilot_gate_engine_goal_audit_chart_stage013_account_state_pilot_gate_engine_v1.png`
- decision: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage013_account_state_pilot_gate_engine/rebuilt_c9_stage013_account_state_pilot_gate_engine_decision_stage013_account_state_pilot_gate_engine_v1.json`
- report: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage013_account_state_pilot_gate_engine/rebuilt_c9_stage013_account_state_pilot_gate_engine_report_stage013_account_state_pilot_gate_engine_v1.md`

## 后续规划和 TODO

- 若仍未满足严格任意结束日目标，停止把深回撤小风险试探当作已解决方案；继续归因它实际触发在哪些账户状态和是否错过右尾。
- 鸡蛋仍需单独补 full-universe monthly AI 分数或非挤占候选，不能直接塞入共享 AI topN。
- 后续若写确认后风险释放，必须继续用真实引擎验证，不用代理曲线替代。

## 反思

- 过拟合反思：否，但风险上升。本阶段仍是单规则冻结验证；如果继续把阈值、品种或日期调到刚好修复 2022-07 窗口，就会过拟合。
- 继续价值反思：是。无论是否达标，真实引擎触发事件和密集窗口审计可以判断账户状态风控是否有方向价值；但不能直接上线。
