# Stage008 PIT 入场风险释放闸门真实引擎 A/B

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-02T04:13:01
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：真实引擎 A/B；不改官方 live config、不连接 CTP、不调用下单
- 是否重要突破：否
- 是否触发A/B：是；A=Stage013，C=Stage013+Stage008

## 外部调研与判断

- 参考资料：pysystemtrade/Rob Carver systematic trading、金融机器学习 point-in-time/backtest overfitting、趋势跟随 RSI/whipsaw 资料。
- 我的判断：Stage007 的条件只能作为风险释放候选；真实引擎必须保持 AI 月池、止损重试、保证金、整数手和成本逻辑不变。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage008_pit_entry_risk_release_gate_engine.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：`stage008_ai_rank_min=5`、`stage008_ai_rank_max=8`、`stage008_long_rsi_min=75.0`、`stage008_short_rsi_max=25.0`、`stage008_pilot_min_volume=1`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：`2018-01-01` 到 `2026-06-30`
- 账户规模：`150,000`
- 成本口径：沿用 C9/Stage013 引擎 rates/slippages/sizes/priceticks。
- 样本过滤：每半年独立冷启动。
- 策略/归因口径：C 只对 opened flat_entry 中 `AI rank 5-8 + RSI 极端顺势 + selected_volume>1` 降为 1 手。

## 结果

- 期末权益：最小 `160,032.00`；中位 `492,538.10`；最大 `10,221,751.50`
- 总收益：最小 `6.6880%`；中位 `228.3587%`；最大 `6714.5010%`
- 最大回撤：最差 `-42.8852%`；中位 `-34.1016%`
- Sharpe：最小 `0.6116`；中位 `1.1776`
- 总滑点：`3,309,490.00`
- 总交易次数：`6,676`
- 胜率：中位 `52.7964%`
- 80% 收益保留：`12/17`
- 严格任意结束日 >1 年负窗口：`227543/7215647`，最差 `-37.7422%`
- 到终点负窗口：`0/13267`，最差 `20.4528%`
- Stage008 触发事件：`217`；减少手数 `11046`
- A/B 收益胜出：`3/17`；收益差中位 `-10.0100pp`
- 决策：`stage008_not_promoted_keep_for_attribution`

## 输出文件

- summary: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage008_pit_entry_risk_release_gate_engine/rebuilt_c9_v2_stage008_pit_entry_risk_release_gate_engine_summary_stage008_pit_entry_risk_release_gate_engine_v1.csv`
- curves: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage008_pit_entry_risk_release_gate_engine/rebuilt_c9_v2_stage008_pit_entry_risk_release_gate_engine_curves_stage008_pit_entry_risk_release_gate_engine_v1.csv`
- entry_candidates: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage008_pit_entry_risk_release_gate_engine/rebuilt_c9_v2_stage008_pit_entry_risk_release_gate_engine_entry_candidates_stage008_pit_entry_risk_release_gate_engine_v1.csv.gz`
- trades: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage008_pit_entry_risk_release_gate_engine/rebuilt_c9_v2_stage008_pit_entry_risk_release_gate_engine_trades_stage008_pit_entry_risk_release_gate_engine_v1.csv.gz`
- entry_risk: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage008_pit_entry_risk_release_gate_engine/rebuilt_c9_v2_stage008_pit_entry_risk_release_gate_engine_entry_risk_stage008_pit_entry_risk_release_gate_engine_v1.csv.gz`
- trade_events: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage008_pit_entry_risk_release_gate_engine/rebuilt_c9_v2_stage008_pit_entry_risk_release_gate_engine_trade_events_stage008_pit_entry_risk_release_gate_engine_v1.csv.gz`
- stage008_events: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage008_pit_entry_risk_release_gate_engine/rebuilt_c9_v2_stage008_pit_entry_risk_release_gate_engine_pit_gate_events_stage008_pit_entry_risk_release_gate_engine_v1.csv`
- ai_month_audit: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage008_pit_entry_risk_release_gate_engine/rebuilt_c9_v2_stage008_pit_entry_risk_release_gate_engine_ai_month_audit_stage008_pit_entry_risk_release_gate_engine_v1.csv`
- ai_pool_audit: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage008_pit_entry_risk_release_gate_engine/rebuilt_c9_v2_stage008_pit_entry_risk_release_gate_engine_ai_pool_audit_stage008_pit_entry_risk_release_gate_engine_v1.csv`
- goal_aggregate: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage008_pit_entry_risk_release_gate_engine/rebuilt_c9_v2_stage008_pit_entry_risk_release_gate_engine_goal_aggregate_stage008_pit_entry_risk_release_gate_engine_v1.csv`
- goal_to_final: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage008_pit_entry_risk_release_gate_engine/rebuilt_c9_v2_stage008_pit_entry_risk_release_gate_engine_goal_to_final_windows_stage008_pit_entry_risk_release_gate_engine_v1.csv`
- goal_fixed_horizon: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage008_pit_entry_risk_release_gate_engine/rebuilt_c9_v2_stage008_pit_entry_risk_release_gate_engine_goal_fixed_horizon_windows_stage008_pit_entry_risk_release_gate_engine_v1.csv`
- goal_worst_windows: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage008_pit_entry_risk_release_gate_engine/rebuilt_c9_v2_stage008_pit_entry_risk_release_gate_engine_goal_worst_windows_stage008_pit_entry_risk_release_gate_engine_v1.csv`
- retention: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage008_pit_entry_risk_release_gate_engine/rebuilt_c9_v2_stage008_pit_entry_risk_release_gate_engine_retention_vs_stage013_stage008_pit_entry_risk_release_gate_engine_v1.csv`
- ab_summary: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage008_pit_entry_risk_release_gate_engine/rebuilt_c9_v2_stage008_pit_entry_risk_release_gate_engine_ab_summary_vs_stage013_stage008_pit_entry_risk_release_gate_engine_v1.csv`
- performance_chart: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage008_pit_entry_risk_release_gate_engine/rebuilt_c9_v2_stage008_pit_entry_risk_release_gate_engine_absolute_equity_chart_stage008_pit_entry_risk_release_gate_engine_v1.png`
- goal_audit_chart: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage008_pit_entry_risk_release_gate_engine/rebuilt_c9_v2_stage008_pit_entry_risk_release_gate_engine_goal_audit_chart_stage008_pit_entry_risk_release_gate_engine_v1.png`
- decision: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage008_pit_entry_risk_release_gate_engine/rebuilt_c9_v2_stage008_pit_entry_risk_release_gate_engine_decision_stage008_pit_entry_risk_release_gate_engine_v1.json`
- report: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage008_pit_entry_risk_release_gate_engine/rebuilt_c9_v2_stage008_pit_entry_risk_release_gate_engine_report_stage008_pit_entry_risk_release_gate_engine_v1.md`

## 结论

- 本阶段结论：`stage008_not_promoted_keep_for_attribution`
- 是否进入下一步：仅当 C 明显减少负窗口且收益保留过线时才继续；否则保留为只读归因。
- 下一步：根据结果决定是否拆分 `rsi_exhaustion` 与 `ai_rank_5_to_8` 的真实贡献，不能追加品种/日期黑名单。

## 过拟合反思

- 运行前判断：有风险。Stage008 的条件来自 Stage007 residual attribution；通过只使用 PIT 字段、固定 rank/RSI 区间、只降为试探仓来控制。
- 运行后判断：有过拟合风险且真实引擎证据不足。不能因为归因 lift 高就继续叠条件救结果。
- 原因：本阶段只有一个预声明规则，但标签来自 Stage007 残余窗口，若继续叠条件救结果会过拟合。

## 继续价值反思

- 运行前判断：有价值。它直接检验 Stage007 归因是否能在真实组合引擎里减少一年以上左尾，而不是继续做代理曲线。
- 运行后判断：有限。若结果没有改善负窗口，应停止该组合规则，回到更外生的信号或账户层结构。
- 原因：真实引擎结果能判断 Stage007 条件是否只是归因幻觉。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：是。
- 是否追加根目录 `memory.md/back_log.md`：否，除非结果成为正式候选或重要路线废弃。
