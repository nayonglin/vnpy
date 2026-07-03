# Stage066 - 保本退出真引擎压力验证

- line_id：`futures_trend_rebuilt_c9_15w_optimization`
- 当前模式：`day`
- 记录时间：`2026-07-01T23:30:27 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：冻结真实引擎候选 A/C 压力验证，不改官方实盘配置。
- 是否重要突破：`是`
- 是否触发A/B：`是`

## 外部调研与判断

- 参考资料：Backtrader stop order/stop-loss examples、NautilusTrader event cycle、pysystemtrade。
- 我的判断：保本退出必须显式事件顺序；本阶段只验真 Stage065 `optimistic_breakeven_after_1r`，不扫 R 倍数或锁盈档位。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_optimization/tools/stage066_breakeven_after_1r_true_engine.py`
- 新增测试：`tests/test_rebuilt_c9_stage066_breakeven_engine.py`
- 修改脚本：无正式策略脚本修改。
- 删除脚本：无。
- 新增参数：`BREAKEVEN_TRIGGER_R=1.0`、`enable_stage066_breakeven_after_1r=True`。
- 修改参数：无正式参数修改。
- 删除参数：无。

## 回测/归因参数

- A：`stage013_pressure_baseline`，Stage013。
- C：`stage066_breakeven_after_1r`，Stage013 + `+1R` 后保本 stop。
- 样本：Stage054/055 去重左尾压力日级起点 `9` 个。
- 结束日期：`2026-06-30`。
- 账户规模：`150,000`。
- 事件顺序：同日同时触发 `+1R` 与回踩入场价时，不假设有利先后，保本 stop 延迟到下一根日 K。

## 结果

- 总收益：Stage013 最小 `55.0954%`；Stage066 最小 `102.4221%`
- 最大回撤：Stage013 最差 `-37.7002%`；Stage066 最差 `-36.5167%`
- Sharpe：Stage013 中位 `0.7584`；Stage066 中位 `0.7156`
- 严格负窗口：Stage013 `81351`；Stage066 `69937`
- 80% 收益保留：`9/9`
- 保本事件：`1124`；实际应用 `550`；同日歧义延迟 `574`。
- 总滑点、总交易次数、胜率：见 summary 输出。

## 输出文件

- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage066_breakeven_after_1r_true_engine/rebuilt_c9_stage066_breakeven_after_1r_true_engine_report_stage066_breakeven_after_1r_true_engine_v1.md`
- summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage066_breakeven_after_1r_true_engine/rebuilt_c9_stage066_breakeven_after_1r_true_engine_summary_stage066_breakeven_after_1r_true_engine_v1.csv`
- curves：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage066_breakeven_after_1r_true_engine/rebuilt_c9_stage066_breakeven_after_1r_true_engine_curves_stage066_breakeven_after_1r_true_engine_v1.csv`
- breakeven_events：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage066_breakeven_after_1r_true_engine/rebuilt_c9_stage066_breakeven_after_1r_true_engine_breakeven_events_stage066_breakeven_after_1r_true_engine_v1.csv`
- goal_aggregate：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage066_breakeven_after_1r_true_engine/rebuilt_c9_stage066_breakeven_after_1r_true_engine_goal_aggregate_stage066_breakeven_after_1r_true_engine_v1.csv`

## 结论

- 本阶段结论：`stage066_pressure_improves_left_tail_expand_validation`。
- 下一步：扩到 Stage042/053 级别更多压力起点，再决定是否做全量日级密集回测。

## 过拟合反思

- 运行前判断：有风险但可控。保本规则来自 Stage065 proxy，但冻结为一个低自由度结构，不按品种/日期/方向救参。
- 运行后判断：暂不判定过拟合。规则未改参且压力集改善，但还没有跨样本证明。

## 继续价值反思

- 运行前判断：有。Stage065 closed-lot 上界通过，需要真引擎验真。
- 运行后判断：有。压力左尾改善且收益保留过关，值得扩样本验证。
