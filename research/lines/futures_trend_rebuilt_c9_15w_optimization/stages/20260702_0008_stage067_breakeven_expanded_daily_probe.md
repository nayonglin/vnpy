# Stage067 - 保本退出扩展日级压力起点验证

- line_id：`futures_trend_rebuilt_c9_15w_optimization`
- 当前模式：`day`
- 记录时间：`2026-07-02T00:08:09 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：Stage066 保本真引擎扩样本验证，不改官方实盘配置。
- 是否重要突破：`否`
- 是否触发A/B：`是`

## 外部调研与判断

- 参考资料：Backtrader stop order、NautilusTrader event cycle、pysystemtrade、Rob Carver dynamic trend following。
- 我的判断：保本退出必须显式事件顺序；本阶段只扩样本，不扫 `1R/2R/4R` 或锁盈档位。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_optimization/tools/stage067_breakeven_expanded_daily_probe.py`
- 新增测试：`tests/test_rebuilt_c9_stage067_expanded_breakeven_probe.py`
- 修改脚本：无正式策略脚本修改。
- 删除脚本：无。
- 新增参数：无新交易参数，复用 Stage066 `stage066_breakeven_trigger_r=1.0`。
- 修改参数：无正式参数修改。
- 删除参数：无。

## 回测/归因参数

- A：`stage013_expanded_baseline`。
- C：`stage067_breakeven_after_1r`。
- 样本：Stage042 扩展日级压力起点 `32` 个。
- 结束日期：`2026-06-30`。
- 账户规模：`150,000`。

## 结果

- 总收益：A 最小 `55.0954%`；C 最小 `58.8787%`
- 最大回撤：A 最差 `-45.8976%`；C 最差 `-46.0359%`
- Sharpe：A 中位 `0.8136`；C 中位 `0.8072`
- 严格负窗口：A `682970`；C `769537`
- 80% 收益保留：`26/32`
- AI 未启用月份：`0`
- 总滑点、总交易次数、胜率：见 summary 输出。

## 输出文件

- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage067_breakeven_expanded_daily_probe/rebuilt_c9_stage067_breakeven_expanded_daily_probe_report_stage067_breakeven_expanded_daily_probe_v1.md`
- summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage067_breakeven_expanded_daily_probe/rebuilt_c9_stage067_breakeven_expanded_daily_probe_summary_stage067_breakeven_expanded_daily_probe_v1.csv`
- curves：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage067_breakeven_expanded_daily_probe/rebuilt_c9_stage067_breakeven_expanded_daily_probe_curves_stage067_breakeven_expanded_daily_probe_v1.csv`
- ai_audit：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage067_breakeven_expanded_daily_probe/rebuilt_c9_stage067_breakeven_expanded_daily_probe_ai_audit_stage067_breakeven_expanded_daily_probe_v1.csv`
- goal_aggregate：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage067_breakeven_expanded_daily_probe/rebuilt_c9_stage067_breakeven_expanded_daily_probe_goal_aggregate_stage067_breakeven_expanded_daily_probe_v1.csv`

## 结论

- 本阶段结论：`stage067_expanded_not_enough_stop_no_param_rescue`。
- 下一步：停止保本 stop 路线参数化救援；转更强 PIT 信息源、账户外层或高质量信号识别。

## 过拟合反思

- 运行前判断：有风险但可控。Stage066 已有压力集改善，本阶段只扩样本，不调参。
- 运行后判断：否。本阶段没有救参；若继续改保本阈值或筛样本就是过拟合。

## 继续价值反思

- 运行前判断：有。必须确认 Stage066 改善能否穿越更多日级压力起点。
- 运行后判断：有限。若扩样本无法保持左尾改善，该保本形状不应继续交易化。
