# Stage023 - 剩余负窗口前置信号只读归因

## 变更时间

- 2026-07-01T15:23:28 CST

## 是否重要突破版本

- 否。只读归因，不是真实引擎候选，不改线上。

## 本次版本改动内容

- 新增工具：`research/lines/futures_trend_rebuilt_c9_15w_optimization/tools/stage023_negative_window_precursor_attribution.py`
- 使用 Stage021 combo 曲线，将每个 `2020-01-01` 到 `2025-06-30` 的可审计起点压成一行，标记未来任意 `>365` 天结束是否出现负收益。
- 合并当时可见的账户状态、市场 regime、AI 月度信心/共识度；不使用 `future_net_pnl_60d`、未来 rank 或事后标签作为条件。

## 新增参数

- `OBJECTIVE_START_MIN=2020-01-01`
- `OBJECTIVE_START_MAX=2025-06-30`
- `MIN_PERIOD_DAYS=365`

## 修改参数

- 无。

## 删除参数

- 无。

## 新增回测结果

- 可审计起点行：`13267`
- 严格负起点数：`2071`
- 严格负起点率：`15.6102%`
- 最差未来任意 `>1` 年收益：`-42.0358%`
- 最强条件：`loss_and_high_vol_low_eff`，负起点率 `36.7470%`，lift `2.3540`，样本 `664`
- 最强分桶：`joint_regime=high_vol_high_eff`，负起点率 `66.2791%`，lift `4.2459`，样本 `946`

## 修改回测结果

- 无。

## 删除回测结果

- 无。

## 指标占位

- 期末权益：只读归因，不适用。
- 总收益：只读归因，不适用。
- 最大回撤：只读归因，不适用。
- Sharpe：只读归因，不适用。
- 总滑点：不新增交易，不适用。
- 总交易次数：不新增交易，不适用。
- 胜率：不新增交易，不适用。

## 调研与判断结论

- 调研结论：趋势/CTA 风控资料支持账户层或 regime 层风控，但 Stage022 已显示锁盈会压右尾；Stage023 改为审计更早的因果状态。
- 判断结论：`stage023_precursor_attribution_only_not_candidate`。当前只得到候选前兆，不足以声明达成用户目标，也不能直接上线。

## 过拟合与继续价值反思

- 运行前是否过拟合：否。本阶段不改参数、不晋级最优组合，只做前置信号归因。
- 运行前是否有价值继续：有。当前失败项是严格任意结束日左尾，必须找到比锁盈更早的风险状态。
- 运行后是否过拟合：否。本阶段没有把最高 lift 条件当作规则；直接上线会过拟合。
- 运行后是否有价值继续：有，但只适合作为下一阶段真实引擎候选的筛选器。需要验证这些前兆是否跨 source 稳定，且不会像 Stage018/022 一样砍掉早期右尾。

## 后续规划和 TODO

- 若某个前兆条件具备足够样本、跨 source 稳定且不是简单砍右尾，下一阶段才能写真实引擎级暂停/恢复候选。
- 不允许基于本阶段直接扫阈值、品种、方向、日期或最强条件的微调。

## 输出文件

- `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage023_negative_window_precursor_attribution/rebuilt_c9_stage023_negative_window_precursor_attribution_report_stage023_negative_window_precursor_attribution_v1.md`
- `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage023_negative_window_precursor_attribution/rebuilt_c9_stage023_negative_window_precursor_attribution_decision_stage023_negative_window_precursor_attribution_v1.json`
- `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage023_negative_window_precursor_attribution/rebuilt_c9_stage023_negative_window_precursor_attribution_chart_stage023_negative_window_precursor_attribution_v1.png`
- `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage023_negative_window_precursor_attribution/rebuilt_c9_stage023_negative_window_precursor_attribution_stability_summary_stage023_negative_window_precursor_attribution_v1.csv`
