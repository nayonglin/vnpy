# Stage086 三版本表现可视化

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：day
- 记录时间：2026-05-27 16:24 CST
- 阶段性质：只读可视化；基于 Stage083 日度权益和 Stage085 任意启动/持有期输出生成图表
- 是否重要突破：否，展示增强。用于更直观看清 `78-1`、`Stage079`、`纯C3` 的收益、回撤和持有体验差异。
- 是否触发A/B：否。本阶段没有新候选或策略接入。

## 外部调研与判断

- 本阶段没有新增策略调研；沿用 Stage085 对 rolling / walk-forward 持有窗口和收益/回撤分布的判断。
- 图表重点不展示单一收益排名，而展示权益曲线、全程水下回撤、固定持有期体验、全量起止区间热力图和坏运气启动窗口。
- 判断：这比单张指标表更适合回答“任何时候启动、启动多久，我的持有体验如何”。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/visualize_qmt_roll_stage386_three_version_charts.py`
- 修改策略脚本：无。
- 新增参数：无策略参数；图表固定使用 Stage085 的持有期和分桶输出。
- 修改参数：无。
- 删除参数：无。

## 输入数据

- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage383_three_version_deep_audit_daily_stage383_three_version_deep_audit_v1.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage385_any_start_holding_experience_fixed_horizon_stage385_any_start_holding_experience_v1.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage385_any_start_holding_experience_all_interval_buckets_stage385_any_start_holding_experience_v1.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage385_any_start_holding_experience_worst_starts_stage385_any_start_holding_experience_v1.csv`

## 输出图表

- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage386_three_version_visual_charts/stage386_equity_drawdown.png`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage386_three_version_visual_charts/stage386_fixed_horizon_experience.png`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage386_three_version_visual_charts/stage386_interval_bucket_heatmaps.png`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage386_three_version_visual_charts/stage386_worst_start_windows.png`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage386_three_version_visual_charts/stage386_three_version_visual_dashboard.html`

## 图表结论

- 权益曲线：纯C3长期收益最高，Stage079略低，78-1早期强但后续水下体验更差。
- 水下回撤：Stage079 全程压在 `-30%` 以内；纯C3和78-1都会穿越 `-30%` 红线。
- 固定持有期：1个月/3个月三者都不舒服；6个月后 Stage079 的正收益概率明显提升，1年后体验显著改善。
- 任意起止区间热力图：Stage079 的收益不是最高，但破30回撤概率在全部分桶中为 `0%`；纯C3从中长期开始破30概率明显抬升，78-1更严重。
- 坏运气启动窗口：Stage079 在最差窗口下仍不是最高收益，但最少穿越心理/风控红线。

## 过拟合与继续价值反思

- 运行前判断：否。本阶段只是对已有审计输出可视化，不改规则、不筛选窗口、不调参数。
- 运行后判断：否。图表没有产生新策略结论，只让 Stage085 的统计结论更清晰。
- 运行前判断：有价值。用户希望更直观看三版本表现，图表比表格更能展示持有体验。
- 运行后判断：有价值。可视化进一步确认 Stage079 是正常成本下更适合持有体验的候选，但不能改变其高滑点和路径重排压力边界。

## 后续规划和 TODO

- 若继续 Stage079：进入 forward / 影子盘持有体验监控，定期更新这四类图表。
- 若要求短持有期也舒服：不要继续调 C3 现金小数，需寻找低相关收益源或降低趋势暴露。
