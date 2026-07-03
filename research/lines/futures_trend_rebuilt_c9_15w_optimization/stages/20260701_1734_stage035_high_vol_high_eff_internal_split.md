# Stage035 - high_vol_high_eff 内部右尾/坏窗口拆解

- 记录时间：`2026-07-01T17:34`
- line_id：`futures_trend_rebuilt_c9_15w_optimization`
- 当前模式：`day`
- model_tag：`stage035_high_vol_high_eff_internal_split_v1`
- 阶段性质：只读归因，不改策略。
- 是否重要突破版本：`否`
- 是否触发A/B：`否`
- 决策：`stage035_internal_overheat_vs_recovery_split_found_needs_engine_validation`

## 外部调研与判断

- 参考资料：Man Group trend-following market mix、Man AHL need for speed、Hurst/Ooi/Pedersen century trend-following、Quantpedia time-series momentum、Return Stacked managed futures。
- 我的判断：趋势跟随优化不能简单截断右尾；本阶段必须先拆清楚 `high_vol_high_eff` 中的过热回吐和恢复右尾。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_optimization/tools/stage035_high_vol_high_eff_internal_split.py`。
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：无交易参数；只读阈值用于归因条件标签。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：沿用 Stage034 特征矩阵，起点覆盖 `2020-01-01` 至 `2025-06-30`，终点为重建 C9 可用曲线末端。
- 账户规模：Stage033/重建 C9 15万 proxy 曲线口径。
- 成本口径：沿用 Stage033 曲线成本，不新增成本假设。
- 样本过滤：仅 `joint_regime=high_vol_high_eff`。
- 策略/归因口径：只读拆解，不生成订单，不接 CTP。

## 结果

- 期末权益：不适用，本阶段不是新增策略回测。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：沿用 Stage033 曲线；本阶段不新增滑点。
- 总交易次数：不适用。
- 胜率：不适用。
- 其他关键指标：`high_vol_high_eff` 样本 `946`，严格负 `627`，负率 `66.2791%`；最强坏窗口条件 `overheat_63d_gt20_consensus_1_3` 负率 `100.0000%`；最强恢复条件 `recovery_dd_le_-30` 负率 `0.0000%`。

## 输出文件

- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage035_high_vol_high_eff_internal_split/rebuilt_c9_stage035_high_vol_high_eff_internal_split_report_stage035_high_vol_high_eff_internal_split_v1.md`
- summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage035_high_vol_high_eff_internal_split/rebuilt_c9_stage035_high_vol_high_eff_internal_split_condition_summary_stage035_high_vol_high_eff_internal_split_v1.csv`
- orders：不适用。
- daily：不适用。
- quality：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage035_high_vol_high_eff_internal_split/rebuilt_c9_stage035_high_vol_high_eff_internal_split_contrast_summary_stage035_high_vol_high_eff_internal_split_v1.csv`

## 结论

- 本阶段结论：`stage035_internal_overheat_vs_recovery_split_found_needs_engine_validation`。
- 是否进入下一步：`是`，但只能进入冻结规则真实引擎验证，不能按单一年份/source 继续微调。
- 下一步：将过热条件做成小手数/暂停候选，同时设置恢复右尾保护条件，验证是否能减少严格负窗口且保留 Stage033 全周期收益。

## 过拟合反思

- 运行前判断：否。Stage035 不回测新策略、不扫参数，只在 Stage034 已冻结特征矩阵中拆解同一个已知坏 regime；条件均来自已有账户、市场和 AI 月度字段。
- 运行后判断：否。Stage035 仍是只读拆解，没有把最高胜率/败率分桶直接转成规则；但如果下一步按 2022 年或 warmup 字段单独调参，就会明显过拟合。
- 原因：本阶段没有修改交易规则；风险在于下一步若按最高 lift 分桶无约束组合，会变成事后拟合。

## 继续价值反思

- 运行前判断：有。Stage024/025/026 已反证 high_vol_high_eff 一刀切暂停，Stage034 又确认剩余左尾集中在该 regime；继续价值在于分清该 regime 内哪些是过热回吐、哪些是恢复右尾。
- 运行后判断：有。结果把 high_vol_high_eff 拆成两类：前期账户/holding PnL 已大幅扩张的过热回吐区，以及 63日已大跌或深回撤后的恢复右尾区；下一步应做冻结规则真实引擎验证，重点保护恢复右尾。
- 原因：已找到比 high_vol_high_eff 一刀切更接近本质的内部结构，值得做冻结真实引擎验证。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage035 结论。
- 是否更新 `research/registry.md`：是，更新当前线最新阶段。
- 是否追加根目录 `memory.md/back_log.md`：只追加 `back_log.md` 重要摘要，不追加 `memory.md`。

## 全量输出路径

- high_vol_rows: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage035_high_vol_high_eff_internal_split/rebuilt_c9_stage035_high_vol_high_eff_internal_split_high_vol_rows_stage035_high_vol_high_eff_internal_split_v1.csv`
- bucket_summary: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage035_high_vol_high_eff_internal_split/rebuilt_c9_stage035_high_vol_high_eff_internal_split_bucket_summary_stage035_high_vol_high_eff_internal_split_v1.csv`
- condition_summary: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage035_high_vol_high_eff_internal_split/rebuilt_c9_stage035_high_vol_high_eff_internal_split_condition_summary_stage035_high_vol_high_eff_internal_split_v1.csv`
- contrast_summary: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage035_high_vol_high_eff_internal_split/rebuilt_c9_stage035_high_vol_high_eff_internal_split_contrast_summary_stage035_high_vol_high_eff_internal_split_v1.csv`
- stability_summary: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage035_high_vol_high_eff_internal_split/rebuilt_c9_stage035_high_vol_high_eff_internal_split_stability_summary_stage035_high_vol_high_eff_internal_split_v1.csv`
- chart: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage035_high_vol_high_eff_internal_split/rebuilt_c9_stage035_high_vol_high_eff_internal_split_chart_stage035_high_vol_high_eff_internal_split_v1.png`
- decision: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage035_high_vol_high_eff_internal_split/rebuilt_c9_stage035_high_vol_high_eff_internal_split_decision_stage035_high_vol_high_eff_internal_split_v1.json`
- report: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage035_high_vol_high_eff_internal_split/rebuilt_c9_stage035_high_vol_high_eff_internal_split_report_stage035_high_vol_high_eff_internal_split_v1.md`
