# Stage058 quality + OI cap50 真实引擎 A/B

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-02T15:20:16
- 工作区：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：真实引擎 A/B；不改官方 live config、不连接 CTP、不调用下单
- 是否重要突破：待结果判断；当前为候选真实验证
- 是否触发A/B：是；A=Stage013，B=不适用，C=Stage013+Stage058

## 外部调研与判断

- 参考资料：meta-labeling/bet sizing、pysystemtrade/systematic trading、AQR managed futures/trend following。
- 我的判断：quality 与 OI 都是主信号上的点时 sizing overlay，不能独立交易；若要接近正式候选，必须在真实引擎里改善路径稳健性，同时不伤 AI 月池和趋势右尾。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage058_quality_oi_cap50_add_risk_engine.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：`stage058_ai_rank_min=1`、`stage058_ai_rank_max=8`、`stage058_quality_add_risk_fraction=0.25`、`stage058_oi_add_risk_fraction=0.25`、`stage058_total_add_risk_cap=0.5`、`stage058_contract_oi_share_min=0.5`、`stage058_max_feature_age_days=10`
- 修改参数：无正式参数修改
- 删除参数：无

## 回测/归因参数

- 数据区间：`2018-01-01` 到 `2026-06-30`
- 账户规模：`150,000`
- 成本口径：沿用 C9/Stage013 引擎 rates/slippages/sizes/priceticks。
- 样本过滤：每半年独立冷启动。
- 策略口径：只对 opened flat_entry 中的质量腿/OI腿做 capped floor 整数加风险；不开独立 B。

## 结果

- 期末权益：最小 `146,562.40`；中位 `467,728.10`；最大 `24,683,207.30`
- 总收益：最小 `-2.2917%`；中位 `211.8187%`；最大 `16355.4715%`
- 最大回撤：最差 `-44.7070%`；中位 `-38.3317%`
- Sharpe：最小 `0.0440`；中位 `1.1864`
- 总滑点：`9,624,690.00`
- 总交易次数：`6,746`
- 胜率：中位 `52.1739%`
- 80% 收益保留：`12/17`
- 严格任意结束日 >1 年负窗口：`323784/7215647`，最差 `-44.7070%`
- 到终点负窗口：`0/13267`，最差 `15.2654%`
- Stage058 触发事件：`1676`；增加手数 `63874`
- 事件构成：quality hit `1343`；OI hit `1428`；both hit `1095`
- A/B 收益胜出：`12/17`；收益差中位 `10.3333pp`
- 决策：`stage058_not_promoted_keep_for_attribution`

## 输出文件

- summary: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage058_quality_oi_cap50_add_risk_engine/rebuilt_c9_v2_stage058_quality_oi_cap50_add_risk_engine_summary_stage058_quality_oi_cap50_add_risk_engine_v1.csv`
- curves: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage058_quality_oi_cap50_add_risk_engine/rebuilt_c9_v2_stage058_quality_oi_cap50_add_risk_engine_curves_stage058_quality_oi_cap50_add_risk_engine_v1.csv`
- entry_candidates: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage058_quality_oi_cap50_add_risk_engine/rebuilt_c9_v2_stage058_quality_oi_cap50_add_risk_engine_entry_candidates_stage058_quality_oi_cap50_add_risk_engine_v1.csv.gz`
- trades: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage058_quality_oi_cap50_add_risk_engine/rebuilt_c9_v2_stage058_quality_oi_cap50_add_risk_engine_trades_stage058_quality_oi_cap50_add_risk_engine_v1.csv.gz`
- entry_risk: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage058_quality_oi_cap50_add_risk_engine/rebuilt_c9_v2_stage058_quality_oi_cap50_add_risk_engine_entry_risk_stage058_quality_oi_cap50_add_risk_engine_v1.csv.gz`
- trade_events: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage058_quality_oi_cap50_add_risk_engine/rebuilt_c9_v2_stage058_quality_oi_cap50_add_risk_engine_trade_events_stage058_quality_oi_cap50_add_risk_engine_v1.csv.gz`
- stage058_events: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage058_quality_oi_cap50_add_risk_engine/rebuilt_c9_v2_stage058_quality_oi_cap50_add_risk_engine_quality_oi_cap50_add_risk_events_stage058_quality_oi_cap50_add_risk_engine_v1.csv`
- ai_month_audit: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage058_quality_oi_cap50_add_risk_engine/rebuilt_c9_v2_stage058_quality_oi_cap50_add_risk_engine_ai_month_audit_stage058_quality_oi_cap50_add_risk_engine_v1.csv`
- ai_pool_audit: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage058_quality_oi_cap50_add_risk_engine/rebuilt_c9_v2_stage058_quality_oi_cap50_add_risk_engine_ai_pool_audit_stage058_quality_oi_cap50_add_risk_engine_v1.csv`
- goal_aggregate: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage058_quality_oi_cap50_add_risk_engine/rebuilt_c9_v2_stage058_quality_oi_cap50_add_risk_engine_goal_aggregate_stage058_quality_oi_cap50_add_risk_engine_v1.csv`
- goal_to_final: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage058_quality_oi_cap50_add_risk_engine/rebuilt_c9_v2_stage058_quality_oi_cap50_add_risk_engine_goal_to_final_windows_stage058_quality_oi_cap50_add_risk_engine_v1.csv`
- goal_fixed_horizon: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage058_quality_oi_cap50_add_risk_engine/rebuilt_c9_v2_stage058_quality_oi_cap50_add_risk_engine_goal_fixed_horizon_windows_stage058_quality_oi_cap50_add_risk_engine_v1.csv`
- goal_worst_windows: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage058_quality_oi_cap50_add_risk_engine/rebuilt_c9_v2_stage058_quality_oi_cap50_add_risk_engine_goal_worst_windows_stage058_quality_oi_cap50_add_risk_engine_v1.csv`
- retention: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage058_quality_oi_cap50_add_risk_engine/rebuilt_c9_v2_stage058_quality_oi_cap50_add_risk_engine_retention_vs_stage013_stage058_quality_oi_cap50_add_risk_engine_v1.csv`
- ab_summary: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage058_quality_oi_cap50_add_risk_engine/rebuilt_c9_v2_stage058_quality_oi_cap50_add_risk_engine_ab_summary_vs_stage013_stage058_quality_oi_cap50_add_risk_engine_v1.csv`
- absolute_equity_chart: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage058_quality_oi_cap50_add_risk_engine/rebuilt_c9_v2_stage058_quality_oi_cap50_add_risk_engine_absolute_equity_chart_stage058_quality_oi_cap50_add_risk_engine_v1.png`
- nav_chart: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage058_quality_oi_cap50_add_risk_engine/rebuilt_c9_v2_stage058_quality_oi_cap50_add_risk_engine_nav_chart_stage058_quality_oi_cap50_add_risk_engine_v1.png`
- goal_audit_chart: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage058_quality_oi_cap50_add_risk_engine/rebuilt_c9_v2_stage058_quality_oi_cap50_add_risk_engine_goal_audit_chart_stage058_quality_oi_cap50_add_risk_engine_v1.png`
- decision: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage058_quality_oi_cap50_add_risk_engine/rebuilt_c9_v2_stage058_quality_oi_cap50_add_risk_engine_decision_stage058_quality_oi_cap50_add_risk_engine_v1.json`
- report: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage058_quality_oi_cap50_add_risk_engine/rebuilt_c9_v2_stage058_quality_oi_cap50_add_risk_engine_report_stage058_quality_oi_cap50_add_risk_engine_v1.md`

## 结论

- 本阶段结论：`stage058_not_promoted_keep_for_attribution`
- 下一步：day 模式下先停下汇报；只有在真实引擎结果通过收益保留、负窗口和 A/B 对比后，才允许进入独立复核或更密集起点压力测试。

## 过拟合反思

- 运行前判断：否，暂不算明显过拟合。规则来自 Stage057 最强代理但只取一个固定组合，且 OI 使用点时 asof，不按坏窗口调品种、日期或方向。
- 运行后判断：真实引擎证据不足。若失败后继续调 OI 阈值、AI topN、权重、ceil 或品种方向，就是过拟合。
- 原因：本阶段只验证一个预声明组合规则；若失败后继续扫 OI 阈值、AI topN、权重或 ceil/min+1 就会过拟合。

## 继续价值反思

- 运行前判断：有价值。Stage057 只是 closed-lot proxy，必须用真实引擎验证整数手、保证金、止损重试、AI 月池和成本联动。
- 运行后判断：有限。若 C 没有改善路径稳健性，应停止该组合落地，回到新 PIT 源或账户外层结构。
- 原因：真实引擎结果能判断 Stage057 最强代理是否能落地，而不是只看 closed-lot 代理曲线。
