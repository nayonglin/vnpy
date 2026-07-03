# Stage026 冷静高质量加风险真实引擎 A/B

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-02T06:59:25
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：真实引擎 A/B；不改官方 live config、不连接 CTP、不调用下单
- 是否重要突破：否
- 是否触发A/B：是；A=Stage013，C=Stage013+Stage026

## 外部调研与判断

- 参考资料：pysystemtrade/Rob Carver systematic trading、金融机器学习 point-in-time/backtest overfitting、趋势跟随 RSI/whipsaw 资料。
- 我的判断：Stage025 说明质量加风险桶也参与剩余左尾，因此真实引擎只能做 top AI 且不过热状态的冻结质量拆分；必须保持 AI 月池、止损重试、保证金、整数手和成本逻辑不变。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage026_cool_quality_add_risk_engine.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：`stage026_ai_rank_min=1`、`stage026_ai_rank_max=4`、`stage026_long_rsi_exhaustion_min=75.0`、`stage026_short_rsi_exhaustion_max=25.0`、`stage026_max_risk_multiplier=2.0`、`stage026_add_risk_fraction=0.25`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：`2018-01-01` 到 `2026-06-30`
- 账户规模：`150,000`
- 成本口径：沿用 C9/Stage013 引擎 rates/slippages/sizes/priceticks。
- 样本过滤：每半年独立冷启动。
- 策略/归因口径：C 只对 opened flat_entry 中 `AI rank 1-4 + selected_volume>1 + risk_multiplier<2 + 非 RSI 极端顺势` 按 floor 25% 增加整数手数。

## 结果

- 期末权益：最小 `166,021.60`；中位 `458,278.10`；最大 `13,907,695.70`
- 总收益：最小 `10.6811%`；中位 `205.5187%`；最大 `9171.7971%`
- 最大回撤：最差 `-43.7940%`；中位 `-35.7144%`
- Sharpe：最小 `0.7481`；中位 `1.2651`
- 总滑点：`4,303,960.00`
- 总交易次数：`6,697`
- 胜率：中位 `52.3702%`
- 80% 收益保留：`14/17`
- 严格任意结束日 >1 年负窗口：`394418/7215647`，最差 `-43.7940%`
- 到终点负窗口：`24/13267`，最差 `-7.1870%`
- Stage026 触发事件：`242`；增加手数 `3279`
- A/B 收益胜出：`10/17`；收益差中位 `0.6067pp`
- 决策：`stage026_not_promoted_keep_for_attribution`

## 输出文件

- summary: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage026_cool_quality_add_risk_engine/rebuilt_c9_v2_stage026_cool_quality_add_risk_engine_summary_stage026_cool_quality_add_risk_engine_v1.csv`
- curves: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage026_cool_quality_add_risk_engine/rebuilt_c9_v2_stage026_cool_quality_add_risk_engine_curves_stage026_cool_quality_add_risk_engine_v1.csv`
- entry_candidates: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage026_cool_quality_add_risk_engine/rebuilt_c9_v2_stage026_cool_quality_add_risk_engine_entry_candidates_stage026_cool_quality_add_risk_engine_v1.csv.gz`
- trades: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage026_cool_quality_add_risk_engine/rebuilt_c9_v2_stage026_cool_quality_add_risk_engine_trades_stage026_cool_quality_add_risk_engine_v1.csv.gz`
- entry_risk: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage026_cool_quality_add_risk_engine/rebuilt_c9_v2_stage026_cool_quality_add_risk_engine_entry_risk_stage026_cool_quality_add_risk_engine_v1.csv.gz`
- trade_events: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage026_cool_quality_add_risk_engine/rebuilt_c9_v2_stage026_cool_quality_add_risk_engine_trade_events_stage026_cool_quality_add_risk_engine_v1.csv.gz`
- stage026_events: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage026_cool_quality_add_risk_engine/rebuilt_c9_v2_stage026_cool_quality_add_risk_engine_cool_quality_add_risk_events_stage026_cool_quality_add_risk_engine_v1.csv`
- ai_month_audit: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage026_cool_quality_add_risk_engine/rebuilt_c9_v2_stage026_cool_quality_add_risk_engine_ai_month_audit_stage026_cool_quality_add_risk_engine_v1.csv`
- ai_pool_audit: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage026_cool_quality_add_risk_engine/rebuilt_c9_v2_stage026_cool_quality_add_risk_engine_ai_pool_audit_stage026_cool_quality_add_risk_engine_v1.csv`
- goal_aggregate: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage026_cool_quality_add_risk_engine/rebuilt_c9_v2_stage026_cool_quality_add_risk_engine_goal_aggregate_stage026_cool_quality_add_risk_engine_v1.csv`
- goal_to_final: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage026_cool_quality_add_risk_engine/rebuilt_c9_v2_stage026_cool_quality_add_risk_engine_goal_to_final_windows_stage026_cool_quality_add_risk_engine_v1.csv`
- goal_fixed_horizon: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage026_cool_quality_add_risk_engine/rebuilt_c9_v2_stage026_cool_quality_add_risk_engine_goal_fixed_horizon_windows_stage026_cool_quality_add_risk_engine_v1.csv`
- goal_worst_windows: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage026_cool_quality_add_risk_engine/rebuilt_c9_v2_stage026_cool_quality_add_risk_engine_goal_worst_windows_stage026_cool_quality_add_risk_engine_v1.csv`
- retention: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage026_cool_quality_add_risk_engine/rebuilt_c9_v2_stage026_cool_quality_add_risk_engine_retention_vs_stage013_stage026_cool_quality_add_risk_engine_v1.csv`
- ab_summary: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage026_cool_quality_add_risk_engine/rebuilt_c9_v2_stage026_cool_quality_add_risk_engine_ab_summary_vs_stage013_stage026_cool_quality_add_risk_engine_v1.csv`
- performance_chart: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage026_cool_quality_add_risk_engine/rebuilt_c9_v2_stage026_cool_quality_add_risk_engine_absolute_equity_chart_stage026_cool_quality_add_risk_engine_v1.png`
- goal_audit_chart: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage026_cool_quality_add_risk_engine/rebuilt_c9_v2_stage026_cool_quality_add_risk_engine_goal_audit_chart_stage026_cool_quality_add_risk_engine_v1.png`
- decision: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage026_cool_quality_add_risk_engine/rebuilt_c9_v2_stage026_cool_quality_add_risk_engine_decision_stage026_cool_quality_add_risk_engine_v1.json`
- report: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage026_cool_quality_add_risk_engine/rebuilt_c9_v2_stage026_cool_quality_add_risk_engine_report_stage026_cool_quality_add_risk_engine_v1.md`

## 结论

- 本阶段结论：`stage026_not_promoted_keep_for_attribution`
- 是否进入下一步：仅当 C 明显改善目标且收益保留过线时才继续；否则保留为只读归因。
- 下一步：根据结果决定是否拆分 top AI cool-quality 的真实贡献，不能追加品种/日期黑名单或改成 ceil/min+1 救参。

## 过拟合反思

- 运行前判断：有风险。Stage026 的条件来自 Stage025 对剩余左尾的反向约束；通过只使用 PIT 字段、固定 top rank/risk/RSI 结构和 floor 25% 整数加风险来控制。
- 运行后判断：有过拟合风险且真实引擎证据不足。不能因为归因 lift 高就继续叠条件救结果。
- 原因：本阶段只有一个预声明规则，但标签来自 Stage025 剩余左尾归因，若继续叠条件救结果会过拟合。

## 继续价值反思

- 运行前判断：有价值。它直接检验 Stage010/013 的质量加风险能否在真实组合引擎里保留右尾并减少一年以上左尾，而不是继续做代理曲线。
- 运行后判断：有限。若结果没有改善负窗口，应停止该组合规则，回到更外生的信号或账户层结构。
- 原因：真实引擎结果能判断 Stage025 的质量拆分是否只是归因幻觉。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：是。
- 是否追加根目录 `memory.md/back_log.md`：否，除非结果成为正式候选或重要路线废弃。
