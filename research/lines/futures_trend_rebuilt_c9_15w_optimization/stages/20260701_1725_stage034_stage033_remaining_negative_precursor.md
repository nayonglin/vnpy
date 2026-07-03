# Stage034 - Stage033 剩余负窗口前置信号归因

- 记录时间：`2026-07-01T17:25`
- line_id：`futures_trend_rebuilt_c9_15w_optimization`
- model_tag：`stage034_stage033_remaining_negative_precursor_v1`
- 是否重要突破版本：`否`
- 决策：`stage034_known_regime_precursor_persists_hard_gate_already_failed`

## 本次版本变更

- 新增工具：`research/lines/futures_trend_rebuilt_c9_15w_optimization/tools/stage034_stage033_remaining_negative_precursor.py`。
- 使用 Stage033 proxy 曲线，将 `2020-01-01` 到 `2025-06-30` 每个可审计起点压成一行，标记未来任意 `>365` 天结束是否出现负收益。
- 合并当时可见的账户状态、市场 regime、AI 月度信心/共识度；不使用未来 PnL 或事后标签作为条件。

## 新增参数

- `OBJECTIVE_START_MIN=2020-01-01`
- `OBJECTIVE_START_MAX=2025-06-30`
- `MIN_PERIOD_DAYS=365`

## 结果

- 可审计起点行：`13267`。
- 严格负起点数：`2122`。
- 严格负起点率：`15.9946%`。
- 最差未来任意 `>1` 年收益：`-42.3664%`。
- 最强条件：`market_high_vol_high_eff`，负起点率 `66.2791%`，lift `4.1438`，样本 `946`。
- 最强分桶：`joint_regime=high_vol_high_eff`，负起点率 `66.2791%`，lift `4.1438`，样本 `946`。

## 调研与判断结论

- 调研结论：趋势跟随稳健性更依赖市场组合、horizon 和风险预算，而不是单一固定加仓标签；因此本阶段做 causal precursor 审计。
- 判断结论：`stage034_known_regime_precursor_persists_hard_gate_already_failed`。当前只读归因不能声明目标达成，也不能直接上线。

## 反思

- 运行前是否过拟合：否。Stage034 不改策略、不扫参数，只解释 Stage033 剩余严格负窗口的前置信号。
- 运行前是否有价值继续：有。Stage033 已确认早段质量加风险有增益但不达标，必须定位剩余左尾是否有稳定 selector。
- 运行后是否过拟合：否。本阶段没有把最高 lift 条件直接变成交易规则；若下一步按局部年份/source 调条件会过拟合。
- 运行后是否有价值继续：有，但不是重复 high_vol_high_eff hard gate。Stage034 证明 Stage033 后剩余左尾仍由同一坏环境前兆主导，而 Stage024/025/026 已反证单一暂停规则；下一步必须拆分该 regime 内右尾错杀与真坏窗口，或转外生信息源。

## 后续规划和 TODO

- 若前兆具备足够样本和跨 source 稳定性，下一阶段只能做冻结真实引擎验证，不能微调年份/source/阈值。
- 若前兆不稳定，转外生信息源或账户外层资金安排。

## 输出文件

- start_outcomes: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage034_stage033_remaining_negative_precursor/rebuilt_c9_stage034_stage033_remaining_negative_precursor_start_outcomes_stage034_stage033_remaining_negative_precursor_v1.csv`
- feature_matrix: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage034_stage033_remaining_negative_precursor/rebuilt_c9_stage034_stage033_remaining_negative_precursor_feature_matrix_stage034_stage033_remaining_negative_precursor_v1.csv`
- bucket_summary: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage034_stage033_remaining_negative_precursor/rebuilt_c9_stage034_stage033_remaining_negative_precursor_bucket_summary_stage034_stage033_remaining_negative_precursor_v1.csv`
- condition_summary: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage034_stage033_remaining_negative_precursor/rebuilt_c9_stage034_stage033_remaining_negative_precursor_condition_summary_stage034_stage033_remaining_negative_precursor_v1.csv`
- stability_summary: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage034_stage033_remaining_negative_precursor/rebuilt_c9_stage034_stage033_remaining_negative_precursor_stability_summary_stage034_stage033_remaining_negative_precursor_v1.csv`
- chart: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage034_stage033_remaining_negative_precursor/rebuilt_c9_stage034_stage033_remaining_negative_precursor_chart_stage034_stage033_remaining_negative_precursor_v1.png`
- decision: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage034_stage033_remaining_negative_precursor/rebuilt_c9_stage034_stage033_remaining_negative_precursor_decision_stage034_stage033_remaining_negative_precursor_v1.json`
- report: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage034_stage033_remaining_negative_precursor/rebuilt_c9_stage034_stage033_remaining_negative_precursor_report_stage034_stage033_remaining_negative_precursor_v1.md`
