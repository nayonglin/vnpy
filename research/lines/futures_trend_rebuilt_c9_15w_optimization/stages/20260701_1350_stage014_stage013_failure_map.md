# Stage014 Stage013 剩余负窗口失败地图

- 记录时间：`2026-07-01 13:50 CST`
- line_id：`futures_trend_rebuilt_c9_15w_optimization`
- model_tag：`stage014_stage013_failure_map_v1`
- 阶段性质：只读归因；不改策略、不连接 CTP、不调用下单 API。
- 是否重要突破版本：`否`
- 决策：`stage014_readonly_failure_map_stage013_not_goal_met_next_needs_confirmation_or_jd_non_overlapping_candidate`

## 本次目标

Stage013 已显著改善回撤，但严格任意结束日 `>1` 年目标仍失败。本阶段不直接写新规则，先按 systematic-debugging 思路定位剩余负窗口结构，避免继续用阈值、品种、方向或日期补丁救参。

## 外部调研判断

- Trend-following CTA 仓位研究显示，仓位方法可以改善收益/风险，但评估必须同时看风险、收益、实现复杂度，不能只靠提高或降低杠杆伪造改善。
- 相关论文/实践资料对 Target Volatility、Max Drawdown Minimize、Dynamic Stop Lock-In 等方向更支持，而不是单品种/单年份黑名单。
- GitHub 上可参考的 trend-following 项目多是简化版均线/波动过滤，适合借鉴“波动和账户状态 gating”的形状，不适合作为当前 C9 多品种引擎的直接逻辑。

## 数据和输出

- Stage013 决策文件：`research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage013_account_state_pilot_gate_engine/rebuilt_c9_stage013_account_state_pilot_gate_engine_decision_stage013_account_state_pilot_gate_engine_v1.json`
- 本阶段输出目录：`research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage014_stage013_failure_map/`
- 主要输出：
  - `rebuilt_c9_stage014_variant_compare_stage013_failure_map_v1.csv`
  - `rebuilt_c9_stage014_worst_window_clusters_stage013_failure_map_v1.csv`
  - `rebuilt_c9_stage014_worst_event_overlay_stage013_failure_map_v1.csv`
  - `rebuilt_c9_stage014_fixed_horizon_negative_rate_stage013_failure_map_v1.csv`
  - `rebuilt_c9_stage014_fixed_horizon_all_stage013_failure_map_v1.csv`
  - `rebuilt_c9_stage014_entry_by_month_stage013_failure_map_v1.csv`
  - `rebuilt_c9_stage014_summary_compare_stage013_failure_map_v1.csv`
  - `rebuilt_c9_stage014_failure_map_chart_stage013_failure_map_v1.png`
  - `rebuilt_c9_stage014_decision_stage013_failure_map_v1.json`

## 核心结果

- Stage006 base 严格任意结束日 `>1` 年负窗口：`444,448`，最差 `-55.2146%`。
- Stage008 proxy 严格任意结束日 `>1` 年负窗口：`427,688`，最差 `-54.2509%`。
- Stage013 engine 严格任意结束日 `>1` 年负窗口：`330,947`，最差 `-43.7940%`。
- Stage013 相比 Stage008 proxy：负窗口减少 `96,741` 个，最差收益改善 `10.4569pp`。
- 到 `2026-06-30` 口径：Stage013 负窗口 `0`，最差 `26.6753%`。
- Stage013 top500 最差窗口中，`pilot_events_during_window` 中位数 `17`，且 `500/500` 都有 Stage013 触发，说明小风险试探确实生效，但不足以清零剩余 1-2 年左尾。

## 最差窗口结构

最差窗口仍高度集中在 `2022-07 -> 2023-07/2023-10`：

| source_start_month | window_start_month | window_end_month | worst_sample_count | min_return_pct | median_return_pct | first_start_date | last_start_date | first_end_date | last_end_date |
| --- | --- | --- | ---: | ---: | ---: | --- | --- | --- | --- |
| 2022-07 | 2022-07 | 2023-07 | 37 | -43.7940 | -29.8853 | 2022-07-12 | 2022-07-29 | 2023-07-17 | 2023-07-31 |
| 2021-07 | 2022-07 | 2023-10 | 42 | -39.4246 | -30.8216 | 2022-07-12 | 2022-07-29 | 2023-10-19 | 2023-10-23 |
| 2021-07 | 2021-10 | 2023-10 | 30 | -35.2888 | -28.5744 | 2021-10-18 | 2021-10-29 | 2023-10-19 | 2023-10-23 |
| 2021-07 | 2022-03 | 2023-10 | 66 | -34.9430 | -28.2549 | 2022-03-02 | 2022-03-31 | 2023-10-19 | 2023-10-23 |
| 2022-01 | 2022-07 | 2023-07 | 19 | -34.0999 | -26.5506 | 2022-07-14 | 2022-07-22 | 2023-07-17 | 2023-07-25 |

固定周期口径：

| horizon_days | window_count | negative_count | negative_rate_pct | min_return_pct |
| ---: | ---: | ---: | ---: | ---: |
| 366 | 13,267 | 1,717 | 12.9419 | -43.7940 |
| 540 | 11,572 | 1,498 | 12.9450 | -36.8200 |
| 730 | 9,777 | 477 | 4.8788 | -33.6647 |
| 1095 | 6,768 | 14 | 0.2069 | -12.0068 |

这说明剩余问题主要是 `1-2` 年恢复段，而不是长期右尾完全失效。

## 对 Stage013 的判断

- Stage013 方向有价值：回撤明显改善，严格负窗口少了约 `22.62%`，全周期收益保留仍通过。
- Stage013 不足以达标：最差窗口仍在同一段；top500 最差窗口均有 pilot gate 触发，说明单纯“深回撤低活跃时降到 1 手”不是充分条件。
- 下一步不应该扫 `30%` 回撤阈值、`active<=1/2` 或 `1/2 手`，这会直接走向过拟合。

## 下一步建议

1. Stage015 可以做两个只读归因：
   - Stage013 触发后的首个可见确认信号是否存在，例如入场后 `N` 日方向性、浮盈、收盘位置、波动恢复，不先加风险。
   - `jd.DCE` 是否能作为非挤占候选填补 `2022-2023` 有效趋势空窗，而不是直接塞入共享 AI topN。
2. 如果确认信号有跨窗口一致性，再写真实引擎候选：试探仓后只有出现可见确认才释放正常风险；无确认则保持小风险或退出。
3. 继续禁止：按 `2022-07` 日期、`SM`、方向、单 source_start 或单 horizon 定制规则。

## 反思

- 过拟合反思：否。本阶段只读归因，不改策略、不扫参数；结论来自 Stage013 全部曲线和密集窗口，而不是挑单个窗口。
- 继续价值反思：是。剩余失败已经从泛泛的“左尾”收敛到 `2022-2023`、`1-2` 年恢复段、Stage013 已触发但不足，这给 Stage015 的确认后风险释放和 `jd` 非挤占候选提供了明确边界。
