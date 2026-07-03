# Stage072 - q90 realized-vol 账户 overlay proxy

- 记录时间：`2026-07-02T00:52`
- line_id：`futures_trend_rebuilt_c9_15w_optimization`
- 当前模式：`day`
- model_tag：`stage072_q90_vol_overlay_proxy_v1`
- 是否重要突破版本：`否`
- 是否触发A/B：`是，A/B/C proxy`
- 决策：`stage072_q90_vol_overlay_partial_improvement_not_goal`

## 本次版本变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_optimization/tools/stage072_q90_vol_overlay_proxy.py`
- 新增测试：`tests/test_rebuilt_c9_stage072_q90_vol_overlay_proxy.py`
- 新增参数：`OVERLAY_LOOKBACK=63`、`OVERLAY_QUANTILE=0.9`、`OVERLAY_FLOOR=0.35`、`OVERLAY_MIN_HISTORY=126`。
- 修改参数：无，Stage013/Stage070/官方 C9 配置未改。
- 删除参数：无。
- 新增回测结果：Stage013 与 Stage070 最佳加风险曲线的账户外层 q90 vol overlay proxy。
- 本阶段不连接 CTP，不调用订单 API，不改实盘。

# Stage072 - q90 realized-vol 账户 overlay proxy

- 生成时间：`2026-07-02T00:52:57`
- 决策：`stage072_q90_vol_overlay_partial_improvement_not_goal`
- 下一步：`do_not_tune_overlay_quantile_turn_to_new_pit_or_account_outer_layer_design`
- 阶段性质：账户外层 closed-curve proxy；不是真实组合引擎，不改 C9，不连接 CTP，不调用下单。
- A/B/C：`{'A': 'stage013_engine', 'B': 'stage013_engine_q90_vol_overlay', 'C0': 'full_market_ai_top8_and_active_positions_lt3', 'C': 'full_market_ai_top8_and_active_positions_lt3_q90_vol_overlay'}`
- Overlay：`{'lookback': 63, 'min_periods': 20, 'quantile': 0.9, 'min_history': 126, 'floor': 0.35}`

## 结果摘要

| variant                                                      |   min_return_pct |   median_return_pct |   worst_max_dd_pct |   median_sharpe |   return_improved_count_vs_stage013 |   return_worse_count_vs_stage013 |   maxdd_improved_count_vs_stage013 |   maxdd_worse_count_vs_stage013 |   overlay_day_count_median |   mean_multiplier_median |   min_multiplier_min |   all_gt1y_window_count |   all_gt1y_negative_count |   all_gt1y_min_return_pct |   to_final_negative_count |   to_final_min_return_pct |   retention_vs_base_pass_count |   retention_vs_stage013_pass_count |   retention_rows |
|:-------------------------------------------------------------|-----------------:|--------------------:|-------------------:|----------------:|------------------------------------:|---------------------------------:|-----------------------------------:|--------------------------------:|---------------------------:|-------------------------:|---------------------:|------------------------:|--------------------------:|--------------------------:|--------------------------:|--------------------------:|-------------------------------:|-----------------------------------:|-----------------:|
| full_market_ai_top8_and_active_positions_lt3_q90_vol_overlay |           5.4611 |             252.33  |           -44.1402 |          1.3519 |                                  14 |                                3 |                                 14 |                               3 |                        104 |                   0.9787 |               0.4834 |                 7215647 |                    304177 |                  -44.1402 |                         0 |                   23.9691 |                             17 |                                 17 |               17 |
| full_market_ai_top8_and_active_positions_lt3                 |           5.4611 |             252.088 |           -44.1402 |          1.3109 |                                  17 |                                0 |                                 14 |                               3 |                          0 |                   1      |               1      |                 7215647 |                    315429 |                  -44.1402 |                         0 |                   26.3113 |                             17 |                                 17 |               17 |
| stage013_engine_q90_vol_overlay                              |           1.9011 |             241.798 |           -43.794  |          1.3231 |                                  11 |                                4 |                                  5 |                               6 |                        103 |                   0.9787 |               0.4841 |                 7215647 |                    318892 |                  -43.794  |                         0 |                   20.9465 |                             17 |                                 17 |               17 |
| stage013_engine                                              |           1.9011 |             238.369 |           -43.794  |          1.2722 |                                   0 |                                0 |                                  0 |                               0 |                          0 |                   1      |               1      |                 7215647 |                    330947 |                  -43.794  |                         0 |                   26.6753 |                              0 |                                  0 |                0 |

## 最差窗口

| variant                                                      | source_start_month   | window_type   | start_date   | end_date   |   period_calendar_days |   period_trading_days |   return_pct |   start_equity |   end_equity |
|:-------------------------------------------------------------|:---------------------|:--------------|:-------------|:-----------|-----------------------:|----------------------:|-------------:|---------------:|-------------:|
| full_market_ai_top8_and_active_positions_lt3                 | 2022-07              | all_gt_1y     | 2022-07-15   | 2023-07-17 |                    367 |                   244 |     -44.1402 |         288510 |       161161 |
| full_market_ai_top8_and_active_positions_lt3_q90_vol_overlay | 2022-07              | all_gt_1y     | 2022-07-15   | 2023-07-17 |                    367 |                   244 |     -44.1402 |         288510 |       161161 |
| full_market_ai_top8_and_active_positions_lt3                 | 2022-07              | all_gt_1y     | 2022-07-15   | 2023-07-24 |                    374 |                   249 |     -44.0882 |         288510 |       161311 |
| full_market_ai_top8_and_active_positions_lt3_q90_vol_overlay | 2022-07              | all_gt_1y     | 2022-07-15   | 2023-07-24 |                    374 |                   249 |     -44.0882 |         288510 |       161311 |
| full_market_ai_top8_and_active_positions_lt3                 | 2022-07              | all_gt_1y     | 2022-07-15   | 2023-07-18 |                    368 |                   245 |     -44.0292 |         288510 |       161481 |
| full_market_ai_top8_and_active_positions_lt3_q90_vol_overlay | 2022-07              | all_gt_1y     | 2022-07-15   | 2023-07-18 |                    368 |                   245 |     -44.0292 |         288510 |       161481 |
| stage013_engine                                              | 2022-07              | all_gt_1y     | 2022-07-15   | 2023-07-17 |                    367 |                   244 |     -43.794  |         288510 |       162160 |
| stage013_engine_q90_vol_overlay                              | 2022-07              | all_gt_1y     | 2022-07-15   | 2023-07-17 |                    367 |                   244 |     -43.794  |         288510 |       162160 |
| stage013_engine                                              | 2022-07              | all_gt_1y     | 2022-07-15   | 2023-07-24 |                    374 |                   249 |     -43.742  |         288510 |       162310 |
| stage013_engine_q90_vol_overlay                              | 2022-07              | all_gt_1y     | 2022-07-15   | 2023-07-24 |                    374 |                   249 |     -43.742  |         288510 |       162310 |
| stage013_engine_q90_vol_overlay                              | 2022-07              | all_gt_1y     | 2022-07-15   | 2023-07-18 |                    368 |                   245 |     -43.6831 |         288510 |       162480 |
| stage013_engine                                              | 2022-07              | all_gt_1y     | 2022-07-15   | 2023-07-18 |                    368 |                   245 |     -43.6831 |         288510 |       162480 |
| stage013_engine                                              | 2021-07              | all_gt_1y     | 2022-07-15   | 2023-10-20 |                    462 |                   307 |     -39.4246 |         357835 |       216760 |
| stage013_engine                                              | 2021-07              | all_gt_1y     | 2022-07-15   | 2023-10-23 |                    465 |                   308 |     -39.4246 |         357835 |       216760 |
| stage013_engine_q90_vol_overlay                              | 2021-07              | all_gt_1y     | 2022-07-15   | 2023-10-20 |                    462 |                   307 |     -39.4246 |         357835 |       216760 |
| stage013_engine_q90_vol_overlay                              | 2021-07              | all_gt_1y     | 2022-07-15   | 2023-10-23 |                    465 |                   308 |     -39.4246 |         357835 |       216760 |
| stage013_engine                                              | 2021-07              | all_gt_1y     | 2022-07-15   | 2023-10-19 |                    461 |                   306 |     -39.3966 |         357835 |       216860 |
| stage013_engine_q90_vol_overlay                              | 2021-07              | all_gt_1y     | 2022-07-15   | 2023-10-19 |                    461 |                   306 |     -39.3966 |         357835 |       216860 |
| full_market_ai_top8_and_active_positions_lt3                 | 2021-07              | all_gt_1y     | 2022-07-15   | 2023-10-23 |                    465 |                   308 |     -38.3634 |         360480 |       222188 |
| full_market_ai_top8_and_active_positions_lt3_q90_vol_overlay | 2021-07              | all_gt_1y     | 2022-07-15   | 2023-10-23 |                    465 |                   308 |     -38.3634 |         360480 |       222188 |
| full_market_ai_top8_and_active_positions_lt3                 | 2021-07              | all_gt_1y     | 2022-07-15   | 2023-10-20 |                    462 |                   307 |     -38.3634 |         360480 |       222188 |
| full_market_ai_top8_and_active_positions_lt3_q90_vol_overlay | 2021-07              | all_gt_1y     | 2022-07-15   | 2023-10-20 |                    462 |                   307 |     -38.3634 |         360480 |       222188 |
| full_market_ai_top8_and_active_positions_lt3                 | 2021-07              | all_gt_1y     | 2022-07-15   | 2023-10-19 |                    461 |                   306 |     -38.2213 |         360480 |       222700 |
| full_market_ai_top8_and_active_positions_lt3_q90_vol_overlay | 2021-07              | all_gt_1y     | 2022-07-15   | 2023-10-19 |                    461 |                   306 |     -38.2213 |         360480 |       222700 |

## 调研和判断结论

- 条件波动率目标资料显示高波动状态下风险管理可能降低尾部和回撤；pysystemtrade/Rob Carver 的风险 overlay 讨论同时提醒 overlay 会降低趋势正偏度，校准应按分布点或开启频率而不是回测收益调参。Stage072 因此固定 q90、63日、floor 0.35，只做账户外层 proxy，不扫参数。

## 反思

- 运行前过拟合反思：有风险但可控。账户 overlay 可能很容易被调成历史窗口补丁；本阶段只用固定 q90 分布点，不扫 lookback、floor 或 quantile。
- 运行后过拟合反思：否。本阶段没有根据结果调参；若继续改 q80/q95、floor、lookback 或按 2022 窗口定制，就是过拟合。
- 运行前继续价值反思：有。Stage071 证明加风险低覆盖剩余左尾，需要验证账户外层是否能低自由度缓冲。
- 运行后继续价值反思：若仍不能清零严格负窗口，则 q90 overlay 只能作为方向证据，下一步不能调参救它，应转新 PIT 信息源或更结构化账户设计。
