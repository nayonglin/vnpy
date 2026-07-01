# Stage009 新目标任意日起点密集审计

- line_id：`futures_trend_rebuilt_c9_15w_optimization`
- 当前模式：`day`
- 记录时间：`2026-07-01 12:55 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读运行曲线子周期审计；读取 Stage006/Stage008 curves，不是任意日独立冷启动回测，不改策略、不连接 CTP、不调用下单。
- 是否重要突破：否。属于目标口径收紧后的缺口定位。
- 是否触发A/B：否。

## 外部调研与判断

- 参考资料：
  - Combinatorially Symmetric Cross-Validation / PBO：`https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2326253`
  - Purged K-Fold / 金融机器学习验证框架：`https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3365282`
  - Walk-forward validation 概念：`https://en.wikipedia.org/wiki/Walk-forward_optimization`
- 我的判断：
  - 用户新目标要求 `2020-01-01` 到 `2025-06-30` 任意日起点，半年冷启动回测不够。
  - 现有曲线只能做“运行中账户子周期”审计，不能证明“任意日独立冷启动”。
  - 如果现有运行曲线子周期都还有负收益，真实每日冷启动更不能直接假定达标。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_optimization/tools/stage009_dense_start_goal_audit.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `OBJECTIVE_START_MIN=2020-01-01`
  - `OBJECTIVE_START_MAX=2025-06-30`
  - `MIN_PERIOD_CALENDAR_DAYS=366`
  - `FIXED_HORIZON_DAYS=(366, 540, 730, 1095)`
- 修改参数：无交易参数。
- 删除参数：无。

## 回测/归因参数

- 数据底座：
  - Stage006 base curves
  - Stage008 proxy curves
- 审计对象：
  - `all_trading_end_dates_gt_1y`：起点在新目标范围内，结束日为所有满足 `>365` 自然日的交易日。
  - `start_to_2026_06_30_only`：起点在新目标范围内，结束日固定为 `2026-06-30`。
  - 固定周期：`366/540/730/1095` 自然日。
- 注意：本阶段 `is_independent_daily_cold_start=false`，只是现有运行曲线上的子周期压力测试。

## 结果

- 全周期收益保留：
  - Stage008 proxy 对 Stage006 base 的全周期收益保留 `17/17` 通过 `80%`。
- 起点到 `2026-06-30`：
  - proxy 窗口数：`13,267`
  - proxy 负收益窗口：`0`
  - proxy 最低收益：`17.7001%`
  - 这个口径下，现有运行曲线子周期没有负收益。
- 任意结束日、周期 `>1` 年：
  - base 窗口数：`7,215,647`
  - base 负收益窗口：`444,448`
  - proxy 窗口数：`7,215,647`
  - proxy 负收益窗口：`427,688`
  - proxy 最差收益：`-54.2509%`
  - 负窗口主要集中在 `2022-07-15 -> 2023-07-17/18/24` 附近。
- 结论：
  - 如果用户目标解释为“任意日起点持有到 2026-06-30”，Stage008 代理在现有运行曲线子周期上通过。
  - 如果严格解释为“任意日起点 + 任意结束日，只要周期 >1 年都正收益”，Stage008 代理明显未达标。
  - 无论哪种解释，本阶段仍不是每日独立冷启动证明。

## 输出文件

- report：`research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage009_dense_start_goal_audit/rebuilt_c9_stage009_dense_start_goal_audit_report_stage009_dense_start_goal_audit_v1.md`
- aggregate：`research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage009_dense_start_goal_audit/rebuilt_c9_stage009_dense_start_goal_audit_aggregate_stage009_dense_start_goal_audit_v1.csv`
- to_final_windows：`research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage009_dense_start_goal_audit/rebuilt_c9_stage009_dense_start_goal_audit_to_final_windows_stage009_dense_start_goal_audit_v1.csv`
- fixed_horizon_windows：`research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage009_dense_start_goal_audit/rebuilt_c9_stage009_dense_start_goal_audit_fixed_horizon_windows_stage009_dense_start_goal_audit_v1.csv`
- worst_windows：`research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage009_dense_start_goal_audit/rebuilt_c9_stage009_dense_start_goal_audit_worst_windows_stage009_dense_start_goal_audit_v1.csv`
- retention：`research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage009_dense_start_goal_audit/rebuilt_c9_stage009_dense_start_goal_audit_full_cycle_retention_stage009_dense_start_goal_audit_v1.csv`
- chart：`research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage009_dense_start_goal_audit/rebuilt_c9_stage009_dense_start_goal_audit_goal_audit_chart_stage009_dense_start_goal_audit_v1.png`

## 结论

- 本阶段结论：更新后的目标尚未完成。Stage008 保留了全周期收益优势，并且“任意目标起点到 2026-06-30”运行曲线子周期无负收益；但严格 `任意起点 + 任意结束日 + >1年` 仍存在大量负窗口，最坏约 `-54.25%`。
- 是否进入下一步：进入。
- 下一步：
  - 先和用户口径对齐：目标中的“回测周期大于一年”是否固定结束到 `2026-06-30`，还是任意结束日。
  - 若固定到 `2026-06-30`，下一步做每日独立冷启动抽样/批量真回测验证。
  - 若任意结束日都必须正收益，下一步不能只加风险；需要账户层保护、左尾生存线或暂停入场/降低风险的真实引擎。

## 过拟合反思

- 运行前判断：否。目标变更后先补审计口径，不改策略、不调参数，只测所有现有曲线子周期。
- 运行后判断：否。本阶段只读审计，发现负窗口后不反向调标签或比例。
- 原因：阶段目的是暴露口径缺口，而不是救参。

## 继续价值反思

- 运行前判断：是。新目标要求任意日起点，半年起点结果不够，必须先定位密集区间缺口。
- 运行后判断：有。Stage008 仍保留收益优势，但密集 `>1` 年子周期还有负收益，下一步要针对左尾目标重构真实引擎或账户层保护。
- 原因：当前方向对收益增强有效，但不是左尾正收益保证；目标需要额外风险治理结构。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：是。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段不是正式候选或重要合入。
