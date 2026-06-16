# Stage074 Stage899 C9 逐月起点首次转正等待期审计

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：`2026-06-15 19:44`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读多起点回测；不改 C9 策略参数、不连接 CTP、不调用下单。
- 是否重要突破：否，属于用户体验/路径稳健性统计。
- 是否触发A/B：否。Stage898 数据无偏差审计未通过，C9 不进入正式候选或 A/B。

## 外部调研与判断

- 参考资料：walk-forward / rolling-start validation 的核心价值是暴露路径依赖、冷启动差异和等待期；这类统计不能替代数据源、撮合和交易成本审计。
- 我的判断：本阶段回答“从任意月份开始后多久会转正”，不是证明 C9 无偏差。Stage898 仍有 `8` 笔 C9 开仓 entry-day 分钟K缺口，所有 C9 结论都必须带这个可信边界。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage899_c9_monthly_time_to_positive.py`
- 修改脚本：无策略脚本修改。
- 删除脚本：无
- 新增参数：无策略参数；脚本支持 `STAGE899_WORKERS`，默认 `1`，避免多进程初始化读 CSV 竞争。
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：每月独立起点 `2018-01-01 -> 2026-05-01`，统一跑到 `2026-05-29`。
- 账户规模：C9 `300,000`
- 成本口径：沿用仓库 vn.py 组合回测费率、滑点、保证金口径。
- 样本过滤：`all_monthly_starts=101`；`mature_1y_or_more=89`。
- 策略/归因口径：C9 = Stage847 `C4 + 0.5R stop + 原入场价 reclaim 后重试一次`；使用 Stage861 full-minute 口径。
- 转正定义：起点后首次 `rebased_nav > 1.0`；若到 `2026-05-29` 未发生，则记为 unresolved。

## 结果

- 全部逐月起点：
  - 样本数：`101`
  - 曾经转正：`99`
  - 未转正：`2`
  - 空结果窗口：`1`（`2026-05` 极短窗口 empty daily result）
  - 曾转正比例：`98.0198%`
  - 最长首次转正等待：`158` 日历日 / `108` 交易日 / `5.191` 月
  - 最长等待窗口：`2018_03_to_2026_05_29`
  - 首次转正日期：`2018-08-06`
  - 等待期中位数：`14` 日历日
  - 等待期 P90：`72.4` 日历日
  - 最新期末仍为正收益：`92/101`
  - 期末收益率中位数：`619.9222%`
  - 期末最小收益率：`-10.4448%`
  - 最差回撤：`-56.6137%`
- 成熟样本（起点到终点至少 1 年）：
  - 样本数：`89`
  - 曾经转正：`89/89`
  - 未转正：`0`
  - 最长首次转正等待：`158` 日历日 / `108` 交易日 / `5.191` 月
  - 等待期中位数：`14` 日历日
  - 等待期 P90：`75.8` 日历日
  - 期末收益率全部为正：`89/89`
  - 期末最小收益率：`72.5755%`
  - 期末收益率中位数：`1315.5930%`
- 未转正窗口：
  - `2026_04_to_2026_05_29`：截至终点已过 `58` 日历日，期末收益 `-6.86%`
  - `2026_05_to_2026_05_29`：极短窗口 empty result，截至终点 `28` 日历日，期末收益 `0.0%`
- Top 等待窗口：
  - `2018-03`：`158` 日历日 / `108` 交易日
  - `2018-04`：`124` 日历日 / `85` 交易日
  - `2019-04`：`113` 日历日 / `77` 交易日
  - `2022-12`：`111` 日历日 / `74` 交易日
  - `2024-06`：`109` 日历日 / `75` 交易日

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage899_c9_monthly_time_to_positive_report_stage899_c9_monthly_time_to_positive_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage899_c9_monthly_time_to_positive_summary_stage899_c9_monthly_time_to_positive_v1.csv`
- curves：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage899_c9_monthly_time_to_positive_curves_stage899_c9_monthly_time_to_positive_v1.csv`
- aggregate：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage899_c9_monthly_time_to_positive_aggregate_stage899_c9_monthly_time_to_positive_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage899_c9_monthly_time_to_positive_decision_stage899_c9_monthly_time_to_positive_v1.json`

## 结论

- 本阶段结论：若只看“曾经转正”，C9 的成熟月度起点表现很强，`89/89` 都曾转正，最长等待约 `5.2` 个月；全部 `101` 个逐月起点中只有 `2026-04` 和 `2026-05` 到当前数据终点仍未转正。
- 但这不等于“体验稳定”：部分窗口转正后到 `2026-05-29` 又回到负收益，尤其 `2025-09` 至 `2026-04` 多个近期起点期末仍为负。
- 是否进入下一步：先不做策略优化；下一步仍应按 Stage898 结论补齐 8 笔 C9 entry-day 分钟K缺口，再重跑 Stage863/896/897/898/899。
- 下一步：补数重跑后，再判断 “最长转正等待期 158 天” 是否稳健。

## 过拟合反思

- 运行前判断：否。逐月起点和首次转正指标在运行前固定，没有调阈值。
- 运行后判断：本阶段没有新增过拟合；C9 自身仍有历史筛选风险。
- 原因：本阶段只读统计等待期，不改变策略，也不选择更好参数。

## 继续价值反思

- 运行前判断：有价值。它回答的是用户能否承受冷启动等待期。
- 运行后判断：有价值，但必须和 Stage898 数据缺口一起看。
- 原因：成熟样本最长等待 `158` 天提供了很直观的资金体验指标；但数据缺口未修复前，不能当成无偏差结论。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage899 等待期统计。
- 是否更新 `research/registry.md`：否，研究线不变。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段不是正式候选、路线废弃或跨线合入。
