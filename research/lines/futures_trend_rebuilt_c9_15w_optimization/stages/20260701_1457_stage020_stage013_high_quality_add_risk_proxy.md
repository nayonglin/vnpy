# Stage020 Stage013 + 高质量标签加风险只读代理

- 记录时间：`2026-07-01T14:57`
- line_id：`futures_trend_rebuilt_c9_15w_optimization`
- model_tag：`stage020_stage013_high_quality_add_risk_proxy_v1`
- 是否重要突破版本：`否`
- 决策：`stage020_proxy_improves_goal_but_not_met_requires_new_selector`

## 本次版本变更

- 新增参数：`stage020_tag=tag_ai4_6_entry_or_first_aligned`、`stage020_add_risk_fraction=0.25`。
- 修改参数：无，Stage013/官方 C9 配置未改。
- 删除参数：无。
- 本阶段只读代理，不新增真实交易规则、不接实盘。

## 调研和判断结论

- 外部 meta-labeling/bet-sizing 支持二级质量信号决定风险大小，但 DSR/PBO 要求控制试验次数。
- 本阶段只跑一个已预声明标签和固定 25% 非挤占比例，不扫参。

## 代理结果

- 选中 lots：`233`。
- Stage013 realized PnL：`6,119,015.00`。
- 代理增量 PnL：`1,529,753.75`。
- 严格任意结束日 `>1` 年负窗口：Stage013 `330947` -> Stage020 `323323`。
- Stage020 严格最差收益：`-41.6745%`。
- 到 `2026-06-30` 负窗口：`0`，最差 `25.5769%`。
- 收益保留 vs Stage006：`17/17`；vs Stage013：`17/17`。
- 收益改善/不变/变差 vs Stage013：`16/1/0`。
- 回撤改善/不变/变差 vs Stage013：`8/2/7`。

## 多起点摘要

| requested_start_month   |   total_return_pct_stage013 |   total_return_pct_stage020 |   return_delta_pp_stage020_vs_stage013 |   max_dd_pct_stage013 |   max_dd_pct_stage020 |   max_dd_delta_pp_stage020_vs_stage013 |
|:------------------------|----------------------------:|----------------------------:|---------------------------------------:|----------------------:|----------------------:|---------------------------------------:|
| 2018-01                 |                   7678.8    |                   7799.9    |                               121.102  |              -37.3409 |              -37.5655 |                                -0.2246 |
| 2018-07                 |                   9880.13   |                  10013.3    |                               133.177  |              -37.9477 |              -38.1062 |                                -0.1585 |
| 2019-01                 |                   9240.88   |                   9382.4    |                               141.522  |              -38.4073 |              -39.339  |                                -0.9318 |
| 2019-07                 |                   5298.26   |                   5494.68   |                               196.427  |              -37.5846 |              -38.3235 |                                -0.7389 |
| 2020-01                 |                   3931.07   |                   4084.01   |                               152.938  |              -38.1717 |              -38.3148 |                                -0.1431 |
| 2020-07                 |                   3233.46   |                   3357.97   |                               124.507  |              -37.3761 |              -37.4824 |                                -0.1064 |
| 2021-01                 |                   1451.64   |                   1510.47   |                                58.8333 |              -36.7684 |              -36.9516 |                                -0.1832 |
| 2021-07                 |                    265.542  |                    273.285  |                                 7.7433 |              -39.4246 |              -38.6036 |                                 0.821  |
| 2022-01                 |                    122.752  |                    127.005  |                                 4.2533 |              -34.2643 |              -32.0596 |                                 2.2048 |
| 2022-07                 |                    238.369  |                    261.106  |                                22.7375 |              -43.794  |              -41.6745 |                                 2.1195 |
| 2023-01                 |                    134.445  |                    147.63   |                                13.1842 |              -24.469  |              -24.469  |                                 0      |
| 2023-07                 |                    201.485  |                    217.515  |                                16.0292 |              -20.2875 |              -19.8293 |                                 0.4582 |
| 2024-01                 |                    138.199  |                    147.73   |                                 9.5317 |              -18.6307 |              -17.3393 |                                 1.2914 |
| 2024-07                 |                     57.5587 |                     63.9837 |                                 6.425  |              -20.3312 |              -17.1361 |                                 3.1951 |
| 2025-01                 |                     51.4687 |                     57.3504 |                                 5.8817 |              -19.6119 |              -16.2599 |                                 3.3521 |
| 2025-07                 |                     33.3787 |                     38.9237 |                                 5.545  |              -19.1855 |              -15.6746 |                                 3.5108 |
| 2026-01                 |                      1.9011 |                      1.9011 |                                 0      |              -14.7303 |              -14.7303 |                                -0      |

## 收益保留摘要

| requested_start_month   |   stage020_vs_base_stage006_return_ratio |   stage020_vs_stage013_return_ratio |   passes_80pct_retention_vs_base_stage006 |   passes_80pct_retention_vs_stage013 |
|:------------------------|-----------------------------------------:|------------------------------------:|------------------------------------------:|-------------------------------------:|
| 2018-01                 |                                   0.9207 |                              1.0158 |                                         1 |                                    1 |
| 2018-07                 |                                   1.0183 |                              1.0135 |                                         1 |                                    1 |
| 2019-01                 |                                   1.0328 |                              1.0153 |                                         1 |                                    1 |
| 2019-07                 |                                   1.0656 |                              1.0371 |                                         1 |                                    1 |
| 2020-01                 |                                   1.0509 |                              1.0389 |                                         1 |                                    1 |
| 2020-07                 |                                   1.0668 |                              1.0385 |                                         1 |                                    1 |
| 2021-01                 |                                   1.0091 |                              1.0405 |                                         1 |                                    1 |
| 2021-07                 |                                   1.1322 |                              1.0292 |                                         1 |                                    1 |
| 2022-01                 |                                   1.0961 |                              1.0346 |                                         1 |                                    1 |
| 2022-07                 |                                   1.2822 |                              1.0954 |                                         1 |                                    1 |
| 2023-01                 |                                   1.1775 |                              1.0981 |                                         1 |                                    1 |
| 2023-07                 |                                   1.2122 |                              1.0796 |                                         1 |                                    1 |
| 2024-01                 |                                   1.1706 |                              1.069  |                                         1 |                                    1 |
| 2024-07                 |                                   1.2488 |                              1.1116 |                                         1 |                                    1 |
| 2025-01                 |                                   1.7713 |                              1.1143 |                                         1 |                                    1 |
| 2025-07                 |                                   1.2108 |                              1.1661 |                                         1 |                                    1 |
| 2026-01                 |                                   1      |                              1      |                                         1 |                                    1 |

## 文件

- lot_deltas: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage020_stage013_high_quality_add_risk_proxy/rebuilt_c9_stage020_stage013_high_quality_add_risk_proxy_lot_deltas_stage020_stage013_high_quality_add_risk_proxy_v1.csv`
- curves: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage020_stage013_high_quality_add_risk_proxy/rebuilt_c9_stage020_stage013_high_quality_add_risk_proxy_curves_stage020_stage013_high_quality_add_risk_proxy_v1.csv`
- summary: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage020_stage013_high_quality_add_risk_proxy/rebuilt_c9_stage020_stage013_high_quality_add_risk_proxy_summary_stage020_stage013_high_quality_add_risk_proxy_v1.csv`
- annual_returns: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage020_stage013_high_quality_add_risk_proxy/rebuilt_c9_stage020_stage013_high_quality_add_risk_proxy_annual_returns_stage020_stage013_high_quality_add_risk_proxy_v1.csv`
- goal_aggregate: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage020_stage013_high_quality_add_risk_proxy/rebuilt_c9_stage020_stage013_high_quality_add_risk_proxy_goal_aggregate_stage020_stage013_high_quality_add_risk_proxy_v1.csv`
- goal_to_final: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage020_stage013_high_quality_add_risk_proxy/rebuilt_c9_stage020_stage013_high_quality_add_risk_proxy_goal_to_final_windows_stage020_stage013_high_quality_add_risk_proxy_v1.csv`
- goal_fixed_horizon: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage020_stage013_high_quality_add_risk_proxy/rebuilt_c9_stage020_stage013_high_quality_add_risk_proxy_goal_fixed_horizon_windows_stage020_stage013_high_quality_add_risk_proxy_v1.csv`
- goal_worst_windows: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage020_stage013_high_quality_add_risk_proxy/rebuilt_c9_stage020_stage013_high_quality_add_risk_proxy_goal_worst_windows_stage020_stage013_high_quality_add_risk_proxy_v1.csv`
- retention: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage020_stage013_high_quality_add_risk_proxy/rebuilt_c9_stage020_stage013_high_quality_add_risk_proxy_full_cycle_retention_stage020_stage013_high_quality_add_risk_proxy_v1.csv`
- chart: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage020_stage013_high_quality_add_risk_proxy/rebuilt_c9_stage020_stage013_high_quality_add_risk_proxy_chart_stage020_stage013_high_quality_add_risk_proxy_v1.png`
- goal_chart: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage020_stage013_high_quality_add_risk_proxy/rebuilt_c9_stage020_stage013_high_quality_add_risk_proxy_goal_chart_stage020_stage013_high_quality_add_risk_proxy_v1.png`
- decision: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage020_stage013_high_quality_add_risk_proxy/rebuilt_c9_stage020_stage013_high_quality_add_risk_proxy_decision_stage020_stage013_high_quality_add_risk_proxy_v1.json`
- report: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage020_stage013_high_quality_add_risk_proxy/rebuilt_c9_stage020_stage013_high_quality_add_risk_proxy_report_stage020_stage013_high_quality_add_risk_proxy_v1.md`

## 后续规划和 TODO

- 若严格负窗口仍未清零，不能通过加风险倍率救参；下一步转向新信息源/选择器或真实引擎前置约束。
- 若代理达标，也必须写真引擎验证成交、保证金、broker10 和 AI 月度审计。

## 反思

- 过拟合反思：否。本阶段没有根据结果换标签或调比例；若继续按失败窗口反推新标签会过拟合。
- 继续价值反思：有，但不是继续加风险倍率救参。Stage020 证明高质量标签能抬收益和部分左尾，但严格负窗口仍未清零，下一步应转向新信息源/选择器或真实引擎前置约束。
