# Stage033 - rank1-9 开仓早段质量加风险只读代理

- 记录时间：`2026-07-01T17:18`
- line_id：`futures_trend_rebuilt_c9_15w_optimization`
- model_tag：`stage033_rank19_early_quality_add_risk_proxy_v1`
- 是否重要突破版本：`否`
- 决策：`stage033_proxy_improves_goal_but_not_met_requires_new_selector`

## 本次版本变更

- 新增参数：`stage033_tag=label_rank_1_9_and_entry_or_first_aligned`、`stage033_add_risk_fraction=0.25`。
- 修改参数：无，Stage013/官方 C9 配置未改。
- 删除参数：无。
- 本阶段只读代理，不新增真实交易规则、不接实盘。

## 调研和判断结论

- 趋势跟随/pyramiding 资料支持确认后加风险，但仓库旧 Stage738/739 已证明真实加仓会受到整数手、保证金、止损和复利路径反身影响。
- 因此 Stage033 只做一个冻结上界代理：`AI rank 1-9 + entry_or_first_aligned + 25% 非挤占风险释放`，不扫标签组合、倍率、品种、方向或年份。

## 代理结果

- 选中 lots：`796`。
- Stage013 realized PnL：`14,242,295.90`。
- 代理增量 PnL：`3,560,573.98`。
- 严格任意结束日 `>1` 年负窗口：Stage013 `330947` -> Stage033 `324091`。
- Stage033 严格最差收益：`-42.3664%`。
- 到 `2026-06-30` 负窗口：`0`，最差 `29.0192%`。
- 收益保留 vs Stage006：`17/17`；vs Stage013：`17/17`。
- 收益改善/不变/变差 vs Stage013：`17/0/0`。
- 回撤改善/不变/变差 vs Stage013：`16/0/1`。

## 多起点摘要

| requested_start_month   |   total_return_pct_stage013 |   total_return_pct_stage020 |   return_delta_pp_stage020_vs_stage013 |   max_dd_pct_stage013 |   max_dd_pct_stage020 |   max_dd_delta_pp_stage020_vs_stage013 |
|:------------------------|----------------------------:|----------------------------:|---------------------------------------:|----------------------:|----------------------:|---------------------------------------:|
| 2018-01                 |                   7678.8    |                   8080.34   |                               401.538  |              -37.3409 |              -36.3839 |                                 0.9569 |
| 2018-07                 |                   9880.13   |                  10397.5    |                               517.341  |              -37.9477 |              -36.6976 |                                 1.2501 |
| 2019-01                 |                   9240.88   |                   9692.27   |                               451.386  |              -38.4073 |              -37.7595 |                                 0.6478 |
| 2019-07                 |                   5298.26   |                   5599.18   |                               300.928  |              -37.5846 |              -36.8025 |                                 0.7821 |
| 2020-01                 |                   3931.07   |                   4162.67   |                               231.596  |              -38.1717 |              -37.1024 |                                 1.0693 |
| 2020-07                 |                   3233.46   |                   3402.94   |                               169.483  |              -37.3761 |              -36.4205 |                                 0.9556 |
| 2021-01                 |                   1451.64   |                   1540.52   |                                88.8742 |              -36.7684 |              -35.6676 |                                 1.1007 |
| 2021-07                 |                    265.542  |                    294.391  |                                28.8492 |              -39.4246 |              -37.7031 |                                 1.7215 |
| 2022-01                 |                    122.752  |                    142.473  |                                19.7208 |              -34.2643 |              -31.6327 |                                 2.6316 |
| 2022-07                 |                    238.369  |                    266.493  |                                28.1247 |              -43.794  |              -42.3664 |                                 1.4276 |
| 2023-01                 |                    134.445  |                    172.371  |                                37.9258 |              -24.469  |              -25.3917 |                                -0.9227 |
| 2023-07                 |                    201.485  |                    246.131  |                                44.6455 |              -20.2875 |              -18.2074 |                                 2.0801 |
| 2024-01                 |                    138.199  |                    163.058  |                                24.8589 |              -18.6307 |              -16.3485 |                                 2.2822 |
| 2024-07                 |                     57.5587 |                     67.3251 |                                 9.7663 |              -20.3312 |              -16.7091 |                                 3.6221 |
| 2025-01                 |                     51.4687 |                     58.28   |                                 6.8113 |              -19.6119 |              -16.0753 |                                 3.5367 |
| 2025-07                 |                     33.3787 |                     40.6421 |                                 7.2633 |              -19.1855 |              -15.5438 |                                 3.6417 |
| 2026-01                 |                      1.9011 |                      6.5061 |                                 4.605  |              -14.7303 |              -14.1716 |                                 0.5587 |

## 收益保留摘要

| requested_start_month   |   stage020_vs_base_stage006_return_ratio |   stage020_vs_stage013_return_ratio |   passes_80pct_retention_vs_base_stage006 |   passes_80pct_retention_vs_stage013 |
|:------------------------|-----------------------------------------:|------------------------------------:|------------------------------------------:|-------------------------------------:|
| 2018-01                 |                                   0.9538 |                              1.0523 |                                         1 |                                    1 |
| 2018-07                 |                                   1.0573 |                              1.0524 |                                         1 |                                    1 |
| 2019-01                 |                                   1.0669 |                              1.0488 |                                         1 |                                    1 |
| 2019-07                 |                                   1.0858 |                              1.0568 |                                         1 |                                    1 |
| 2020-01                 |                                   1.0711 |                              1.0589 |                                         1 |                                    1 |
| 2020-07                 |                                   1.0811 |                              1.0524 |                                         1 |                                    1 |
| 2021-01                 |                                   1.0292 |                              1.0612 |                                         1 |                                    1 |
| 2021-07                 |                                   1.2197 |                              1.1086 |                                         1 |                                    1 |
| 2022-01                 |                                   1.2296 |                              1.1607 |                                         1 |                                    1 |
| 2022-07                 |                                   1.3086 |                              1.118  |                                         1 |                                    1 |
| 2023-01                 |                                   1.3748 |                              1.2821 |                                         1 |                                    1 |
| 2023-07                 |                                   1.3716 |                              1.2216 |                                         1 |                                    1 |
| 2024-01                 |                                   1.2921 |                              1.1799 |                                         1 |                                    1 |
| 2024-07                 |                                   1.314  |                              1.1697 |                                         1 |                                    1 |
| 2025-01                 |                                   1.8    |                              1.1323 |                                         1 |                                    1 |
| 2025-07                 |                                   1.2642 |                              1.2176 |                                         1 |                                    1 |
| 2026-01                 |                                   3.4223 |                              3.4223 |                                         1 |                                    1 |

## 文件

- lot_deltas: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage033_rank19_early_quality_add_risk_proxy/rebuilt_c9_stage033_rank19_early_quality_add_risk_proxy_lot_deltas_stage033_rank19_early_quality_add_risk_proxy_v1.csv`
- curves: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage033_rank19_early_quality_add_risk_proxy/rebuilt_c9_stage033_rank19_early_quality_add_risk_proxy_curves_stage033_rank19_early_quality_add_risk_proxy_v1.csv`
- summary: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage033_rank19_early_quality_add_risk_proxy/rebuilt_c9_stage033_rank19_early_quality_add_risk_proxy_summary_stage033_rank19_early_quality_add_risk_proxy_v1.csv`
- annual_returns: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage033_rank19_early_quality_add_risk_proxy/rebuilt_c9_stage033_rank19_early_quality_add_risk_proxy_annual_returns_stage033_rank19_early_quality_add_risk_proxy_v1.csv`
- goal_aggregate: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage033_rank19_early_quality_add_risk_proxy/rebuilt_c9_stage033_rank19_early_quality_add_risk_proxy_goal_aggregate_stage033_rank19_early_quality_add_risk_proxy_v1.csv`
- goal_to_final: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage033_rank19_early_quality_add_risk_proxy/rebuilt_c9_stage033_rank19_early_quality_add_risk_proxy_goal_to_final_windows_stage033_rank19_early_quality_add_risk_proxy_v1.csv`
- goal_fixed_horizon: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage033_rank19_early_quality_add_risk_proxy/rebuilt_c9_stage033_rank19_early_quality_add_risk_proxy_goal_fixed_horizon_windows_stage033_rank19_early_quality_add_risk_proxy_v1.csv`
- goal_worst_windows: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage033_rank19_early_quality_add_risk_proxy/rebuilt_c9_stage033_rank19_early_quality_add_risk_proxy_goal_worst_windows_stage033_rank19_early_quality_add_risk_proxy_v1.csv`
- retention: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage033_rank19_early_quality_add_risk_proxy/rebuilt_c9_stage033_rank19_early_quality_add_risk_proxy_full_cycle_retention_stage033_rank19_early_quality_add_risk_proxy_v1.csv`
- chart: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage033_rank19_early_quality_add_risk_proxy/rebuilt_c9_stage033_rank19_early_quality_add_risk_proxy_chart_stage033_rank19_early_quality_add_risk_proxy_v1.png`
- goal_chart: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage033_rank19_early_quality_add_risk_proxy/rebuilt_c9_stage033_rank19_early_quality_add_risk_proxy_goal_chart_stage033_rank19_early_quality_add_risk_proxy_v1.png`
- decision: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage033_rank19_early_quality_add_risk_proxy/rebuilt_c9_stage033_rank19_early_quality_add_risk_proxy_decision_stage033_rank19_early_quality_add_risk_proxy_v1.json`
- report: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage033_rank19_early_quality_add_risk_proxy/rebuilt_c9_stage033_rank19_early_quality_add_risk_proxy_report_stage033_rank19_early_quality_add_risk_proxy_v1.md`

## 后续规划和 TODO

- 若严格负窗口仍未清零，不能通过加风险倍率救参；下一步转向账户级 selector、真实可交易早段引擎可行性，或外生信息源。
- 若代理达标，也必须写真引擎验证成交、保证金、broker10、AI 月度审计和实盘执行可行性。

## 反思

- 过拟合反思：否。结果无论好坏都不调标签和比例；若下一步按负窗口倒推参数或复用小样本产品/日期豁免，会过拟合。
- 继续价值反思：有，但不是进入真实加仓引擎。Stage033 提升收益和多数起点回撤，说明早段质量标签有信息量；但严格任意大于一年负窗口仍未清零，下一步应转向账户级 selector、可交易早段执行约束或外生信息源。
