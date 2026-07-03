# Stage040 - Stage039 负窗口迁移与 delta 归因

- 记录时间：`2026-07-01T18:32`
- line_id：`futures_trend_rebuilt_c9_15w_optimization`
- model_tag：`stage040_stage039_negative_window_delta_attribution_v1`
- 是否重要突破版本：`否`
- 决策：`stage040_stage039_added_negatives_mixed_with_denominator_effect`

## 本次版本变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_optimization/tools/stage040_stage039_negative_window_delta_attribution.py`
- 新增参数：无交易参数；诊断常量 `MIN_PERIOD_CALENDAR_DAYS=366`、`OBJECTIVE_START_MIN=2020-01-01`、`OBJECTIVE_START_MAX=2025-06-30`。
- 修改参数：无，Stage013/Stage039/官方 C9 配置未改。
- 删除参数：无。
- 新增回测结果：Stage013 vs Stage039 严格窗口迁移与 lot delta 归因；不是真实组合引擎。
- 本阶段不连接 CTP，不调用订单 API，不触发 A/B。

## 调研和判断结论

- 趋势跟随文献和 managed futures 实务更强调风险预算、波动目标和回撤承受域；Stage040 只做左尾窗口迁移诊断，不把 single signal bet sizing 当成目标解。

## 结果

- Stage013 负窗口：`330947`。
- Stage039 负窗口：`332446`。
- 净变化：`1499`。
- 修复负窗口：`6905`。
- 新增负窗口：`8404`。
- 新增负窗口里分母效应：`7731`。
- 新增负窗口里绝对期末权益更低：`673`。
- Stage013 最差收益：`-43.7940%`。
- Stage039 最差收益：`-44.1402%`。

## 分 source 摘要

| source_start_month   |   stage013_negative_count |   stage039_negative_count |   fixed_by_stage039_count |   added_negative_by_stage039_count |   added_negative_absolute_end_lt_stage013_count |   stage013_min_return_pct |   stage039_min_return_pct |
|:---------------------|--------------------------:|--------------------------:|--------------------------:|-----------------------------------:|------------------------------------------------:|--------------------------:|--------------------------:|
| 2018-01              |                     28452 |                     27895 |                      1542 |                                985 |                                              14 |                  -31.48   |                  -31.5906 |
| 2018-07              |                     28573 |                     28471 |                      1214 |                               1112 |                                              13 |                  -32.324  |                  -32.4373 |
| 2019-01              |                     31781 |                     32606 |                       543 |                               1368 |                                               0 |                  -32.8083 |                  -32.9177 |
| 2019-07              |                     28229 |                     28473 |                       683 |                                927 |                                               1 |                  -31.3609 |                  -31.478  |
| 2020-01              |                     28967 |                     29189 |                       597 |                                819 |                                               2 |                  -31.6661 |                  -31.7595 |
| 2020-07              |                     29328 |                     29611 |                       663 |                                946 |                                              13 |                  -31.3553 |                  -31.4599 |
| 2021-01              |                     36496 |                     36717 |                       848 |                               1069 |                                              17 |                  -31.8738 |                  -31.9484 |
| 2021-07              |                     75371 |                     75337 |                       549 |                                515 |                                             294 |                  -39.4246 |                  -39.0076 |
| 2022-01              |                     29096 |                     29174 |                       266 |                                344 |                                               0 |                  -34.0999 |                  -33.6491 |
| 2022-07              |                     13778 |                     14074 |                         0 |                                296 |                                             296 |                  -43.794  |                  -44.1402 |
| 2023-01              |                       876 |                       898 |                         0 |                                 22 |                                              22 |                   -8.6906 |                   -8.8514 |
| 2023-07              |                         0 |                         0 |                         0 |                                  0 |                                               0 |                    4.9842 |                    4.7976 |
| 2024-01              |                         0 |                         1 |                         0 |                                  1 |                                               1 |                    0.8339 |                   -0.058  |
| 2024-07              |                         0 |                         0 |                         0 |                                  0 |                                               0 |                    4.94   |                    5      |
| 2025-01              |                         0 |                         0 |                         0 |                                  0 |                                               0 |                   27.8887 |                   35.6794 |
| 2025-07              |                         0 |                         0 |                         0 |                                  0 |                                               0 |                           |                           |
| 2026-01              |                         0 |                         0 |                         0 |                                  0 |                                               0 |                           |                           |

## 输出

- summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage040_stage039_negative_window_delta_attribution/rebuilt_c9_stage040_stage039_negative_window_delta_attribution_summary_stage040_stage039_negative_window_delta_attribution_v1.csv`
- by_source：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage040_stage039_negative_window_delta_attribution/rebuilt_c9_stage040_stage039_negative_window_delta_attribution_by_source_stage040_stage039_negative_window_delta_attribution_v1.csv`
- top_windows：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage040_stage039_negative_window_delta_attribution/rebuilt_c9_stage040_stage039_negative_window_delta_attribution_top_windows_stage040_stage039_negative_window_delta_attribution_v1.csv`
- lot_attribution：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage040_stage039_negative_window_delta_attribution/rebuilt_c9_stage040_stage039_negative_window_delta_attribution_top_window_lot_attribution_stage040_stage039_negative_window_delta_attribution_v1.csv`
- product_attribution：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage040_stage039_negative_window_delta_attribution/rebuilt_c9_stage040_stage039_negative_window_delta_attribution_top_window_product_attribution_stage040_stage039_negative_window_delta_attribution_v1.csv`
- decision：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage040_stage039_negative_window_delta_attribution/rebuilt_c9_stage040_stage039_negative_window_delta_attribution_decision_stage040_stage039_negative_window_delta_attribution_v1.json`
- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage040_stage039_negative_window_delta_attribution/rebuilt_c9_stage040_stage039_negative_window_delta_attribution_report_stage040_stage039_negative_window_delta_attribution_v1.md`

## 反思

- 运行前过拟合反思：否。本阶段不新增交易规则、不扫参数，只解释 Stage039 为什么右尾增强但严格目标失败。
- 运行后过拟合反思：否。输出是窗口迁移和 delta 归因；若据此反推日期/品种/方向过滤才会过拟合。
- 运行前继续价值反思：有。必须先确认失败来自真实窗口内亏损还是收益率分母效应，才能决定下一条路线。
- 运行后继续价值反思：Stage039 新增负窗口含显著分母效应；后续需要分别看绝对权益和收益率目标。
