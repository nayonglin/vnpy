# Stage028 xsmom 确认加风险真实引擎 A/B

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-02T07:42:49
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：真实引擎 A/B；不改官方 live config、不连接 CTP、不调用下单
- 是否重要突破：否
- 是否触发A/B：是；A=Stage013，C=Stage013+Stage028

## 外部调研与判断

- 参考资料：pysystemtrade/Rob Carver position sizing、meta-labeling/bet sizing、managed futures/trend following。
- 我的判断：Stage027 唯一前沿线索是 Stage022 xsmom 入场确认；本阶段必须冻结为前一交易日 12-1m xsmom 不反向真引擎，不能扫 xsmom lookback/topN/权重救参。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage028_xsmom_confirmation_add_risk_engine.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：`stage028_ai_rank_min=1`、`stage028_ai_rank_max=8`、`stage028_max_risk_multiplier=2.0`、`stage028_add_risk_fraction=0.25`、`stage028_xsmom_spec=mom_12m_skip1m`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：`2018-01-01` 到 `2026-06-30`
- 账户规模：`150,000`
- 成本口径：沿用 C9/Stage013 引擎 rates/slippages/sizes/priceticks。
- 样本过滤：每半年独立冷启动。
- 策略/归因口径：C 只对 opened flat_entry 中 `AI rank 1-8 + selected_volume>1 + risk_multiplier<2 + prior xsmom12 not opposed` 按 floor 25% 增加整数手数。

## 结果

- 期末权益：最小 `156,691.60`；中位 `437,433.10`；最大 `14,929,177.00`
- 总收益：最小 `4.4611%`；中位 `191.6221%`；最大 `9852.7847%`
- 最大回撤：最差 `-47.6821%`；中位 `-38.9615%`
- Sharpe：最小 `0.4586`；中位 `1.1074`
- 总滑点：`5,158,980.00`
- 总交易次数：`6,726`
- 胜率：中位 `52.2513%`
- 80% 收益保留：`14/17`
- 严格任意结束日 >1 年负窗口：`351519/7215647`，最差 `-44.3266%`
- 到终点负窗口：`69/13267`，最差 `-12.5613%`
- Stage028 触发事件：`622`；增加手数 `11387`
- A/B 收益胜出：`6/17`；收益差中位 `-10.9967pp`
- 决策：`stage028_not_promoted_keep_for_attribution`

## 输出文件

- summary: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage028_xsmom_confirmation_add_risk_engine/rebuilt_c9_v2_stage028_xsmom_confirmation_add_risk_engine_summary_stage028_xsmom_confirmation_add_risk_engine_v1.csv`
- curves: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage028_xsmom_confirmation_add_risk_engine/rebuilt_c9_v2_stage028_xsmom_confirmation_add_risk_engine_curves_stage028_xsmom_confirmation_add_risk_engine_v1.csv`
- entry_candidates: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage028_xsmom_confirmation_add_risk_engine/rebuilt_c9_v2_stage028_xsmom_confirmation_add_risk_engine_entry_candidates_stage028_xsmom_confirmation_add_risk_engine_v1.csv.gz`
- trades: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage028_xsmom_confirmation_add_risk_engine/rebuilt_c9_v2_stage028_xsmom_confirmation_add_risk_engine_trades_stage028_xsmom_confirmation_add_risk_engine_v1.csv.gz`
- entry_risk: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage028_xsmom_confirmation_add_risk_engine/rebuilt_c9_v2_stage028_xsmom_confirmation_add_risk_engine_entry_risk_stage028_xsmom_confirmation_add_risk_engine_v1.csv.gz`
- trade_events: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage028_xsmom_confirmation_add_risk_engine/rebuilt_c9_v2_stage028_xsmom_confirmation_add_risk_engine_trade_events_stage028_xsmom_confirmation_add_risk_engine_v1.csv.gz`
- stage028_events: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage028_xsmom_confirmation_add_risk_engine/rebuilt_c9_v2_stage028_xsmom_confirmation_add_risk_engine_xsmom_confirmation_add_risk_events_stage028_xsmom_confirmation_add_risk_engine_v1.csv`
- ai_month_audit: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage028_xsmom_confirmation_add_risk_engine/rebuilt_c9_v2_stage028_xsmom_confirmation_add_risk_engine_ai_month_audit_stage028_xsmom_confirmation_add_risk_engine_v1.csv`
- ai_pool_audit: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage028_xsmom_confirmation_add_risk_engine/rebuilt_c9_v2_stage028_xsmom_confirmation_add_risk_engine_ai_pool_audit_stage028_xsmom_confirmation_add_risk_engine_v1.csv`
- goal_aggregate: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage028_xsmom_confirmation_add_risk_engine/rebuilt_c9_v2_stage028_xsmom_confirmation_add_risk_engine_goal_aggregate_stage028_xsmom_confirmation_add_risk_engine_v1.csv`
- goal_to_final: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage028_xsmom_confirmation_add_risk_engine/rebuilt_c9_v2_stage028_xsmom_confirmation_add_risk_engine_goal_to_final_windows_stage028_xsmom_confirmation_add_risk_engine_v1.csv`
- goal_fixed_horizon: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage028_xsmom_confirmation_add_risk_engine/rebuilt_c9_v2_stage028_xsmom_confirmation_add_risk_engine_goal_fixed_horizon_windows_stage028_xsmom_confirmation_add_risk_engine_v1.csv`
- goal_worst_windows: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage028_xsmom_confirmation_add_risk_engine/rebuilt_c9_v2_stage028_xsmom_confirmation_add_risk_engine_goal_worst_windows_stage028_xsmom_confirmation_add_risk_engine_v1.csv`
- retention: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage028_xsmom_confirmation_add_risk_engine/rebuilt_c9_v2_stage028_xsmom_confirmation_add_risk_engine_retention_vs_stage013_stage028_xsmom_confirmation_add_risk_engine_v1.csv`
- ab_summary: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage028_xsmom_confirmation_add_risk_engine/rebuilt_c9_v2_stage028_xsmom_confirmation_add_risk_engine_ab_summary_vs_stage013_stage028_xsmom_confirmation_add_risk_engine_v1.csv`
- absolute_equity_chart: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage028_xsmom_confirmation_add_risk_engine/rebuilt_c9_v2_stage028_xsmom_confirmation_add_risk_engine_absolute_equity_chart_stage028_xsmom_confirmation_add_risk_engine_v1.png`
- nav_chart: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage028_xsmom_confirmation_add_risk_engine/rebuilt_c9_v2_stage028_xsmom_confirmation_add_risk_engine_nav_chart_stage028_xsmom_confirmation_add_risk_engine_v1.png`
- goal_audit_chart: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage028_xsmom_confirmation_add_risk_engine/rebuilt_c9_v2_stage028_xsmom_confirmation_add_risk_engine_goal_audit_chart_stage028_xsmom_confirmation_add_risk_engine_v1.png`
- decision: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage028_xsmom_confirmation_add_risk_engine/rebuilt_c9_v2_stage028_xsmom_confirmation_add_risk_engine_decision_stage028_xsmom_confirmation_add_risk_engine_v1.json`
- report: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage028_xsmom_confirmation_add_risk_engine/rebuilt_c9_v2_stage028_xsmom_confirmation_add_risk_engine_report_stage028_xsmom_confirmation_add_risk_engine_v1.md`

## 结论

- 本阶段结论：`stage028_not_promoted_keep_for_attribution`
- 是否进入下一步：只有在负窗口、收益保留、AI 审计同时改善时才进入独立 review；否则保留为归因证据。
- 下一步：根据结果判断 Stage022 proxy 是否能真实落地；不能继续调 lookback/topN/权重、品种/日期黑名单或 ceil/min+1。

## 过拟合反思

- 运行前判断：有中等风险。Stage022 来自 proxy 前沿筛选；本阶段通过固定 12-1m 前一交易日 not-opposed、AI rank 1-8、risk<2、floor25 整数加风险来降低自由度。
- 运行后判断：有过拟合风险且真实引擎证据不足。若 proxy 改善不能真实落地，就不能继续围绕同一 xsmom 条件调参。
- 原因：本阶段冻结一个低自由度规则；若失败后继续叠条件救结果，就会转为过拟合。

## 继续价值反思

- 运行前判断：有价值。Stage027 唯一前沿线索是 Stage022 xsmom confirmation，本阶段直接检验它在真实组合引擎、保证金、成本和止损重试下是否仍成立。
- 运行后判断：有限。除非结果显示明显结构改善，否则应回到更外生的 PIT 源或账户层结构。
- 原因：它是 Stage027 唯一前沿线索的真引擎检验。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：是。
- 是否追加根目录 `memory.md/back_log.md`：否，除非结果成为正式候选或重要路线废弃。
