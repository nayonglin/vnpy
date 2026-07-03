# Stage070 - Stage068 sibling composite 加风险面板

- 记录时间：`2026-07-02T00:36`
- line_id：`futures_trend_rebuilt_c9_15w_optimization`
- 当前模式：`day`
- model_tag：`stage070_super_quality_sibling_panel_v1`
- 是否重要突破版本：`否`
- 是否触发A/B：`是，A/C sibling panel proxy`
- 决策：`stage070_sibling_panel_partial_improvement_no_goal`

## 本次版本变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_optimization/tools/stage070_super_quality_sibling_panel.py`
- 新增测试：`tests/test_rebuilt_c9_stage070_super_quality_sibling_panel.py`
- 新增参数：`candidate_variants=full_market_ai_top8_and_account_injured,full_market_ai_top8_and_ai_rank_1_6,full_market_ai_top8_and_active_positions_lt3`、`ADD_RISK_FRACTION=0.25`。
- 修改参数：无，Stage013/Stage006/官方 C9 配置未改。
- 删除参数：无。
- 新增回测结果：Stage068 sibling composite closed-lot 只读 proxy 面板；不是真实组合引擎。
- 本阶段不连接 CTP，不调用订单 API，不改实盘。

## 外部调研与判断

- Stage070 只比较 Stage068 已通过的低自由度 new composite，同一固定 25% 非挤占风险；这不是 topN/阈值/品种方向扫参。若面板仍不达标，应停止 Stage068 加风险形状。

# Stage070 - Stage068 sibling composite 加风险面板

- 生成时间：`2026-07-02T00:36:26`
- 决策：`stage070_sibling_panel_partial_improvement_no_goal`
- 下一步：`do_not_tune_panel_candidates_turn_to_failure_attribution_or_account_layer`
- 阶段性质：closed-lot 只读面板；不是真实组合引擎，不改 C9，不连接 CTP，不调用下单。
- 候选：Stage068 已通过的 3 个 new composite；固定 `+25%` 非挤占风险。

## 结果摘要

| variant                                      |   selected_lots |   selected_open_trades |   selected_realized_pnl |   total_proxy_delta_pnl |   min_return_pct |   median_return_pct |   worst_max_dd_pct |   median_sharpe |   return_improved_count_vs_stage013 |   return_worse_count_vs_stage013 |   maxdd_improved_count_vs_stage013 |   maxdd_worse_count_vs_stage013 |   all_gt1y_window_count |   all_gt1y_negative_count |   all_gt1y_min_return_pct |   to_final_negative_count |   to_final_min_return_pct |   retention_vs_base_pass_count |   retention_vs_stage013_pass_count |   retention_rows |
|:---------------------------------------------|----------------:|-----------------------:|------------------------:|------------------------:|-----------------:|--------------------:|-------------------:|----------------:|------------------------------------:|---------------------------------:|-----------------------------------:|--------------------------------:|------------------------:|--------------------------:|--------------------------:|--------------------------:|--------------------------:|-------------------------------:|-----------------------------------:|-----------------:|
| full_market_ai_top8_and_active_positions_lt3 |             246 |                    246 |             3.35145e+06 |                  837862 |           5.4611 |             252.088 |           -44.1402 |          1.3109 |                                  17 |                                0 |                                 14 |                               3 |                 7215647 |                    315429 |                  -44.1402 |                         0 |                   26.3113 |                             17 |                                 17 |               17 |
| full_market_ai_top8_and_account_injured      |             161 |                    161 |             2.1501e+06  |                  537525 |           5.4611 |             254.107 |           -44.1402 |          1.3267 |                                  16 |                                1 |                                  8 |                               9 |                 7215647 |                    330030 |                  -44.1402 |                         0 |                   26.5269 |                             17 |                                 17 |               17 |
| full_market_ai_top8_and_ai_rank_1_6          |             157 |                    157 |             1.92113e+06 |                  480282 |           1.9011 |             250.535 |           -44.2073 |          1.3054 |                                  15 |                                1 |                                  4 |                               3 |                 7215647 |                    330055 |                  -44.2073 |                         0 |                   26.522  |                             17 |                                 17 |               17 |

## 最差窗口

| variant                                      | source_start_month   | window_type   | start_date   | end_date   |   period_calendar_days |   period_trading_days |   return_pct |   start_equity |   end_equity |
|:---------------------------------------------|:---------------------|:--------------|:-------------|:-----------|-----------------------:|----------------------:|-------------:|---------------:|-------------:|
| full_market_ai_top8_and_ai_rank_1_6          | 2022-07              | all_gt_1y     | 2022-07-15   | 2023-07-17 |                    367 |                   244 |     -44.2073 |         288510 |       160968 |
| full_market_ai_top8_and_ai_rank_1_6          | 2022-07              | all_gt_1y     | 2022-07-15   | 2023-07-24 |                    374 |                   249 |     -44.1553 |         288510 |       161118 |
| full_market_ai_top8_and_account_injured      | 2022-07              | all_gt_1y     | 2022-07-15   | 2023-07-17 |                    367 |                   244 |     -44.1402 |         288510 |       161161 |
| full_market_ai_top8_and_active_positions_lt3 | 2022-07              | all_gt_1y     | 2022-07-15   | 2023-07-17 |                    367 |                   244 |     -44.1402 |         288510 |       161161 |
| full_market_ai_top8_and_ai_rank_1_6          | 2022-07              | all_gt_1y     | 2022-07-15   | 2023-07-18 |                    368 |                   245 |     -44.0964 |         288510 |       161288 |
| full_market_ai_top8_and_active_positions_lt3 | 2022-07              | all_gt_1y     | 2022-07-15   | 2023-07-24 |                    374 |                   249 |     -44.0882 |         288510 |       161311 |
| full_market_ai_top8_and_account_injured      | 2022-07              | all_gt_1y     | 2022-07-15   | 2023-07-24 |                    374 |                   249 |     -44.0882 |         288510 |       161311 |
| full_market_ai_top8_and_active_positions_lt3 | 2022-07              | all_gt_1y     | 2022-07-15   | 2023-07-18 |                    368 |                   245 |     -44.0292 |         288510 |       161481 |
| full_market_ai_top8_and_account_injured      | 2022-07              | all_gt_1y     | 2022-07-15   | 2023-07-18 |                    368 |                   245 |     -44.0292 |         288510 |       161481 |
| stage013_engine                              | 2022-07              | all_gt_1y     | 2022-07-15   | 2023-07-17 |                    367 |                   244 |     -43.794  |         288510 |       162160 |
| stage013_engine                              | 2022-07              | all_gt_1y     | 2022-07-15   | 2023-07-24 |                    374 |                   249 |     -43.742  |         288510 |       162310 |
| stage013_engine                              | 2022-07              | all_gt_1y     | 2022-07-15   | 2023-07-18 |                    368 |                   245 |     -43.6831 |         288510 |       162480 |
| stage013_engine                              | 2021-07              | all_gt_1y     | 2022-07-15   | 2023-10-20 |                    462 |                   307 |     -39.4246 |         357835 |       216760 |
| stage013_engine                              | 2021-07              | all_gt_1y     | 2022-07-15   | 2023-10-23 |                    465 |                   308 |     -39.4246 |         357835 |       216760 |
| stage013_engine                              | 2021-07              | all_gt_1y     | 2022-07-15   | 2023-10-19 |                    461 |                   306 |     -39.3966 |         357835 |       216860 |
| full_market_ai_top8_and_account_injured      | 2021-07              | all_gt_1y     | 2022-07-15   | 2023-10-23 |                    465 |                   308 |     -38.6486 |         357820 |       219528 |
| full_market_ai_top8_and_account_injured      | 2021-07              | all_gt_1y     | 2022-07-15   | 2023-10-20 |                    462 |                   307 |     -38.6486 |         357820 |       219528 |
| full_market_ai_top8_and_ai_rank_1_6          | 2021-07              | all_gt_1y     | 2022-07-15   | 2023-10-20 |                    462 |                   307 |     -38.5904 |         357835 |       219745 |
| full_market_ai_top8_and_ai_rank_1_6          | 2021-07              | all_gt_1y     | 2022-07-15   | 2023-10-23 |                    465 |                   308 |     -38.5904 |         357835 |       219745 |
| full_market_ai_top8_and_account_injured      | 2021-07              | all_gt_1y     | 2022-07-15   | 2023-10-19 |                    461 |                   306 |     -38.5054 |         357820 |       220040 |
| full_market_ai_top8_and_ai_rank_1_6          | 2021-07              | all_gt_1y     | 2022-07-15   | 2023-10-19 |                    461 |                   306 |     -38.4472 |         357835 |       220258 |
| full_market_ai_top8_and_active_positions_lt3 | 2021-07              | all_gt_1y     | 2022-07-15   | 2023-10-20 |                    462 |                   307 |     -38.3634 |         360480 |       222188 |
| full_market_ai_top8_and_active_positions_lt3 | 2021-07              | all_gt_1y     | 2022-07-15   | 2023-10-23 |                    465 |                   308 |     -38.3634 |         360480 |       222188 |
| full_market_ai_top8_and_active_positions_lt3 | 2021-07              | all_gt_1y     | 2022-07-15   | 2023-10-19 |                    461 |                   306 |     -38.2213 |         360480 |       222700 |

## 反思

- 运行前过拟合反思：否。候选集合在 Stage068 已冻结，本阶段不新增阈值、不改风险比例、不加入诊断项。
- 运行后过拟合反思：否。结果只用于判断 Stage068 加风险形状是否整体有目标价值；不能根据排名继续调参。
- 运行前继续价值反思：有。Stage069 最强均值候选只部分改善，需要确认 sibling 候选是否更贴合目标左尾。
- 运行后继续价值反思：若无候选清零严格负窗口，则继续价值转向失败归因、账户外层或新 PIT 信息源，不继续救 Stage068 组合。
