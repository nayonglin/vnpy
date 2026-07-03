# Stage074 冷启动资本 ramp proxy

- 记录时间：2026-07-02 01:13 CST
- line_id：`futures_trend_rebuilt_c9_15w_optimization`
- model_tag：`stage074_cold_start_capital_ramp_proxy_v1`
- 是否重要突破版本：否
- 新增参数：`stage074_cold_start_ramp_floor=0.35`、`stage074_cold_start_ramp_trading_days=252`。
- 修改参数：无正式策略参数修改；本阶段是账户外层 proxy。
- 删除参数：无。

# Stage074 cold-start capital ramp proxy

## 结论

- 决策：`stage074_cold_start_ramp_proxy_not_goal_no_param_rescue`
- 下一步：停止 floor/ramp_days 救参；若继续账户外层，应换结构而不是调 0.35/252
- A/B/C：A=`stage013_engine`，B=`stage013_engine_cold_start_ramp`，C0=`full_market_ai_top8_and_active_positions_lt3`，C=`full_market_ai_top8_and_active_positions_lt3_cold_start_ramp`
- 固定参数：floor `0.35`，ramp `252` 个交易日。

## 外部调研判断

- Managed futures/trend-following 资料支持组合层风险目标、drawdown/risk overlay 和 capital correction，但也警告过度调参会削弱趋势右尾。
- 本阶段只验证一个冷启动部署层，不改信号、不改品种、不按坏窗口调参数。

## 过拟合与继续价值反思

- 开始是否过拟合：否。候选是账户启动风险部署层，固定 252 个交易日和 0.35 floor，不按具体坏窗口调参。
- 结束是否过拟合：否。本阶段没有根据结果调整 floor 或 ramp_days；若失败后继续调这些数就是过拟合。
- 开始是否值得继续：有。目标本质包含任意起点冷启动路径，账户部署层直接针对这个结构问题。
- 结束是否值得继续：若 proxy 不达标，则该线性 ramp 形状无继续救参价值；若达标，也必须做真实部署层验证。

## Variant Summary

| variant                                                      |   min_return_pct |   median_return_pct |   worst_max_dd_pct |   median_sharpe |   all_gt1y_window_count |   all_gt1y_negative_count |   all_gt1y_min_return_pct |   to_final_negative_count |   to_final_min_return_pct |   retention_vs_base_stage006_pass_count |   retention_vs_stage013_pass_count |   retention_rows |
|:-------------------------------------------------------------|-----------------:|--------------------:|-------------------:|----------------:|------------------------:|--------------------------:|--------------------------:|--------------------------:|--------------------------:|----------------------------------------:|-----------------------------------:|-----------------:|
| full_market_ai_top8_and_active_positions_lt3                 |           5.4611 |             252.088 |           -44.1402 |          1.3109 |                 7215647 |                    315429 |                  -44.1402 |                         0 |                   26.3113 |                                         |                                    |                0 |
| full_market_ai_top8_and_active_positions_lt3_cold_start_ramp |           0.694  |             231.653 |           -46.5554 |          1.1777 |                 7215647 |                    304693 |                  -23.6338 |                         0 |                   13.5359 |                                      15 |                                 15 |               17 |
| stage013_engine                                              |           1.9011 |             238.369 |           -43.794  |          1.2722 |                 7215647 |                    330947 |                  -43.794  |                         0 |                   26.6753 |                                         |                                    |                0 |
| stage013_engine_cold_start_ramp                              |          -0.8839 |             219.891 |           -47.8435 |          1.1353 |                 7215647 |                    320226 |                  -24.845  |                         0 |                   13.6081 |                                      15 |                                 14 |               17 |

## Goal Aggregate

| variant                                                      | source_start_month   | audit_scope                 |   window_count |   positive_count |   negative_count |   negative_rate_pct |   min_return_pct |   mean_return_pct |   is_independent_daily_cold_start |   is_start_reset_ramp_proxy |
|:-------------------------------------------------------------|:---------------------|:----------------------------|---------------:|-----------------:|-----------------:|--------------------:|-----------------:|------------------:|----------------------------------:|----------------------------:|
| full_market_ai_top8_and_active_positions_lt3                 | 2018-01              | all_trading_end_dates_gt_1y |         882036 |           856165 |            25871 |              2.9331 |         -31.5683 |          757.643  |                                 0 |                           0 |
| full_market_ai_top8_and_active_positions_lt3                 | 2018-01              | start_to_2026_06_30_only    |           1328 |             1328 |                0 |              0      |          28.0729 |          874.637  |                                 0 |                           0 |
| full_market_ai_top8_and_active_positions_lt3_cold_start_ramp | 2018-01              | all_trading_end_dates_gt_1y |         882036 |           855415 |            26621 |              3.0181 |         -16.3027 |          700.242  |                                 0 |                           1 |
| full_market_ai_top8_and_active_positions_lt3_cold_start_ramp | 2018-01              | start_to_2026_06_30_only    |           1328 |             1328 |                0 |              0      |          13.5359 |          834.066  |                                 0 |                           1 |
| full_market_ai_top8_and_active_positions_lt3                 | 2018-07              | all_trading_end_dates_gt_1y |         882036 |           855594 |            26442 |              2.9978 |         -32.4206 |          812.646  |                                 0 |                           0 |
| full_market_ai_top8_and_active_positions_lt3                 | 2018-07              | start_to_2026_06_30_only    |           1328 |             1328 |                0 |              0      |          30.7608 |          916.095  |                                 0 |                           0 |
| full_market_ai_top8_and_active_positions_lt3_cold_start_ramp | 2018-07              | all_trading_end_dates_gt_1y |         882036 |           854950 |            27086 |              3.0708 |         -15.6788 |          753.038  |                                 0 |                           1 |
| full_market_ai_top8_and_active_positions_lt3_cold_start_ramp | 2018-07              | start_to_2026_06_30_only    |           1328 |             1328 |                0 |              0      |          14.2604 |          874.344  |                                 0 |                           1 |
| full_market_ai_top8_and_active_positions_lt3                 | 2019-01              | all_trading_end_dates_gt_1y |         882036 |           851959 |            30077 |              3.41   |         -32.8977 |          816.412  |                                 0 |                           0 |
| full_market_ai_top8_and_active_positions_lt3                 | 2019-01              | start_to_2026_06_30_only    |           1328 |             1328 |                0 |              0      |          29.6473 |          975.692  |                                 0 |                           0 |
| full_market_ai_top8_and_active_positions_lt3_cold_start_ramp | 2019-01              | all_trading_end_dates_gt_1y |         882036 |           853471 |            28565 |              3.2385 |         -17.8652 |          757.374  |                                 0 |                           1 |
| full_market_ai_top8_and_active_positions_lt3_cold_start_ramp | 2019-01              | start_to_2026_06_30_only    |           1328 |             1328 |                0 |              0      |          13.9141 |          933.882  |                                 0 |                           1 |
| full_market_ai_top8_and_active_positions_lt3                 | 2019-07              | all_trading_end_dates_gt_1y |         882036 |           855607 |            26429 |              2.9964 |         -31.4469 |          580.601  |                                 0 |                           0 |
| full_market_ai_top8_and_active_positions_lt3                 | 2019-07              | start_to_2026_06_30_only    |           1328 |             1328 |                0 |              0      |          39.6755 |          748.031  |                                 0 |                           0 |
| full_market_ai_top8_and_active_positions_lt3_cold_start_ramp | 2019-07              | all_trading_end_dates_gt_1y |         882036 |           856728 |            25308 |              2.8693 |         -16.0252 |          534.272  |                                 0 |                           1 |
| full_market_ai_top8_and_active_positions_lt3_cold_start_ramp | 2019-07              | start_to_2026_06_30_only    |           1328 |             1328 |                0 |              0      |          21.5377 |          713.759  |                                 0 |                           1 |
| full_market_ai_top8_and_active_positions_lt3                 | 2020-01              | all_trading_end_dates_gt_1y |         882036 |           855078 |            26958 |              3.0563 |         -31.7195 |          627.454  |                                 0 |                           0 |
| full_market_ai_top8_and_active_positions_lt3                 | 2020-01              | start_to_2026_06_30_only    |           1328 |             1328 |                0 |              0      |          40.2034 |          799.564  |                                 0 |                           0 |
| full_market_ai_top8_and_active_positions_lt3_cold_start_ramp | 2020-01              | all_trading_end_dates_gt_1y |         882036 |           856243 |            25793 |              2.9243 |         -16.0546 |          578.212  |                                 0 |                           1 |
| full_market_ai_top8_and_active_positions_lt3_cold_start_ramp | 2020-01              | start_to_2026_06_30_only    |           1328 |             1328 |                0 |              0      |          21.805  |          763.588  |                                 0 |                           1 |
| full_market_ai_top8_and_active_positions_lt3                 | 2020-07              | all_trading_end_dates_gt_1y |         733565 |           706368 |            27197 |              3.7075 |         -31.4102 |          386.715  |                                 0 |                           0 |
| full_market_ai_top8_and_active_positions_lt3                 | 2020-07              | start_to_2026_06_30_only    |           1211 |             1211 |                0 |              0      |          36.7453 |          477.963  |                                 0 |                           0 |
| full_market_ai_top8_and_active_positions_lt3_cold_start_ramp | 2020-07              | all_trading_end_dates_gt_1y |         733565 |           707390 |            26175 |              3.5682 |         -15.8034 |          338.692  |                                 0 |                           1 |
| full_market_ai_top8_and_active_positions_lt3_cold_start_ramp | 2020-07              | start_to_2026_06_30_only    |           1211 |             1211 |                0 |              0      |          19.9124 |          444.349  |                                 0 |                           1 |
| full_market_ai_top8_and_active_positions_lt3                 | 2021-01              | all_trading_end_dates_gt_1y |         589005 |           553820 |            35185 |              5.9736 |         -31.7901 |          182.02   |                                 0 |                           0 |
| full_market_ai_top8_and_active_positions_lt3                 | 2021-01              | start_to_2026_06_30_only    |           1085 |             1085 |                0 |              0      |          35.8694 |          243.744  |                                 0 |                           0 |
| full_market_ai_top8_and_active_positions_lt3_cold_start_ramp | 2021-01              | all_trading_end_dates_gt_1y |         589005 |           549158 |            39847 |              6.7651 |         -15.9867 |          150.426  |                                 0 |                           1 |
| full_market_ai_top8_and_active_positions_lt3_cold_start_ramp | 2021-01              | start_to_2026_06_30_only    |           1085 |             1085 |                0 |              0      |          19.2731 |          220.246  |                                 0 |                           1 |
| full_market_ai_top8_and_active_positions_lt3                 | 2021-07              | all_trading_end_dates_gt_1y |         467873 |           393572 |            74301 |             15.8806 |         -38.3634 |           61.5016 |                                 0 |                           0 |
| full_market_ai_top8_and_active_positions_lt3                 | 2021-07              | start_to_2026_06_30_only    |            967 |              967 |                0 |              0      |          31.0859 |          112.87   |                                 0 |                           0 |
| full_market_ai_top8_and_active_positions_lt3_cold_start_ramp | 2021-07              | all_trading_end_dates_gt_1y |         467873 |           393200 |            74673 |             15.9601 |         -23.6338 |           54.1414 |                                 0 |                           1 |
| full_market_ai_top8_and_active_positions_lt3_cold_start_ramp | 2021-07              | start_to_2026_06_30_only    |            967 |              967 |                0 |              0      |          16.5068 |          103.298  |                                 0 |                           1 |
| full_market_ai_top8_and_active_positions_lt3                 | 2022-01              | all_trading_end_dates_gt_1y |         354785 |           326508 |            28277 |              7.9702 |         -33.631  |           82.0748 |                                 0 |                           0 |
| full_market_ai_top8_and_active_positions_lt3                 | 2022-01              | start_to_2026_06_30_only    |            842 |              842 |                0 |              0      |          26.3113 |          126.111  |                                 0 |                           0 |
| full_market_ai_top8_and_active_positions_lt3_cold_start_ramp | 2022-01              | all_trading_end_dates_gt_1y |         354785 |           335623 |            19162 |              5.401  |         -19.1653 |           77.2136 |                                 0 |                           1 |
| full_market_ai_top8_and_active_positions_lt3_cold_start_ramp | 2022-01              | start_to_2026_06_30_only    |            842 |              842 |                0 |              0      |          13.9548 |          116.297  |                                 0 |                           1 |
| full_market_ai_top8_and_active_positions_lt3                 | 2022-07              | all_trading_end_dates_gt_1y |         263196 |           249402 |            13794 |              5.241  |         -44.1402 |           97.4327 |                                 0 |                           0 |
| full_market_ai_top8_and_active_positions_lt3                 | 2022-07              | start_to_2026_06_30_only    |            725 |              725 |                0 |              0      |          36.3311 |          141.183  |                                 0 |                           0 |
| full_market_ai_top8_and_active_positions_lt3_cold_start_ramp | 2022-07              | all_trading_end_dates_gt_1y |         263196 |           252037 |            11159 |              4.2398 |         -22.2161 |           91.0339 |                                 0 |                           1 |
| full_market_ai_top8_and_active_positions_lt3_cold_start_ramp | 2022-07              | start_to_2026_06_30_only    |            725 |              725 |                0 |              0      |          18.383  |          128.487  |                                 0 |                           1 |

## Worst Windows

| variant                                      | source_start_month   | window_type   | start_date   | end_date   |   period_calendar_days |   period_trading_days |   return_pct |   start_equity |   end_equity |
|:---------------------------------------------|:---------------------|:--------------|:-------------|:-----------|-----------------------:|----------------------:|-------------:|---------------:|-------------:|
| full_market_ai_top8_and_active_positions_lt3 | 2022-07              | all_gt_1y     | 2022-07-15   | 2023-07-17 |                    367 |                   244 |     -44.1402 |         288510 |       161161 |
| full_market_ai_top8_and_active_positions_lt3 | 2022-07              | all_gt_1y     | 2022-07-15   | 2023-07-24 |                    374 |                   249 |     -44.0882 |         288510 |       161311 |
| full_market_ai_top8_and_active_positions_lt3 | 2022-07              | all_gt_1y     | 2022-07-15   | 2023-07-18 |                    368 |                   245 |     -44.0292 |         288510 |       161481 |
| stage013_engine                              | 2022-07              | all_gt_1y     | 2022-07-15   | 2023-07-17 |                    367 |                   244 |     -43.794  |         288510 |       162160 |
| stage013_engine                              | 2022-07              | all_gt_1y     | 2022-07-15   | 2023-07-24 |                    374 |                   249 |     -43.742  |         288510 |       162310 |
| stage013_engine                              | 2022-07              | all_gt_1y     | 2022-07-15   | 2023-07-18 |                    368 |                   245 |     -43.6831 |         288510 |       162480 |
| stage013_engine                              | 2021-07              | all_gt_1y     | 2022-07-15   | 2023-10-23 |                    465 |                   308 |     -39.4246 |         357835 |       216760 |
| stage013_engine                              | 2021-07              | all_gt_1y     | 2022-07-15   | 2023-10-20 |                    462 |                   307 |     -39.4246 |         357835 |       216760 |
| stage013_engine                              | 2021-07              | all_gt_1y     | 2022-07-15   | 2023-10-19 |                    461 |                   306 |     -39.3966 |         357835 |       216860 |
| full_market_ai_top8_and_active_positions_lt3 | 2021-07              | all_gt_1y     | 2022-07-15   | 2023-10-23 |                    465 |                   308 |     -38.3634 |         360480 |       222188 |
| full_market_ai_top8_and_active_positions_lt3 | 2021-07              | all_gt_1y     | 2022-07-15   | 2023-10-20 |                    462 |                   307 |     -38.3634 |         360480 |       222188 |
| full_market_ai_top8_and_active_positions_lt3 | 2021-07              | all_gt_1y     | 2022-07-15   | 2023-10-19 |                    461 |                   306 |     -38.2213 |         360480 |       222700 |
| stage013_engine                              | 2021-07              | all_gt_1y     | 2021-10-26   | 2023-10-20 |                    724 |                   483 |     -35.2888 |         334965 |       216760 |
| stage013_engine                              | 2021-07              | all_gt_1y     | 2021-10-26   | 2023-10-23 |                    727 |                   484 |     -35.2888 |         334965 |       216760 |
| stage013_engine                              | 2021-07              | all_gt_1y     | 2021-10-26   | 2023-10-19 |                    723 |                   482 |     -35.2589 |         334965 |       216860 |
| stage013_engine                              | 2021-07              | all_gt_1y     | 2022-03-07   | 2023-10-23 |                    595 |                   396 |     -34.943  |         333185 |       216760 |
| stage013_engine                              | 2021-07              | all_gt_1y     | 2022-03-07   | 2023-10-20 |                    592 |                   395 |     -34.943  |         333185 |       216760 |
| stage013_engine                              | 2021-07              | all_gt_1y     | 2022-03-07   | 2023-10-19 |                    591 |                   394 |     -34.913  |         333185 |       216860 |
| full_market_ai_top8_and_active_positions_lt3 | 2022-07              | all_gt_1y     | 2022-07-19   | 2023-07-24 |                    370 |                   247 |     -34.7842 |         247350 |       161311 |
| full_market_ai_top8_and_active_positions_lt3 | 2022-07              | all_gt_1y     | 2022-07-19   | 2023-07-21 |                    367 |                   246 |     -34.4284 |         247350 |       162191 |
| full_market_ai_top8_and_active_positions_lt3 | 2022-07              | all_gt_1y     | 2022-07-19   | 2023-07-20 |                    366 |                   245 |     -34.4284 |         247350 |       162191 |
| stage013_engine                              | 2022-07              | all_gt_1y     | 2022-07-19   | 2023-07-24 |                    370 |                   247 |     -34.3804 |         247350 |       162310 |
| stage013_engine                              | 2021-07              | all_gt_1y     | 2022-03-09   | 2023-10-23 |                    593 |                   394 |     -34.1485 |         329165 |       216760 |
| stage013_engine                              | 2021-07              | all_gt_1y     | 2022-03-09   | 2023-10-20 |                    590 |                   393 |     -34.1485 |         329165 |       216760 |
| stage013_engine                              | 2021-07              | all_gt_1y     | 2021-10-27   | 2023-10-23 |                    726 |                   483 |     -34.1485 |         329165 |       216760 |
| stage013_engine                              | 2021-07              | all_gt_1y     | 2021-10-27   | 2023-10-20 |                    723 |                   482 |     -34.1485 |         329165 |       216760 |
| stage013_engine                              | 2021-07              | all_gt_1y     | 2022-03-09   | 2023-10-19 |                    589 |                   392 |     -34.1181 |         329165 |       216860 |
| stage013_engine                              | 2021-07              | all_gt_1y     | 2021-10-27   | 2023-10-19 |                    722 |                   481 |     -34.1181 |         329165 |       216860 |
| full_market_ai_top8_and_active_positions_lt3 | 2022-07              | all_gt_1y     | 2022-07-14   | 2023-07-17 |                    368 |                   245 |     -34.1177 |         244620 |       161161 |
| stage013_engine                              | 2022-01              | all_gt_1y     | 2022-07-15   | 2023-07-17 |                    367 |                   244 |     -34.0999 |         170250 |       112195 |
| full_market_ai_top8_and_active_positions_lt3 | 2022-07              | all_gt_1y     | 2022-07-14   | 2023-07-24 |                    375 |                   250 |     -34.0564 |         244620 |       161311 |
| stage013_engine                              | 2022-01              | all_gt_1y     | 2022-07-15   | 2023-07-18 |                    368 |                   245 |     -34.0294 |         170250 |       112315 |
| stage013_engine                              | 2022-07              | all_gt_1y     | 2022-07-19   | 2023-07-21 |                    367 |                   246 |     -34.0247 |         247350 |       163190 |
| stage013_engine                              | 2022-07              | all_gt_1y     | 2022-07-19   | 2023-07-20 |                    366 |                   245 |     -34.0247 |         247350 |       163190 |
| stage013_engine                              | 2022-01              | all_gt_1y     | 2022-07-15   | 2023-07-24 |                    374 |                   249 |     -33.9883 |         170250 |       112385 |
| full_market_ai_top8_and_active_positions_lt3 | 2022-07              | all_gt_1y     | 2022-07-14   | 2023-07-18 |                    369 |                   246 |     -33.9869 |         244620 |       161481 |
| full_market_ai_top8_and_active_positions_lt3 | 2022-07              | all_gt_1y     | 2022-07-18   | 2023-07-24 |                    371 |                   248 |     -33.9267 |         244140 |       161311 |
| stage013_engine                              | 2021-07              | all_gt_1y     | 2022-03-30   | 2023-10-20 |                    569 |                   378 |     -33.8208 |         327535 |       216760 |
| stage013_engine                              | 2021-07              | all_gt_1y     | 2022-03-30   | 2023-10-23 |                    572 |                   379 |     -33.8208 |         327535 |       216760 |
| stage013_engine                              | 2021-07              | all_gt_1y     | 2022-03-30   | 2023-10-19 |                    568 |                   377 |     -33.7903 |         327535 |       216860 |

## 输出

- panel_curves: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage074_cold_start_capital_ramp_proxy/rebuilt_c9_stage074_cold_start_capital_ramp_proxy_panel_curves_stage074_cold_start_capital_ramp_proxy_v1.csv.gz`
- source_summary: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage074_cold_start_capital_ramp_proxy/rebuilt_c9_stage074_cold_start_capital_ramp_proxy_source_summary_stage074_cold_start_capital_ramp_proxy_v1.csv`
- retention: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage074_cold_start_capital_ramp_proxy/rebuilt_c9_stage074_cold_start_capital_ramp_proxy_retention_stage074_cold_start_capital_ramp_proxy_v1.csv`
- goal_aggregate: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage074_cold_start_capital_ramp_proxy/rebuilt_c9_stage074_cold_start_capital_ramp_proxy_goal_aggregate_stage074_cold_start_capital_ramp_proxy_v1.csv`
- goal_worst_windows: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage074_cold_start_capital_ramp_proxy/rebuilt_c9_stage074_cold_start_capital_ramp_proxy_goal_worst_windows_stage074_cold_start_capital_ramp_proxy_v1.csv`
- decision: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage074_cold_start_capital_ramp_proxy/rebuilt_c9_stage074_cold_start_capital_ramp_proxy_decision_stage074_cold_start_capital_ramp_proxy_v1.json`
- report: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage074_cold_start_capital_ramp_proxy/rebuilt_c9_stage074_cold_start_capital_ramp_proxy_report_stage074_cold_start_capital_ramp_proxy_v1.md`
- absolute_equity_chart: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage074_cold_start_capital_ramp_proxy/rebuilt_c9_stage074_cold_start_capital_ramp_proxy_absolute_equity_chart_stage074_cold_start_capital_ramp_proxy_v1.png`
- target_absolute_equity_focus_chart: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage074_cold_start_capital_ramp_proxy/rebuilt_c9_stage074_cold_start_capital_ramp_proxy_target_absolute_equity_focus_chart_stage074_cold_start_capital_ramp_proxy_v1.png`
- absolute_equity_curve_summary: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage074_cold_start_capital_ramp_proxy/rebuilt_c9_stage074_cold_start_capital_ramp_proxy_absolute_equity_curve_summary_stage074_cold_start_capital_ramp_proxy_v1.csv`
