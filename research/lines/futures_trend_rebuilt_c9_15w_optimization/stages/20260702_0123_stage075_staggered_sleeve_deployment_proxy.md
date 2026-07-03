# Stage075 分批多袖账户部署 proxy

- 记录时间：2026-07-02 01:23 CST
- line_id：`futures_trend_rebuilt_c9_15w_optimization`
- model_tag：`stage075_staggered_sleeve_deployment_proxy_v1`
- 是否重要突破版本：否
- 新增参数：`stage075_sleeve_offsets=(0,63,126,189)`、`stage075_sleeve_count=4`。
- 修改参数：无正式策略参数修改；本阶段是账户外层 proxy。
- 删除参数：无。

# Stage075 staggered sleeve deployment proxy

## 结论

- 决策：`stage075_staggered_sleeve_proxy_not_goal_no_param_rescue`
- 下一步：停止 sleeve_count/offset 救参；若继续账户外层，需要不同结构或新 PIT 信息源
- A/B/C：A=`stage013_engine`，B=`stage013_engine_staggered_sleeve`，C0=`full_market_ai_top8_and_active_positions_lt3`，C=`full_market_ai_top8_and_active_positions_lt3_staggered_sleeve`
- 固定参数：`sleeve_offsets=[0, 63, 126, 189]`，`sleeve_count=4`。

## 外部调研判断

- Managed futures/pysystemtrade 资料支持组合层 allocation、risk target 与 capital correction；但趋势右尾脆弱，失败后不能扫袖数、offset 或坏窗口。
- 本阶段只验证一个固定账户部署结构，不改信号、不改 AI 池、不改品种、不按坏窗口调参数。

## 过拟合与继续价值反思

- 开始是否过拟合：否。候选是账户部署结构，固定 4 个等权袖和 0/63/126/189 交易日投入，不按坏窗口调参。
- 结束是否过拟合：否。本阶段没有根据结果调整袖数或 offset；若失败后继续扫这些参数就是过拟合。
- 开始是否值得继续：有。任意起点目标本质包含冷启动路径依赖，分批部署直接针对该结构问题。
- 结束是否值得继续：该固定分袖形状若不达标就无救参价值；应转新 PIT 信息源或不同账户外层结构。

## Variant Summary

| variant                                                       |   min_return_pct |   median_return_pct |   worst_max_dd_pct |   median_sharpe |   all_gt1y_window_count |   all_gt1y_negative_count |   all_gt1y_min_return_pct |   to_final_negative_count |   to_final_min_return_pct |   retention_vs_base_stage006_pass_count |   retention_vs_stage013_pass_count |   retention_rows |
|:--------------------------------------------------------------|-----------------:|--------------------:|-------------------:|----------------:|------------------------:|--------------------------:|--------------------------:|--------------------------:|--------------------------:|----------------------------------------:|-----------------------------------:|-----------------:|
| full_market_ai_top8_and_active_positions_lt3                  |           5.4611 |             252.088 |           -44.1402 |          1.3109 |                 7215647 |                    315429 |                  -44.1402 |                         0 |                   26.3113 |                                         |                                    |                0 |
| full_market_ai_top8_and_active_positions_lt3_staggered_sleeve |          -1.6714 |             213.491 |           -51.2562 |          1.1334 |                 7215647 |                    325602 |                  -31.7355 |                         0 |                    9.7091 |                                      15 |                                 15 |               17 |
| stage013_engine                                               |           1.9011 |             238.369 |           -43.794  |          1.2722 |                 7215647 |                    330947 |                  -43.794  |                         0 |                   26.6753 |                                         |                                    |                0 |
| stage013_engine_staggered_sleeve                              |          -2.5614 |             205.536 |           -52.6741 |          1.0969 |                 7215647 |                    336672 |                  -32.872  |                         0 |                    9.7937 |                                      15 |                                 14 |               17 |

## Goal Aggregate

| variant                                                       | source_start_month   | audit_scope                 |   window_count |   positive_count |   negative_count |   negative_rate_pct |   min_return_pct |   mean_return_pct |   is_independent_daily_cold_start |   is_staggered_sleeve_proxy |
|:--------------------------------------------------------------|:---------------------|:----------------------------|---------------:|-----------------:|-----------------:|--------------------:|-----------------:|------------------:|----------------------------------:|----------------------------:|
| full_market_ai_top8_and_active_positions_lt3                  | 2018-01              | all_trading_end_dates_gt_1y |         882036 |           856165 |            25871 |              2.9331 |         -31.5683 |          757.643  |                                 0 |                           0 |
| full_market_ai_top8_and_active_positions_lt3                  | 2018-01              | start_to_2026_06_30_only    |           1328 |             1328 |                0 |              0      |          28.0729 |          874.637  |                                 0 |                           0 |
| full_market_ai_top8_and_active_positions_lt3_staggered_sleeve | 2018-01              | all_trading_end_dates_gt_1y |         882036 |           854067 |            27969 |              3.171  |         -20.8246 |          696.409  |                                 0 |                           1 |
| full_market_ai_top8_and_active_positions_lt3_staggered_sleeve | 2018-01              | start_to_2026_06_30_only    |           1328 |             1328 |                0 |              0      |           9.7091 |          830.547  |                                 0 |                           1 |
| full_market_ai_top8_and_active_positions_lt3                  | 2018-07              | all_trading_end_dates_gt_1y |         882036 |           855594 |            26442 |              2.9978 |         -32.4206 |          812.646  |                                 0 |                           0 |
| full_market_ai_top8_and_active_positions_lt3                  | 2018-07              | start_to_2026_06_30_only    |           1328 |             1328 |                0 |              0      |          30.7608 |          916.095  |                                 0 |                           0 |
| full_market_ai_top8_and_active_positions_lt3_staggered_sleeve | 2018-07              | all_trading_end_dates_gt_1y |         882036 |           853088 |            28948 |              3.282  |         -21.5991 |          748.947  |                                 0 |                           1 |
| full_market_ai_top8_and_active_positions_lt3_staggered_sleeve | 2018-07              | start_to_2026_06_30_only    |           1328 |             1328 |                0 |              0      |          10.0987 |          870.686  |                                 0 |                           1 |
| full_market_ai_top8_and_active_positions_lt3                  | 2019-01              | all_trading_end_dates_gt_1y |         882036 |           851959 |            30077 |              3.41   |         -32.8977 |          816.412  |                                 0 |                           0 |
| full_market_ai_top8_and_active_positions_lt3                  | 2019-01              | start_to_2026_06_30_only    |           1328 |             1328 |                0 |              0      |          29.6473 |          975.692  |                                 0 |                           0 |
| full_market_ai_top8_and_active_positions_lt3_staggered_sleeve | 2019-01              | all_trading_end_dates_gt_1y |         882036 |           852484 |            29552 |              3.3504 |         -22.3214 |          753.181  |                                 0 |                           1 |
| full_market_ai_top8_and_active_positions_lt3_staggered_sleeve | 2019-01              | start_to_2026_06_30_only    |           1328 |             1328 |                0 |              0      |           9.872  |          930.112  |                                 0 |                           1 |
| full_market_ai_top8_and_active_positions_lt3                  | 2019-07              | all_trading_end_dates_gt_1y |         882036 |           855607 |            26429 |              2.9964 |         -31.4469 |          580.601  |                                 0 |                           0 |
| full_market_ai_top8_and_active_positions_lt3                  | 2019-07              | start_to_2026_06_30_only    |           1328 |             1328 |                0 |              0      |          39.6755 |          748.031  |                                 0 |                           0 |
| full_market_ai_top8_and_active_positions_lt3_staggered_sleeve | 2019-07              | all_trading_end_dates_gt_1y |         882036 |           854790 |            27246 |              3.089  |         -19.8748 |          530.538  |                                 0 |                           1 |
| full_market_ai_top8_and_active_positions_lt3_staggered_sleeve | 2019-07              | start_to_2026_06_30_only    |           1328 |             1328 |                0 |              0      |          16.7635 |          710.366  |                                 0 |                           1 |
| full_market_ai_top8_and_active_positions_lt3                  | 2020-01              | all_trading_end_dates_gt_1y |         882036 |           855078 |            26958 |              3.0563 |         -31.7195 |          627.454  |                                 0 |                           0 |
| full_market_ai_top8_and_active_positions_lt3                  | 2020-01              | start_to_2026_06_30_only    |           1328 |             1328 |                0 |              0      |          40.2034 |          799.564  |                                 0 |                           0 |
| full_market_ai_top8_and_active_positions_lt3_staggered_sleeve | 2020-01              | all_trading_end_dates_gt_1y |         882036 |           854241 |            27795 |              3.1512 |         -20.2236 |          574.358  |                                 0 |                           1 |
| full_market_ai_top8_and_active_positions_lt3_staggered_sleeve | 2020-01              | start_to_2026_06_30_only    |           1328 |             1328 |                0 |              0      |          16.9396 |          760.114  |                                 0 |                           1 |
| full_market_ai_top8_and_active_positions_lt3                  | 2020-07              | all_trading_end_dates_gt_1y |         733565 |           706368 |            27197 |              3.7075 |         -31.4102 |          386.715  |                                 0 |                           0 |
| full_market_ai_top8_and_active_positions_lt3                  | 2020-07              | start_to_2026_06_30_only    |           1211 |             1211 |                0 |              0      |          36.7453 |          477.963  |                                 0 |                           0 |
| full_market_ai_top8_and_active_positions_lt3_staggered_sleeve | 2020-07              | all_trading_end_dates_gt_1y |         733565 |           705295 |            28270 |              3.8538 |         -19.8934 |          333.697  |                                 0 |                           1 |
| full_market_ai_top8_and_active_positions_lt3_staggered_sleeve | 2020-07              | start_to_2026_06_30_only    |           1211 |             1211 |                0 |              0      |          15.436  |          440.411  |                                 0 |                           1 |
| full_market_ai_top8_and_active_positions_lt3                  | 2021-01              | all_trading_end_dates_gt_1y |         589005 |           553820 |            35185 |              5.9736 |         -31.7901 |          182.02   |                                 0 |                           0 |
| full_market_ai_top8_and_active_positions_lt3                  | 2021-01              | start_to_2026_06_30_only    |           1085 |             1085 |                0 |              0      |          35.8694 |          243.744  |                                 0 |                           0 |
| full_market_ai_top8_and_active_positions_lt3_staggered_sleeve | 2021-01              | all_trading_end_dates_gt_1y |         589005 |           545516 |            43489 |              7.3835 |         -20.7399 |          143.964  |                                 0 |                           1 |
| full_market_ai_top8_and_active_positions_lt3_staggered_sleeve | 2021-01              | start_to_2026_06_30_only    |           1085 |             1085 |                0 |              0      |          14.7526 |          215.813  |                                 0 |                           1 |
| full_market_ai_top8_and_active_positions_lt3                  | 2021-07              | all_trading_end_dates_gt_1y |         467873 |           393572 |            74301 |             15.8806 |         -38.3634 |           61.5016 |                                 0 |                           0 |
| full_market_ai_top8_and_active_positions_lt3                  | 2021-07              | start_to_2026_06_30_only    |            967 |              967 |                0 |              0      |          31.0859 |          112.87   |                                 0 |                           0 |
| full_market_ai_top8_and_active_positions_lt3_staggered_sleeve | 2021-07              | all_trading_end_dates_gt_1y |         467873 |           381742 |            86130 |             18.4088 |         -31.7355 |           52.6027 |                                 0 |                           1 |
| full_market_ai_top8_and_active_positions_lt3_staggered_sleeve | 2021-07              | start_to_2026_06_30_only    |            967 |              967 |                0 |              0      |          12.7393 |          101.693  |                                 0 |                           1 |
| full_market_ai_top8_and_active_positions_lt3                  | 2022-01              | all_trading_end_dates_gt_1y |         354785 |           326508 |            28277 |              7.9702 |         -33.631  |           82.0748 |                                 0 |                           0 |
| full_market_ai_top8_and_active_positions_lt3                  | 2022-01              | start_to_2026_06_30_only    |            842 |              842 |                0 |              0      |          26.3113 |          126.111  |                                 0 |                           0 |
| full_market_ai_top8_and_active_positions_lt3_staggered_sleeve | 2022-01              | all_trading_end_dates_gt_1y |         354785 |           337025 |            17760 |              5.0058 |         -27.1112 |           76.7858 |                                 0 |                           1 |
| full_market_ai_top8_and_active_positions_lt3_staggered_sleeve | 2022-01              | start_to_2026_06_30_only    |            842 |              842 |                0 |              0      |          10.7226 |          115.031  |                                 0 |                           1 |
| full_market_ai_top8_and_active_positions_lt3                  | 2022-07              | all_trading_end_dates_gt_1y |         263196 |           249402 |            13794 |              5.241  |         -44.1402 |           97.4327 |                                 0 |                           0 |
| full_market_ai_top8_and_active_positions_lt3                  | 2022-07              | start_to_2026_06_30_only    |            725 |              725 |                0 |              0      |          36.3311 |          141.183  |                                 0 |                           0 |
| full_market_ai_top8_and_active_positions_lt3_staggered_sleeve | 2022-07              | all_trading_end_dates_gt_1y |         263196 |           255860 |             7336 |              2.7873 |         -17.672  |           91.0129 |                                 0 |                           1 |
| full_market_ai_top8_and_active_positions_lt3_staggered_sleeve | 2022-07              | start_to_2026_06_30_only    |            725 |              725 |                0 |              0      |          13.7245 |          127.043  |                                 0 |                           1 |

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
| stage013_engine                              | 2021-07              | all_gt_1y     | 2022-03-07   | 2023-10-20 |                    592 |                   395 |     -34.943  |         333185 |       216760 |
| stage013_engine                              | 2021-07              | all_gt_1y     | 2022-03-07   | 2023-10-23 |                    595 |                   396 |     -34.943  |         333185 |       216760 |
| stage013_engine                              | 2021-07              | all_gt_1y     | 2022-03-07   | 2023-10-19 |                    591 |                   394 |     -34.913  |         333185 |       216860 |
| full_market_ai_top8_and_active_positions_lt3 | 2022-07              | all_gt_1y     | 2022-07-19   | 2023-07-24 |                    370 |                   247 |     -34.7842 |         247350 |       161311 |
| full_market_ai_top8_and_active_positions_lt3 | 2022-07              | all_gt_1y     | 2022-07-19   | 2023-07-21 |                    367 |                   246 |     -34.4284 |         247350 |       162191 |
| full_market_ai_top8_and_active_positions_lt3 | 2022-07              | all_gt_1y     | 2022-07-19   | 2023-07-20 |                    366 |                   245 |     -34.4284 |         247350 |       162191 |
| stage013_engine                              | 2022-07              | all_gt_1y     | 2022-07-19   | 2023-07-24 |                    370 |                   247 |     -34.3804 |         247350 |       162310 |
| stage013_engine                              | 2021-07              | all_gt_1y     | 2022-03-09   | 2023-10-20 |                    590 |                   393 |     -34.1485 |         329165 |       216760 |
| stage013_engine                              | 2021-07              | all_gt_1y     | 2022-03-09   | 2023-10-23 |                    593 |                   394 |     -34.1485 |         329165 |       216760 |
| stage013_engine                              | 2021-07              | all_gt_1y     | 2021-10-27   | 2023-10-20 |                    723 |                   482 |     -34.1485 |         329165 |       216760 |
| stage013_engine                              | 2021-07              | all_gt_1y     | 2021-10-27   | 2023-10-23 |                    726 |                   483 |     -34.1485 |         329165 |       216760 |
| stage013_engine                              | 2021-07              | all_gt_1y     | 2022-03-09   | 2023-10-19 |                    589 |                   392 |     -34.1181 |         329165 |       216860 |
| stage013_engine                              | 2021-07              | all_gt_1y     | 2021-10-27   | 2023-10-19 |                    722 |                   481 |     -34.1181 |         329165 |       216860 |
| full_market_ai_top8_and_active_positions_lt3 | 2022-07              | all_gt_1y     | 2022-07-14   | 2023-07-17 |                    368 |                   245 |     -34.1177 |         244620 |       161161 |
| stage013_engine                              | 2022-01              | all_gt_1y     | 2022-07-15   | 2023-07-17 |                    367 |                   244 |     -34.0999 |         170250 |       112195 |
| full_market_ai_top8_and_active_positions_lt3 | 2022-07              | all_gt_1y     | 2022-07-14   | 2023-07-24 |                    375 |                   250 |     -34.0564 |         244620 |       161311 |
| stage013_engine                              | 2022-01              | all_gt_1y     | 2022-07-15   | 2023-07-18 |                    368 |                   245 |     -34.0294 |         170250 |       112315 |
| stage013_engine                              | 2022-07              | all_gt_1y     | 2022-07-19   | 2023-07-20 |                    366 |                   245 |     -34.0247 |         247350 |       163190 |
| stage013_engine                              | 2022-07              | all_gt_1y     | 2022-07-19   | 2023-07-21 |                    367 |                   246 |     -34.0247 |         247350 |       163190 |
| stage013_engine                              | 2022-01              | all_gt_1y     | 2022-07-15   | 2023-07-24 |                    374 |                   249 |     -33.9883 |         170250 |       112385 |
| full_market_ai_top8_and_active_positions_lt3 | 2022-07              | all_gt_1y     | 2022-07-14   | 2023-07-18 |                    369 |                   246 |     -33.9869 |         244620 |       161481 |
| full_market_ai_top8_and_active_positions_lt3 | 2022-07              | all_gt_1y     | 2022-07-18   | 2023-07-24 |                    371 |                   248 |     -33.9267 |         244140 |       161311 |
| stage013_engine                              | 2021-07              | all_gt_1y     | 2022-03-30   | 2023-10-20 |                    569 |                   378 |     -33.8208 |         327535 |       216760 |
| stage013_engine                              | 2021-07              | all_gt_1y     | 2022-03-30   | 2023-10-23 |                    572 |                   379 |     -33.8208 |         327535 |       216760 |
| stage013_engine                              | 2021-07              | all_gt_1y     | 2022-03-30   | 2023-10-19 |                    568 |                   377 |     -33.7903 |         327535 |       216860 |

## 输出

- panel_curves: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage075_staggered_sleeve_deployment_proxy/rebuilt_c9_stage075_staggered_sleeve_deployment_proxy_panel_curves_stage075_staggered_sleeve_deployment_proxy_v1.csv.gz`
- source_summary: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage075_staggered_sleeve_deployment_proxy/rebuilt_c9_stage075_staggered_sleeve_deployment_proxy_source_summary_stage075_staggered_sleeve_deployment_proxy_v1.csv`
- retention: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage075_staggered_sleeve_deployment_proxy/rebuilt_c9_stage075_staggered_sleeve_deployment_proxy_retention_stage075_staggered_sleeve_deployment_proxy_v1.csv`
- goal_aggregate: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage075_staggered_sleeve_deployment_proxy/rebuilt_c9_stage075_staggered_sleeve_deployment_proxy_goal_aggregate_stage075_staggered_sleeve_deployment_proxy_v1.csv`
- goal_worst_windows: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage075_staggered_sleeve_deployment_proxy/rebuilt_c9_stage075_staggered_sleeve_deployment_proxy_goal_worst_windows_stage075_staggered_sleeve_deployment_proxy_v1.csv`
- variant_summary: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage075_staggered_sleeve_deployment_proxy/rebuilt_c9_stage075_staggered_sleeve_deployment_proxy_variant_summary_stage075_staggered_sleeve_deployment_proxy_v1.csv`
- decision: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage075_staggered_sleeve_deployment_proxy/rebuilt_c9_stage075_staggered_sleeve_deployment_proxy_decision_stage075_staggered_sleeve_deployment_proxy_v1.json`
- report: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage075_staggered_sleeve_deployment_proxy/rebuilt_c9_stage075_staggered_sleeve_deployment_proxy_report_stage075_staggered_sleeve_deployment_proxy_v1.md`
- absolute_equity_chart: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage075_staggered_sleeve_deployment_proxy/rebuilt_c9_stage075_staggered_sleeve_deployment_proxy_absolute_equity_chart_stage075_staggered_sleeve_deployment_proxy_v1.png`
- target_absolute_equity_focus_chart: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage075_staggered_sleeve_deployment_proxy/rebuilt_c9_stage075_staggered_sleeve_deployment_proxy_target_absolute_equity_focus_chart_stage075_staggered_sleeve_deployment_proxy_v1.png`
