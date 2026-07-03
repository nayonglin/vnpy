# Stage021 full-market 共识选择器与 jd 非挤占只读代理

- 记录时间：`2026-07-01T15:07`
- line_id：`futures_trend_rebuilt_c9_15w_optimization`
- model_tag：`stage021_full_market_consensus_jd_proxy_v1`
- 是否重要突破版本：`否`
- 决策：`stage021_proxy_improves_but_goal_not_met`

## 本次版本变更

- 新增参数：`selector=AI top8 AND simple trend top8`、`stage021_add_risk_fraction=0.25`。
- 修改参数：无，Stage013/Stage020/官方 C9 配置未改。
- 删除参数：无。
- 本阶段只读代理，不新增真实交易规则、不接实盘。

## 调研和判断结论

- 外部趋势跟随资料支持分散化、目标波动和市场广度，但 sizing 没有普适免费午餐。
- 本阶段只跑一个 full-market AI 与 simple trend 共识选择器，不扫 topN、倍率、品种或日期。
- jd 只能先按非挤占候选审计，不能直接塞入共享 AI topN。

## 代理结果

- selected lots：`100`。
- Stage013 realized PnL：`11,707,033.20`。
- 代理增量 PnL：`2,926,758.30`。
- focus 2022-2023 selected realized PnL：`482,830.00`。
- 严格任意结束日 `>1` 年负窗口：Stage020 `323323` -> Stage021 combo `321446`。
- Stage021 combo 严格最差收益：`-42.0358%`。
- 到 `2026-06-30` 负窗口：`0`，最差 `29.8486%`。
- 收益保留 vs Stage006：`17/17`。
- 收益改善/不变/变差 vs Stage020：`16/1/0`。
- 回撤改善/不变/变差 vs Stage020：`9/6/2`。

## 选择器统计

| selector       |   row_count |   month_count |   product_count |   future_top_half_rate_pct |   mean_future_net_pnl_60d |   median_future_net_pnl_60d |   mean_future_rank_pct_60d |   mean_ai_rank |   mean_simple_rank |
|:---------------|------------:|--------------:|----------------:|---------------------------:|--------------------------:|----------------------------:|---------------------------:|---------------:|-------------------:|
| ai_top8        |         400 |            50 |              56 |                    77.25   |                   47.6625 |                           0 |                   0.527237 |        4.5     |           29.19    |
| simple_top8    |         400 |            50 |              51 |                    60.25   |                 -432.85   |                           0 |                   0.487544 |       34.0975  |            4.5     |
| consensus_top8 |          33 |            23 |              21 |                    66.6667 |                  544.545  |                           0 |                   0.498405 |        4.72727 |            3.60606 |
| non_consensus  |        2817 |            50 |              57 |                    67.3411 |                 -133.06   |                           0 |                   0.508893 |       29.2843  |           29.2975  |

## jd 摘要

| scope                   |   month_count |   ai_top8_count |   simple_top8_count |   consensus_top8_count |   future_top_half_count |   future_top_half_rate_pct |   mean_future_net_pnl_60d |   median_future_net_pnl_60d |   mean_ai_rank |   median_ai_rank |   mean_simple_rank |   median_simple_rank |
|:------------------------|--------------:|----------------:|--------------------:|-----------------------:|------------------------:|---------------------------:|--------------------------:|----------------------------:|---------------:|-----------------:|-------------------:|---------------------:|
| jd_all_available_months |            50 |              11 |                  11 |                      2 |                      21 |                    42      |                    -92.4  |                        -480 |        28.42   |             25.5 |            30.9    |                 37.5 |
| jd_focus_2022_2023      |            24 |               3 |                   6 |                      2 |                       9 |                    37.5    |                    317.5  |                        -895 |        38.2917 |             44.5 |            31.4583 |                 34.5 |
| jd_2022_h1              |             6 |               1 |                   1 |                      0 |                       5 |                    83.3333 |                   7201.67 |                        8230 |        33.1667 |             35   |            22.3333 |                 17.5 |
| jd_2022_h2              |             6 |               2 |                   5 |                      2 |                       2 |                    33.3333 |                  -1405    |                        -760 |        28.8333 |             34   |            10.1667 |                  6   |
| jd_2023                 |            12 |               0 |                   0 |                      0 |                       2 |                    16.6667 |                  -2263.33 |                       -3000 |        45.5833 |             46   |            46.6667 |                 49.5 |
| jd_2024_2025            |            24 |               8 |                   5 |                      0 |                      10 |                    41.6667 |                   -510    |                        -420 |        18.9167 |             18.5 |            28.875  |                 33.5 |

## 多起点摘要

| requested_start_month   |   total_return_pct_stage020_high_quality_proxy |   total_return_pct_stage021_combo_stage020_plus_consensus |   combo_return_delta_pp_vs_stage020 |   max_dd_pct_stage020_high_quality_proxy |   max_dd_pct_stage021_combo_stage020_plus_consensus |   combo_maxdd_delta_pp_vs_stage020 |
|:------------------------|-----------------------------------------------:|----------------------------------------------------------:|------------------------------------:|-----------------------------------------:|----------------------------------------------------:|-----------------------------------:|
| 2018-01                 |                                     7799.9     |                                                8150.63    |                           350.725   |                                 -37.5655 |                                            -36.5374 |                          1.02812   |
| 2018-07                 |                                    10013.3     |                                               10471.4     |                           458.055   |                                 -38.1062 |                                            -37.039  |                          1.06721   |
| 2019-01                 |                                     9382.4     |                                                9804.79    |                           422.388   |                                 -39.339  |                                            -39.339  |                          0         |
| 2019-07                 |                                     5494.68    |                                                5740.39    |                           245.701   |                                 -38.3235 |                                            -38.3235 |                          0         |
| 2020-01                 |                                     4084.01    |                                                4267.93    |                           183.915   |                                 -38.3148 |                                            -37.589  |                          0.725838  |
| 2020-07                 |                                     3357.97    |                                                3499.24    |                           141.278   |                                 -37.4824 |                                            -37.2327 |                          0.249706  |
| 2021-01                 |                                     1510.47    |                                                1575.78    |                            65.3096  |                                 -36.9516 |                                            -36.4175 |                          0.534133  |
| 2021-07                 |                                      273.285   |                                                 287.873   |                            14.588   |                                 -38.6036 |                                            -38.7035 |                         -0.0998548 |
| 2022-01                 |                                      127.005   |                                                 135.95    |                             8.94462 |                                 -32.0596 |                                            -31.7952 |                          0.264333  |
| 2022-07                 |                                      261.106   |                                                 274.508   |                            13.4013  |                                 -41.6745 |                                            -42.0358 |                         -0.361339  |
| 2023-01                 |                                      147.63    |                                                 156.636   |                             9.00628 |                                 -24.469  |                                            -24.469  |                          0         |
| 2023-07                 |                                      217.515   |                                                 229.604   |                            12.0896  |                                 -19.8293 |                                            -19.8293 |                          0         |
| 2024-01                 |                                      147.73    |                                                 156.737   |                             9.00628 |                                 -17.3393 |                                            -17.3393 |                          0         |
| 2024-07                 |                                       63.9837  |                                                  69.9067  |                             5.92295 |                                 -17.1361 |                                            -16.6489 |                          0.487233  |
| 2025-01                 |                                       57.3504  |                                                  63.2734  |                             5.92295 |                                 -16.2599 |                                            -14.9326 |                          1.32727   |
| 2025-07                 |                                       38.9237  |                                                  43.8433  |                             4.91962 |                                 -15.6746 |                                            -14.6739 |                          1.00071   |
| 2026-01                 |                                        1.90107 |                                                   1.90107 |                             0       |                                 -14.7303 |                                            -14.7303 |                          0         |

## 收益保留摘要

| requested_start_month   |   stage021_combo_stage020_plus_consensus_vs_base_stage006_return_ratio |   stage021_combo_stage020_plus_consensus_vs_stage013_return_ratio |   stage021_combo_stage020_plus_consensus_passes_80pct_retention_vs_base_stage006 |   stage021_combo_stage020_plus_consensus_passes_80pct_retention_vs_stage013 |
|:------------------------|-----------------------------------------------------------------------:|------------------------------------------------------------------:|---------------------------------------------------------------------------------:|----------------------------------------------------------------------------:|
| 2018-01                 |                                                                0.96213 |                                                           1.06145 |                                                                                1 |                                                                           1 |
| 2018-07                 |                                                                1.06485 |                                                           1.05984 |                                                                                1 |                                                                           1 |
| 2019-01                 |                                                                1.07927 |                                                           1.06102 |                                                                                1 |                                                                           1 |
| 2019-07                 |                                                                1.11321 |                                                           1.08345 |                                                                                1 |                                                                           1 |
| 2020-01                 |                                                                1.09823 |                                                           1.08569 |                                                                                1 |                                                                           1 |
| 2020-07                 |                                                                1.11173 |                                                           1.0822  |                                                                                1 |                                                                           1 |
| 2021-01                 |                                                                1.05275 |                                                           1.08552 |                                                                                1 |                                                                           1 |
| 2021-07                 |                                                                1.19268 |                                                           1.0841  |                                                                                1 |                                                                           1 |
| 2022-01                 |                                                                1.17334 |                                                           1.10752 |                                                                                1 |                                                                           1 |
| 2022-07                 |                                                                1.34799 |                                                           1.15161 |                                                                                1 |                                                                           1 |
| 2023-01                 |                                                                1.24929 |                                                           1.16505 |                                                                                1 |                                                                           1 |
| 2023-07                 |                                                                1.27953 |                                                           1.13956 |                                                                                1 |                                                                           1 |
| 2024-01                 |                                                                1.24198 |                                                           1.13414 |                                                                                1 |                                                                           1 |
| 2024-07                 |                                                                1.36443 |                                                           1.21453 |                                                                                1 |                                                                           1 |
| 2025-01                 |                                                                1.95419 |                                                           1.22936 |                                                                                1 |                                                                           1 |
| 2025-07                 |                                                                1.36379 |                                                           1.31351 |                                                                                1 |                                                                           1 |
| 2026-01                 |                                                                1       |                                                           1       |                                                                                1 |                                                                           1 |

## 文件

- predictions: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage021_full_market_consensus_jd_proxy/rebuilt_c9_stage021_full_market_consensus_jd_proxy_full_market_predictions_ranked_stage021_full_market_consensus_jd_proxy_v1.csv`
- lot_deltas: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage021_full_market_consensus_jd_proxy/rebuilt_c9_stage021_full_market_consensus_jd_proxy_lot_deltas_stage021_full_market_consensus_jd_proxy_v1.csv`
- curves: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage021_full_market_consensus_jd_proxy/rebuilt_c9_stage021_full_market_consensus_jd_proxy_curves_stage021_full_market_consensus_jd_proxy_v1.csv`
- summary: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage021_full_market_consensus_jd_proxy/rebuilt_c9_stage021_full_market_consensus_jd_proxy_summary_stage021_full_market_consensus_jd_proxy_v1.csv`
- selector_summary: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage021_full_market_consensus_jd_proxy/rebuilt_c9_stage021_full_market_consensus_jd_proxy_selector_summary_stage021_full_market_consensus_jd_proxy_v1.csv`
- jd_month_audit: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage021_full_market_consensus_jd_proxy/rebuilt_c9_stage021_full_market_consensus_jd_proxy_jd_month_audit_stage021_full_market_consensus_jd_proxy_v1.csv`
- jd_summary: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage021_full_market_consensus_jd_proxy/rebuilt_c9_stage021_full_market_consensus_jd_proxy_jd_summary_stage021_full_market_consensus_jd_proxy_v1.csv`
- goal_aggregate: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage021_full_market_consensus_jd_proxy/rebuilt_c9_stage021_full_market_consensus_jd_proxy_goal_aggregate_stage021_full_market_consensus_jd_proxy_v1.csv`
- goal_to_final: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage021_full_market_consensus_jd_proxy/rebuilt_c9_stage021_full_market_consensus_jd_proxy_goal_to_final_windows_stage021_full_market_consensus_jd_proxy_v1.csv`
- goal_fixed_horizon: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage021_full_market_consensus_jd_proxy/rebuilt_c9_stage021_full_market_consensus_jd_proxy_goal_fixed_horizon_windows_stage021_full_market_consensus_jd_proxy_v1.csv`
- goal_worst_windows: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage021_full_market_consensus_jd_proxy/rebuilt_c9_stage021_full_market_consensus_jd_proxy_goal_worst_windows_stage021_full_market_consensus_jd_proxy_v1.csv`
- retention: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage021_full_market_consensus_jd_proxy/rebuilt_c9_stage021_full_market_consensus_jd_proxy_retention_stage021_full_market_consensus_jd_proxy_v1.csv`
- chart: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage021_full_market_consensus_jd_proxy/rebuilt_c9_stage021_full_market_consensus_jd_proxy_chart_stage021_full_market_consensus_jd_proxy_v1.png`
- decision: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage021_full_market_consensus_jd_proxy/rebuilt_c9_stage021_full_market_consensus_jd_proxy_decision_stage021_full_market_consensus_jd_proxy_v1.json`
- report: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage021_full_market_consensus_jd_proxy/rebuilt_c9_stage021_full_market_consensus_jd_proxy_report_stage021_full_market_consensus_jd_proxy_v1.md`

## 后续规划和 TODO

- 若严格负窗口仍未清零，不继续调 topN 或加风险比例；转真实引擎前置生存约束或新外生信息源。
- 若 jd 共识月份仍不稳定，jd 只保留为非挤占观察，不直接加入共享 AI topN。

## 反思

- 过拟合反思：否。本阶段只读归因，不根据结果改 topN、比例或过滤条件；若用 2022H1/2023 事后分段写规则会过拟合。
- 继续价值反思：有，但只能作为新信息源候选。full-market 共识若降低负窗口但未达标，应转真实引擎小预算验证或继续找非价格信息。
