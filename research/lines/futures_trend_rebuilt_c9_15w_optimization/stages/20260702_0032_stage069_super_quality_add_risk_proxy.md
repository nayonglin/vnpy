# Stage069 - Stage068 超高质量组合加风险 proxy

- 记录时间：`2026-07-02T00:32`
- line_id：`futures_trend_rebuilt_c9_15w_optimization`
- 当前模式：`day`
- model_tag：`stage069_super_quality_add_risk_proxy_v1`
- 是否重要突破版本：`否`
- 是否触发A/B：`是，A/C 研究 proxy`
- 决策：`stage069_super_quality_proxy_partially_improves_not_goal`

## 本次版本变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_optimization/tools/stage069_super_quality_add_risk_proxy.py`
- 新增测试：`tests/test_rebuilt_c9_stage069_super_quality_add_risk_proxy.py`
- 新增参数：`selector=full_market_ai_top8_and_account_injured`、`ADD_RISK_FRACTION=0.25`。
- 修改参数：无，Stage013/Stage006/官方 C9 配置未改。
- 删除参数：无。
- 新增回测结果：closed-lot 只读 proxy 目标审计；不是真实组合引擎。
- 本阶段不连接 CTP，不调用订单 API，不改实盘。

## 外部调研与判断

- 商品期货 ML/横截面趋势资料支持用可解释点时信号做排序，position sizing 资料支持按信号质量调风险；purged/embargo CV 资料提示必须用时间顺序 OOS 与多起点路径检验，不能凭单段高均值直接上线。

# Stage069 - Stage068 超高质量组合加风险 proxy

- 生成时间：`2026-07-02T00:32:53`
- 决策：`stage069_super_quality_proxy_partially_improves_not_goal`
- 阶段性质：closed-lot 只读上界 proxy；不是真实组合引擎，不改 C9，不连接 CTP，不调用下单。
- selector：`full_market_ai_top8_and_account_injured`
- 固定额外风险比例：`25.00%`

## A/C 预声明

- A：`stage013_engine`
- C：`stage013_engine + full_market_ai_top8_and_account_injured +25pct non-overwriting risk proxy`
- B：closed-lot proxy 下 standalone 没有可解释资金曲线，不单跑。

## 核心结果

- 选中 open trades：`161`；选中 lots：`161`；selected realized PnL `2,150,098.20`；proxy delta `537,524.55`。
- Stage069 严格任意 `>1` 年负窗口：`330030` / `7215647`；最差 `-44.1402%`。
- Stage013 严格任意 `>1` 年负窗口：`330947`。
- 到 `2026-06-30` 负窗口：`0`；最差 `26.5269%`。
- 80% 收益保留 vs Stage006：`17/17`；vs Stage013：`17/17`。
- 收益改善/不变/变差 vs Stage013：`16/0/1`。
- 回撤改善/不变/变差 vs Stage013：`8/0/9`。

## 多起点摘要

| requested_start_month   |   total_return_pct_stage013_engine |   total_return_pct_stage069_super_quality_add_risk_proxy |   return_delta_pp_stage069_vs_stage013 |   max_dd_pct_stage013_engine |   max_dd_pct_stage069_super_quality_add_risk_proxy |   maxdd_delta_pp_stage069_vs_stage013 |
|:------------------------|-----------------------------------:|---------------------------------------------------------:|---------------------------------------:|-----------------------------:|---------------------------------------------------:|--------------------------------------:|
| 2018-01                 |                          7678.8    |                                                7702.62   |                                23.8201 |                     -37.3409 |                                           -37.3411 |                               -0.0003 |
| 2018-07                 |                          9880.13   |                                                9853.67   |                               -26.4583 |                     -37.9477 |                                           -37.9479 |                               -0.0002 |
| 2019-01                 |                          9240.88   |                                                9267.54   |                                26.6584 |                     -38.4073 |                                           -38.4075 |                               -0.0002 |
| 2019-07                 |                          5298.26   |                                                5399.48   |                               101.223  |                     -37.5846 |                                           -37.585  |                               -0.0004 |
| 2020-01                 |                          3931.07   |                                                4008.21   |                                77.1313 |                     -38.1717 |                                           -38.1723 |                               -0.0006 |
| 2020-07                 |                          3233.46   |                                                3292.8    |                                59.3413 |                     -37.3761 |                                           -37.3767 |                               -0.0007 |
| 2021-01                 |                          1451.64   |                                                1475.19   |                                23.5496 |                     -36.7684 |                                           -36.7697 |                               -0.0013 |
| 2021-07                 |                           265.542  |                                                 273.908  |                                 8.3663 |                     -39.4246 |                                           -38.6486 |                                0.776  |
| 2022-01                 |                           122.752  |                                                 123.576  |                                 0.8242 |                     -34.2643 |                                           -34.1535 |                                0.1108 |
| 2022-07                 |                           238.369  |                                                 254.107  |                                15.7388 |                     -43.794  |                                           -44.1402 |                               -0.3462 |
| 2023-01                 |                           134.445  |                                                 150.169  |                                15.7238 |                     -24.469  |                                           -24.0856 |                                0.3834 |
| 2023-07                 |                           201.485  |                                                 216.002  |                                14.5163 |                     -20.2875 |                                           -20.2191 |                                0.0684 |
| 2024-01                 |                           138.199  |                                                 148.632  |                                10.433  |                     -18.6307 |                                           -17.7206 |                                0.9101 |
| 2024-07                 |                            57.5587 |                                                  58.7984 |                                 1.2396 |                     -20.3312 |                                           -20.3082 |                                0.023  |
| 2025-01                 |                            51.4687 |                                                  52.3967 |                                 0.9279 |                     -19.6119 |                                           -19.7751 |                               -0.1631 |
| 2025-07                 |                            33.3787 |                                                  35.1333 |                                 1.7546 |                     -19.1855 |                                           -18.7647 |                                0.4208 |
| 2026-01                 |                             1.9011 |                                                   5.4611 |                                 3.56   |                     -14.7303 |                                           -14.3019 |                                0.4284 |

## 严格目标审计

| variant                               | source_start_month   | audit_scope                 | objective_start_min   | objective_start_max   |   window_count |   positive_count |   negative_count |   negative_rate_pct |   min_return_pct |   mean_return_pct |   is_independent_daily_cold_start |
|:--------------------------------------|:---------------------|:----------------------------|:----------------------|:----------------------|---------------:|-----------------:|-----------------:|--------------------:|-----------------:|------------------:|----------------------------------:|
| stage069_super_quality_add_risk_proxy | 2018-01              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |         882036 |           853375 |            28661 |              3.2494 |         -31.9918 |          749.472  |                                 0 |
| stage069_super_quality_add_risk_proxy | 2018-07              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |         882036 |           853378 |            28658 |              3.2491 |         -32.8697 |          803.871  |                                 0 |
| stage069_super_quality_add_risk_proxy | 2019-01              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |         882036 |           850174 |            31862 |              3.6123 |         -33.354  |          808.526  |                                 0 |
| stage069_super_quality_add_risk_proxy | 2019-07              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |         882036 |           853902 |            28134 |              3.1897 |         -31.8632 |          576.1    |                                 0 |
| stage069_super_quality_add_risk_proxy | 2020-01              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |         882036 |           853339 |            28697 |              3.2535 |         -32.1376 |          622.874  |                                 0 |
| stage069_super_quality_add_risk_proxy | 2020-07              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |         733565 |           704673 |            28892 |              3.9386 |         -31.8094 |          384.637  |                                 0 |
| stage069_super_quality_add_risk_proxy | 2021-01              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |         589005 |           551928 |            37077 |              6.2949 |         -32.1489 |          182.13   |                                 0 |
| stage069_super_quality_add_risk_proxy | 2021-07              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |         467873 |           393350 |            74523 |             15.928  |         -38.6486 |           62.0658 |                                 0 |
| stage069_super_quality_add_risk_proxy | 2022-01              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |         354785 |           325889 |            28896 |              8.1447 |         -33.989  |           82.7858 |                                 0 |
| stage069_super_quality_add_risk_proxy | 2022-07              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |         263196 |           249404 |            13792 |              5.2402 |         -44.1402 |           98.6168 |                                 0 |
| stage069_super_quality_add_risk_proxy | 2023-01              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |         180432 |           179594 |              838 |              0.4644 |          -8.3072 |          101.185  |                                 0 |
| stage069_super_quality_add_risk_proxy | 2023-07              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |         116529 |           116529 |                0 |              0      |           6.6072 |          108.573  |                                 0 |
| stage069_super_quality_add_risk_proxy | 2024-01              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |          64285 |            64285 |                0 |              0      |           1.8559 |           83.1911 |                                 0 |
| stage069_super_quality_add_risk_proxy | 2024-07              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |          29059 |            29059 |                0 |              0      |           6.0467 |           55.126  |                                 0 |
| stage069_super_quality_add_risk_proxy | 2025-01              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |           6738 |             6738 |                0 |              0      |          27.4809 |           59.1912 |                                 0 |
| stage069_super_quality_add_risk_proxy | 2025-07              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |              0 |                0 |                0 |                     |                  |                   |                                 0 |
| stage069_super_quality_add_risk_proxy | 2026-01              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |              0 |                0 |                0 |                     |                  |                   |                                 0 |

## 收益保留

| requested_start_month   |   stage069_vs_base_stage006_return_ratio |   stage069_vs_stage013_return_ratio |   passes_80pct_retention_vs_base_stage006 |   passes_80pct_retention_vs_stage013 |
|:------------------------|-----------------------------------------:|------------------------------------:|------------------------------------------:|-------------------------------------:|
| 2018-01                 |                                   0.9092 |                              1.0031 |                                         1 |                                    1 |
| 2018-07                 |                                   1.002  |                              0.9973 |                                         1 |                                    1 |
| 2019-01                 |                                   1.0201 |                              1.0029 |                                         1 |                                    1 |
| 2019-07                 |                                   1.0471 |                              1.0191 |                                         1 |                                    1 |
| 2020-01                 |                                   1.0314 |                              1.0196 |                                         1 |                                    1 |
| 2020-07                 |                                   1.0461 |                              1.0184 |                                         1 |                                    1 |
| 2021-01                 |                                   0.9855 |                              1.0162 |                                         1 |                                    1 |
| 2021-07                 |                                   1.1348 |                              1.0315 |                                         1 |                                    1 |
| 2022-01                 |                                   1.0665 |                              1.0067 |                                         1 |                                    1 |
| 2022-07                 |                                   1.2478 |                              1.066  |                                         1 |                                    1 |
| 2023-01                 |                                   1.1977 |                              1.117  |                                         1 |                                    1 |
| 2023-07                 |                                   1.2037 |                              1.072  |                                         1 |                                    1 |
| 2024-01                 |                                   1.1778 |                              1.0755 |                                         1 |                                    1 |
| 2024-07                 |                                   1.1476 |                              1.0215 |                                         1 |                                    1 |
| 2025-01                 |                                   1.6183 |                              1.018  |                                         1 |                                    1 |
| 2025-07                 |                                   1.0929 |                              1.0526 |                                         1 |                                    1 |
| 2026-01                 |                                   2.8726 |                              2.8726 |                                         1 |                                    1 |

## 反思

- 运行前过拟合反思：否。Stage069 冻结 Stage068 最强 new composite 与固定 25% 非挤占风险，不扫 TopN、账户阈值、品种、方向或年份。
- 运行后过拟合反思：否。本阶段只验证一个冻结候选；若失败后改 account 阈值、TopN、风险比例或按产品方向救参就是过拟合。
- 运行前继续价值反思：有。目标明确要求 AI 识别超高质量信号并加大风险投入，Stage068 已给出低自由度候选，必须先做组合路径 proxy。
- 运行后继续价值反思：有但未达标。候选可进入更窄的日级压力探针或真实引擎，但不能加参救援。
