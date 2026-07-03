# Stage039 - full-market AI top8 非挤占加风险 proxy

- 记录时间：`2026-07-01T18:24`
- line_id：`futures_trend_rebuilt_c9_15w_optimization`
- model_tag：`stage039_full_market_ai_top8_proxy_v1`
- 是否重要突破版本：`否`
- 决策：`stage039_full_market_ai_top8_proxy_not_enough_no_param_rescue`

## 本次版本变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_optimization/tools/stage039_full_market_ai_top8_proxy.py`
- 新增参数：`selector=full_market_ai_top8`、`ADD_RISK_FRACTION=0.25`。
- 修改参数：无，Stage013/Stage006/官方 C9 配置未改。
- 删除参数：无。
- 新增回测结果：closed-lot 只读 proxy 目标审计；不是真实组合引擎。
- 本阶段不连接 CTP，不调用订单 API，不触发 A/B。

## 调研和判断结论

- 金融 ML / commodity ML 文献支持用 OOS 稳定的二级质量信号做 bet sizing；PBO/DSR 警告禁止多次扫 topN 和阈值。Stage039 因此只验证 Stage038 排名第一的 full_market_ai_top8，固定 25% 非挤占风险。

## 结果

- 选中 lots：`399`。
- selected realized PnL：`15,805,148.20`。
- proxy delta：`3,951,287.05`。
- Stage039 严格任意 `>1` 年负窗口：`332446` / `7215647`。
- Stage039 严格最差收益：`-44.1402%`。
- 到 `2026-06-30` 负窗口：`0`，最差 `34.2414%`。
- 收益保留 vs Stage006：`17/17`；vs Stage013：`17/17`。
- 收益改善/不变/变差 vs Stage013：`17/0/0`。
- 回撤改善/不变/变差 vs Stage013：`14/0/3`。

## 多起点摘要

| requested_start_month   |   total_return_pct_stage013_engine |   total_return_pct_stage039_full_market_ai_top8_proxy |   return_delta_pp_stage039_vs_stage013 |   max_dd_pct_stage013_engine |   max_dd_pct_stage039_full_market_ai_top8_proxy |
|:------------------------|-----------------------------------:|------------------------------------------------------:|---------------------------------------:|-----------------------------:|------------------------------------------------:|
| 2018-01                 |                          7678.8    |                                             8124.23   |                               445.429  |                     -37.3409 |                                        -36.219  |
| 2018-07                 |                          9880.13   |                                            10494.6    |                               614.447  |                     -37.9477 |                                        -36.7799 |
| 2019-01                 |                          9240.88   |                                             9840.77   |                               599.892  |                     -38.4073 |                                        -37.7925 |
| 2019-07                 |                          5298.26   |                                             5631.17   |                               332.917  |                     -37.5846 |                                        -36.7331 |
| 2020-01                 |                          3931.07   |                                             4180.7    |                               249.622  |                     -38.1717 |                                        -37.07   |
| 2020-07                 |                          3233.46   |                                             3415.15   |                               181.696  |                     -37.3761 |                                        -36.3203 |
| 2021-01                 |                          1451.64   |                                             1536.6    |                                84.9621 |                     -36.7684 |                                        -35.8424 |
| 2021-07                 |                           265.542  |                                              287.189  |                                21.6471 |                     -39.4246 |                                        -39.0076 |
| 2022-01                 |                           122.752  |                                              135.634  |                                12.8821 |                     -34.2643 |                                        -33.8119 |
| 2022-07                 |                           238.369  |                                              256.436  |                                18.0671 |                     -43.794  |                                        -44.1402 |
| 2023-01                 |                           134.445  |                                              147.021  |                                12.5754 |                     -24.469  |                                        -24.0856 |
| 2023-07                 |                           201.485  |                                              218.39   |                                16.9046 |                     -20.2875 |                                        -21.7164 |
| 2024-01                 |                           138.199  |                                              151.042  |                                12.843  |                     -18.6307 |                                        -19.2577 |
| 2024-07                 |                            57.5587 |                                               67.05   |                                 9.4913 |                     -20.3312 |                                        -17.905  |
| 2025-01                 |                            51.4687 |                                               61.8784 |                                10.4096 |                     -19.6119 |                                        -16.2201 |
| 2025-07                 |                            33.3787 |                                               40.225  |                                 6.8463 |                     -19.1855 |                                        -15.5409 |
| 2026-01                 |                             1.9011 |                                                5.4611 |                                 3.56   |                     -14.7303 |                                        -14.3019 |

## 严格目标摘要

| variant                            | source_start_month   | audit_scope                 | objective_start_min   | objective_start_max   |   window_count |   positive_count |   negative_count |   negative_rate_pct |   min_return_pct |   mean_return_pct |   is_independent_daily_cold_start |
|:-----------------------------------|:---------------------|:----------------------------|:----------------------|:----------------------|---------------:|-----------------:|-----------------:|--------------------:|-----------------:|------------------:|----------------------------------:|
| stage039_full_market_ai_top8_proxy | 2018-01              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |         882036 |           854141 |            27895 |              3.1626 |         -31.5906 |          765.028  |                                 0 |
| stage039_full_market_ai_top8_proxy | 2018-07              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |         882036 |           853565 |            28471 |              3.2279 |         -32.4373 |          824.891  |                                 0 |
| stage039_full_market_ai_top8_proxy | 2019-01              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |         882036 |           849430 |            32606 |              3.6967 |         -32.9177 |          829.162  |                                 0 |
| stage039_full_market_ai_top8_proxy | 2019-07              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |         882036 |           853563 |            28473 |              3.2281 |         -31.478  |          588.576  |                                 0 |
| stage039_full_market_ai_top8_proxy | 2020-01              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |         882036 |           852847 |            29189 |              3.3093 |         -31.7595 |          636.106  |                                 0 |
| stage039_full_market_ai_top8_proxy | 2020-07              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |         733565 |           703954 |            29611 |              4.0366 |         -31.4599 |          391.849  |                                 0 |
| stage039_full_market_ai_top8_proxy | 2021-01              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |         589005 |           552288 |            36717 |              6.2337 |         -31.9484 |          186.93   |                                 0 |
| stage039_full_market_ai_top8_proxy | 2021-07              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |         467873 |           392536 |            75337 |             16.102  |         -39.0076 |           64.5465 |                                 0 |
| stage039_full_market_ai_top8_proxy | 2022-01              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |         354785 |           325611 |            29174 |              8.223  |         -33.6491 |           85.6756 |                                 0 |
| stage039_full_market_ai_top8_proxy | 2022-07              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |         263196 |           249122 |            14074 |              5.3473 |         -44.1402 |           98.071  |                                 0 |
| stage039_full_market_ai_top8_proxy | 2023-01              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |         180432 |           179534 |              898 |              0.4977 |          -8.8514 |           98.9589 |                                 0 |
| stage039_full_market_ai_top8_proxy | 2023-07              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |         116529 |           116529 |                0 |              0      |           4.7976 |          108.716  |                                 0 |
| stage039_full_market_ai_top8_proxy | 2024-01              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |          64285 |            64284 |                1 |              0.0016 |          -0.058  |           83.6172 |                                 0 |
| stage039_full_market_ai_top8_proxy | 2024-07              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |          29059 |            29059 |                0 |              0      |           5      |           62.578  |                                 0 |
| stage039_full_market_ai_top8_proxy | 2025-01              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |           6738 |             6738 |                0 |              0      |          35.6794 |           68.9668 |                                 0 |
| stage039_full_market_ai_top8_proxy | 2025-07              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |              0 |                0 |                0 |                     |                  |                   |                                 0 |
| stage039_full_market_ai_top8_proxy | 2026-01              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |              0 |                0 |                0 |                     |                  |                   |                                 0 |

## 输出

- lot_deltas：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage039_full_market_ai_top8_proxy/rebuilt_c9_stage039_full_market_ai_top8_proxy_lot_deltas_stage039_full_market_ai_top8_proxy_v1.csv`
- curves：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage039_full_market_ai_top8_proxy/rebuilt_c9_stage039_full_market_ai_top8_proxy_curves_stage039_full_market_ai_top8_proxy_v1.csv`
- summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage039_full_market_ai_top8_proxy/rebuilt_c9_stage039_full_market_ai_top8_proxy_summary_stage039_full_market_ai_top8_proxy_v1.csv`
- goal_aggregate：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage039_full_market_ai_top8_proxy/rebuilt_c9_stage039_full_market_ai_top8_proxy_goal_aggregate_stage039_full_market_ai_top8_proxy_v1.csv`
- retention：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage039_full_market_ai_top8_proxy/rebuilt_c9_stage039_full_market_ai_top8_proxy_retention_stage039_full_market_ai_top8_proxy_v1.csv`
- decision：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage039_full_market_ai_top8_proxy/rebuilt_c9_stage039_full_market_ai_top8_proxy_decision_stage039_full_market_ai_top8_proxy_v1.json`
- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage039_full_market_ai_top8_proxy/rebuilt_c9_stage039_full_market_ai_top8_proxy_report_stage039_full_market_ai_top8_proxy_v1.md`

## 反思

- 运行前过拟合反思：否。只冻结 Stage038 排名第一且 OOS 通过的 `full_market_ai_top8`，不扫 topN、simple 共识、倍率或年份。
- 运行后过拟合反思：否。本阶段无参数搜索；若失败后改 topN、组合 OI、筛年份或按产品救参就是过拟合。
- 运行前继续价值反思：有。用户目标包含 AI 选品优化和超高质量信号加风险，必须用目标窗口审计确认该信号是否有策略价值。
- 运行后继续价值反思：有限。若没有改善严格负窗口或收益保留失败，就不应继续在 full_market_ai_top8 上调参。
