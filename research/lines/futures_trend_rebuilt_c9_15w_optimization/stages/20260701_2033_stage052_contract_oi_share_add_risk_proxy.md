# Stage052 - contract_oi_share_ge50 非挤占加风险 proxy

- 记录时间：`2026-07-01T20:33`
- line_id：`futures_trend_rebuilt_c9_15w_optimization`
- model_tag：`stage052_contract_oi_share_add_risk_proxy_v1`
- 是否重要突破版本：`否`
- 决策：`stage052_contract_oi_share_proxy_partially_improves_not_goal`

## 本次版本变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_optimization/tools/stage052_contract_oi_share_add_risk_proxy.py`
- 新增测试：`tests/test_rebuilt_c9_stage052_contract_oi_proxy.py`
- 新增参数：`selector=contract_oi_share_ge50`、`ADD_RISK_FRACTION=0.25`。
- 修改参数：无，Stage013/Stage006/官方 C9 配置未改。
- 删除参数：无。
- 新增回测结果：closed-lot 只读 proxy 目标审计；不是真实组合引擎。
- 本阶段不连接 CTP，不调用订单 API，不触发 A/B。

## 调研和判断结论

- CME/CFTC/Databento 资料都把 open interest 视作市场参与度、持仓集中和换月/连续合约构造的重要信息。Stage052 因此只把 `contract_oi_share_ge50` 当流动性/换月质量条件做 fixed proxy，不把它直接视为 alpha。

# Stage052 - contract_oi_share_ge50 非挤占加风险 proxy

- 生成时间：`2026-07-01T20:33:12`
- 决策：`stage052_contract_oi_share_proxy_partially_improves_not_goal`
- 阶段性质：closed-lot 只读上界 proxy；不是真实组合引擎，不改 C9，不连接 CTP，不调用下单。
- selector：`contract_oi_share_ge50`
- 固定额外风险比例：`25.00%`

## 核心结果

- 选中 lots：`1728`；selected realized PnL `42,941,026.70`；proxy delta `10,735,256.68`。
- Stage052 严格任意 `>1` 年负窗口：`252134` / `7215647`；最差 `-40.3699%`。
- Stage013 严格任意 `>1` 年负窗口：`330947`。
- 到 `2026-06-30` 负窗口：`0`；最差 `24.7554%`。
- 80% 收益保留 vs Stage006：`17/17`；vs Stage013：`17/17`。
- 收益改善/不变/变差 vs Stage013：`17/0/0`。
- 回撤改善/不变/变差 vs Stage013：`14/0/3`。

## 多起点摘要

| requested_start_month   |   total_return_pct_stage013_engine |   total_return_pct_stage052_contract_oi_share_ge50_add_risk_proxy |   return_delta_pp_stage052_vs_stage013 |   max_dd_pct_stage013_engine |   max_dd_pct_stage052_contract_oi_share_ge50_add_risk_proxy |   maxdd_delta_pp_stage052_vs_stage013 |
|:------------------------|-----------------------------------:|------------------------------------------------------------------:|---------------------------------------:|-----------------------------:|------------------------------------------------------------:|--------------------------------------:|
| 2018-01                 |                          7678.8    |                                                         9145.6    |                              1466.8    |                     -37.3409 |                                                    -29.4379 |                                7.9029 |
| 2018-07                 |                          9880.13   |                                                        11357.3    |                              1477.2    |                     -37.9477 |                                                    -30.1233 |                                7.8245 |
| 2019-01                 |                          9240.88   |                                                        11042.7    |                              1801.81   |                     -38.4073 |                                                    -30.084  |                                8.3233 |
| 2019-07                 |                          5298.26   |                                                         6127.68   |                               829.425  |                     -37.5846 |                                                    -29.5671 |                                8.0175 |
| 2020-01                 |                          3931.07   |                                                         4556.05   |                               624.977  |                     -38.1717 |                                                    -30.0502 |                                8.1215 |
| 2020-07                 |                          3233.46   |                                                         3714.95   |                               481.491  |                     -37.3761 |                                                    -29.4993 |                                7.8768 |
| 2021-01                 |                          1451.64   |                                                         1693.6    |                               241.956  |                     -36.7684 |                                                    -29.4225 |                                7.3458 |
| 2021-07                 |                           265.542  |                                                          317.655  |                                52.1133 |                     -39.4246 |                                                    -35.0518 |                                4.3728 |
| 2022-01                 |                           122.752  |                                                          129.569  |                                 6.8167 |                     -34.2643 |                                                    -34.8344 |                               -0.5701 |
| 2022-07                 |                           238.369  |                                                          274.779  |                                36.4105 |                     -43.794  |                                                    -40.3699 |                                3.4241 |
| 2023-01                 |                           134.445  |                                                          165.429  |                                30.9833 |                     -24.469  |                                                    -28.8828 |                               -4.4138 |
| 2023-07                 |                           201.485  |                                                          244.695  |                                43.2097 |                     -20.2875 |                                                    -19.4392 |                                0.8483 |
| 2024-01                 |                           138.199  |                                                          168.488  |                                30.2889 |                     -18.6307 |                                                    -17.1061 |                                1.5246 |
| 2024-07                 |                            57.5587 |                                                           69.0634 |                                11.5047 |                     -20.3312 |                                                    -17.7832 |                                2.5481 |
| 2025-01                 |                            51.4687 |                                                           62.8475 |                                11.3788 |                     -19.6119 |                                                    -14.5932 |                                5.0188 |
| 2025-07                 |                            33.3787 |                                                           42.6137 |                                 9.235  |                     -19.1855 |                                                    -14.2237 |                                4.9618 |
| 2026-01                 |                             1.9011 |                                                            3.143  |                                 1.2419 |                     -14.7303 |                                                    -15.4661 |                               -0.7358 |

## 严格目标审计

| variant                                        | source_start_month   | audit_scope                 | objective_start_min   | objective_start_max   |   window_count |   positive_count |   negative_count |   negative_rate_pct |   min_return_pct |   mean_return_pct |   is_independent_daily_cold_start |
|:-----------------------------------------------|:---------------------|:----------------------------|:----------------------|:----------------------|---------------:|-----------------:|-----------------:|--------------------:|-----------------:|------------------:|----------------------------------:|
| stage052_contract_oi_share_ge50_add_risk_proxy | 2018-01              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |         882036 |           863461 |            18575 |              2.1059 |         -23.932  |          861.77   |                                 0 |
| stage052_contract_oi_share_ge50_add_risk_proxy | 2018-07              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |         882036 |           863293 |            18743 |              2.125  |         -24.7791 |          910.14   |                                 0 |
| stage052_contract_oi_share_ge50_add_risk_proxy | 2019-01              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |         882036 |           860861 |            21175 |              2.4007 |         -24.8251 |          926.107  |                                 0 |
| stage052_contract_oi_share_ge50_add_risk_proxy | 2019-07              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |         882036 |           863982 |            18054 |              2.0469 |         -23.5732 |          656.787  |                                 0 |
| stage052_contract_oi_share_ge50_add_risk_proxy | 2020-01              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |         882036 |           863649 |            18387 |              2.0846 |         -23.7905 |          709.875  |                                 0 |
| stage052_contract_oi_share_ge50_add_risk_proxy | 2020-07              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |         733565 |           714950 |            18615 |              2.5376 |         -23.616  |          416.577  |                                 0 |
| stage052_contract_oi_share_ge50_add_risk_proxy | 2021-01              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |         589005 |           564895 |            24110 |              4.0933 |         -24.4079 |          192.361  |                                 0 |
| stage052_contract_oi_share_ge50_add_risk_proxy | 2021-07              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |         467873 |           397074 |            70799 |             15.1321 |         -35.0518 |           63.1843 |                                 0 |
| stage052_contract_oi_share_ge50_add_risk_proxy | 2022-01              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |         354785 |           325977 |            28807 |              8.1196 |         -34.8314 |           88.5844 |                                 0 |
| stage052_contract_oi_share_ge50_add_risk_proxy | 2022-07              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |         263196 |           249445 |            13751 |              5.2246 |         -40.3699 |           96.7378 |                                 0 |
| stage052_contract_oi_share_ge50_add_risk_proxy | 2023-01              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |         180432 |           179314 |             1118 |              0.6196 |         -13.0615 |          119.421  |                                 0 |
| stage052_contract_oi_share_ge50_add_risk_proxy | 2023-07              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |         116529 |           116529 |                0 |              0      |          14.1065 |          125.518  |                                 0 |
| stage052_contract_oi_share_ge50_add_risk_proxy | 2024-01              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |          64285 |            64285 |                0 |              0      |           9.5723 |           90.8771 |                                 0 |
| stage052_contract_oi_share_ge50_add_risk_proxy | 2024-07              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |          29059 |            29059 |                0 |              0      |           6.7133 |           65.2655 |                                 0 |
| stage052_contract_oi_share_ge50_add_risk_proxy | 2025-01              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |           6738 |             6738 |                0 |              0      |          37.4928 |           72.099  |                                 0 |
| stage052_contract_oi_share_ge50_add_risk_proxy | 2025-07              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |              0 |                0 |                0 |                     |                  |                   |                                 0 |
| stage052_contract_oi_share_ge50_add_risk_proxy | 2026-01              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |              0 |                0 |                0 |                     |                  |                   |                                 0 |

## 收益保留

| requested_start_month   |   stage052_vs_base_stage006_return_ratio |   stage052_vs_stage013_return_ratio |   passes_80pct_retention_vs_base_stage006 |   passes_80pct_retention_vs_stage013 |
|:------------------------|-----------------------------------------:|------------------------------------:|------------------------------------------:|-------------------------------------:|
| 2018-01                 |                                   1.0796 |                              1.191  |                                         1 |                                    1 |
| 2018-07                 |                                   1.1549 |                              1.1495 |                                         1 |                                    1 |
| 2019-01                 |                                   1.2155 |                              1.195  |                                         1 |                                    1 |
| 2019-07                 |                                   1.1883 |                              1.1565 |                                         1 |                                    1 |
| 2020-01                 |                                   1.1724 |                              1.159  |                                         1 |                                    1 |
| 2020-07                 |                                   1.1803 |                              1.1489 |                                         1 |                                    1 |
| 2021-01                 |                                   1.1315 |                              1.1667 |                                         1 |                                    1 |
| 2021-07                 |                                   1.3161 |                              1.1963 |                                         1 |                                    1 |
| 2022-01                 |                                   1.1183 |                              1.0555 |                                         1 |                                    1 |
| 2022-07                 |                                   1.3493 |                              1.1527 |                                         1 |                                    1 |
| 2023-01                 |                                   1.3194 |                              1.2305 |                                         1 |                                    1 |
| 2023-07                 |                                   1.3636 |                              1.2145 |                                         1 |                                    1 |
| 2024-01                 |                                   1.3351 |                              1.2192 |                                         1 |                                    1 |
| 2024-07                 |                                   1.348  |                              1.1999 |                                         1 |                                    1 |
| 2025-01                 |                                   1.941  |                              1.2211 |                                         1 |                                    1 |
| 2025-07                 |                                   1.3255 |                              1.2767 |                                         1 |                                    1 |
| 2026-01                 |                                   1.6533 |                              1.6533 |                                         1 |                                    1 |

## 反思

- 运行前过拟合反思：否。Stage052 冻结 Stage051 第一稳定条件 `contract_oi_share_ge50` 和固定 25% 非挤占风险，不扫 OI 阈值。
- 运行后过拟合反思：否。本阶段仍是只读 proxy；若失败后改 `0.33/0.50/0.70`、品种、年份或方向就是过拟合。
- 运行前继续价值反思：有。Stage051 已清源缺口，必须验证 OI 集中度从候选级 PnL lift 落到组合目标路径后是否仍有价值。
- 运行后继续价值反思：有但未达标。OI 集中度可保留为候选，下一步做日级冷启动探针或真实引擎验真。
