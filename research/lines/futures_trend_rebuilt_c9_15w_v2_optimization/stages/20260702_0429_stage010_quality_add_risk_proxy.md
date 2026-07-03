# Stage010 Stage009 质量候选非挤占加风险 proxy

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-02T04:24:57
- 阶段性质：closed-lot 只读 proxy；不改官方 live config、不连接 CTP、不调用下单
- 是否重要突破：否
- 是否触发A/B：是，A=Stage013，C=Stage013 + `ai_rank_1_8_and_selected_volume_gt1` 固定 `+25%` 非挤占 proxy

## 外部调研与判断

- 参考资料：Meta-labeling / bet sizing、trend-following right-tail/risk sizing、pysystemtrade capital/risk overlay。
- 我的判断：Stage009 候选只有先通过多起点路径 proxy，才值得进入真实组合引擎；逐笔均值 lift 不足以证明能上线。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage010_quality_add_risk_proxy.py`
- 新增测试：`tests/test_rebuilt_c9_v2_stage010_quality_add_risk_proxy.py`
- 新增参数：`SELECTOR_NAME=ai_rank_1_8_and_selected_volume_gt1`、`ADD_RISK_FRACTION=0.25`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 输入：Stage009 quality events + Stage013 多起点资金曲线。
- C：对满足 `AI rank 1-8 + selected_volume>1` 的 closed lots，在退出日加入 `realized_pnl * 25%` 的非挤占 proxy delta。
- 注意：本阶段不是真实引擎，不产生真实新增订单、滑点、保证金或整数手路径，只作为进入真实引擎前的上界筛选。

## 结果

- 选中 lots：`1414`
- selected realized PnL：`60,391,409.40`
- proxy delta：`15,097,852.35`
- 期末收益最小/中位：`3.3513%` / `286.7196%`
- 最大回撤最差/中位：`-41.2213%` / `-29.6337%`
- 严格任意 `>1` 年负窗口：`269509/7215647`，最差 `-41.2213%`
- 到 `2026-06-30` 负窗口：`0`，最差 `32.4490%`
- 80% 收益保留 vs Stage013：`17/17`
- 收益改善/不变/变差 vs Stage013：`17/0/0`
- 回撤改善/不变/变差 vs Stage013：`12/0/5`
- 决策：`stage010_proxy_improves_left_tail_need_failure_attribution`

## 多起点摘要

| requested_start_month   |   total_return_pct_stage013_engine |   total_return_pct_stage010_quality_add_risk_proxy |   return_delta_pp_stage010_vs_stage013 |   max_dd_pct_stage013_engine |   max_dd_pct_stage010_quality_add_risk_proxy |
|:------------------------|-----------------------------------:|---------------------------------------------------:|---------------------------------------:|-----------------------------:|---------------------------------------------:|
| 2018-01                 |                          7678.8    |                                          9498.96   |                              1820.16   |                     -37.3409 |                                     -29.6681 |
| 2018-07                 |                          9880.13   |                                         12249.3    |                              2369.14   |                     -37.9477 |                                     -30.3527 |
| 2019-01                 |                          9240.88   |                                         11511.4    |                              2270.52   |                     -38.4073 |                                     -30.4558 |
| 2019-07                 |                          5298.26   |                                          6550.91   |                              1252.65   |                     -37.5846 |                                     -29.8326 |
| 2020-01                 |                          3931.07   |                                          4869.41   |                               938.338  |                     -38.1717 |                                     -30.2967 |
| 2020-07                 |                          3233.46   |                                          4017.59   |                               784.126  |                     -37.3761 |                                     -29.6337 |
| 2021-01                 |                          1451.64   |                                          1814.26   |                               362.623  |                     -36.7684 |                                     -29.1836 |
| 2021-07                 |                           265.542  |                                           338.684  |                                73.1417 |                     -39.4246 |                                     -35.3322 |
| 2022-01                 |                           122.752  |                                           143.407  |                                20.655  |                     -34.2643 |                                     -35.6359 |
| 2022-07                 |                           238.369  |                                           286.72   |                                48.3508 |                     -43.794  |                                     -41.2213 |
| 2023-01                 |                           134.445  |                                           158.18   |                                23.735  |                     -24.469  |                                     -28.5117 |
| 2023-07                 |                           201.485  |                                           242.23   |                                40.745  |                     -20.2875 |                                     -21.5683 |
| 2024-01                 |                           138.199  |                                           165.316  |                                27.1175 |                     -18.6307 |                                     -19.1908 |
| 2024-07                 |                            57.5587 |                                            68.6854 |                                11.1267 |                     -20.3312 |                                     -19.7404 |
| 2025-01                 |                            51.4687 |                                            64.8746 |                                13.4058 |                     -19.6119 |                                     -14.6259 |
| 2025-07                 |                            33.3787 |                                            41.3287 |                                 7.95   |                     -19.1855 |                                     -14.6099 |
| 2026-01                 |                             1.9011 |                                             3.3513 |                                 1.4503 |                     -14.7303 |                                     -15.4396 |

## 严格目标摘要

| variant                         | source_start_month   | audit_scope                 | objective_start_min   | objective_start_max   |   window_count |   positive_count |   negative_count |   negative_rate_pct |   min_return_pct |   mean_return_pct |   is_independent_daily_cold_start |
|:--------------------------------|:---------------------|:----------------------------|:----------------------|:----------------------|---------------:|-----------------:|-----------------:|--------------------:|-----------------:|------------------:|----------------------------------:|
| stage010_quality_add_risk_proxy | 2018-01              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |         882036 |           862163 |            19873 |              2.2531 |         -25.0272 |          907.432  |                                 0 |
| stage010_quality_add_risk_proxy | 2018-07              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |         882036 |           861587 |            20449 |              2.3184 |         -25.9172 |          971.333  |                                 0 |
| stage010_quality_add_risk_proxy | 2019-01              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |         882036 |           859556 |            22480 |              2.5486 |         -26.1269 |          981.529  |                                 0 |
| stage010_quality_add_risk_proxy | 2019-07              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |         882036 |           862505 |            19531 |              2.2143 |         -24.7769 |          693.13   |                                 0 |
| stage010_quality_add_risk_proxy | 2020-01              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |         882036 |           862084 |            19952 |              2.262  |         -25.0111 |          748.642  |                                 0 |
| stage010_quality_add_risk_proxy | 2020-07              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |         733565 |           713517 |            20048 |              2.733  |         -24.7795 |          450.333  |                                 0 |
| stage010_quality_add_risk_proxy | 2021-01              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |         589005 |           562802 |            26203 |              4.4487 |         -25.189  |          208.628  |                                 0 |
| stage010_quality_add_risk_proxy | 2021-07              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |         467873 |           395623 |            72250 |             15.4422 |         -35.3322 |           68.1076 |                                 0 |
| stage010_quality_add_risk_proxy | 2022-01              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |         354785 |           322052 |            32733 |              9.2262 |         -35.4655 |           97.66   |                                 0 |
| stage010_quality_add_risk_proxy | 2022-07              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |         263196 |           248341 |            14855 |              5.6441 |         -41.2213 |          104.456  |                                 0 |
| stage010_quality_add_risk_proxy | 2023-01              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |         180432 |           179297 |             1135 |              0.629  |         -12.6179 |          110.564  |                                 0 |
| stage010_quality_add_risk_proxy | 2023-07              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |         116529 |           116529 |                0 |              0      |           9.4291 |          120.968  |                                 0 |
| stage010_quality_add_risk_proxy | 2024-01              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |          64285 |            64285 |                0 |              0      |           3.4888 |           88.267  |                                 0 |
| stage010_quality_add_risk_proxy | 2024-07              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |          29059 |            29059 |                0 |              0      |           1.8033 |           66.144  |                                 0 |
| stage010_quality_add_risk_proxy | 2025-01              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |           6738 |             6738 |                0 |              0      |          39.5169 |           73.6315 |                                 0 |
| stage010_quality_add_risk_proxy | 2025-07              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |              0 |                0 |                0 |                     |                  |                   |                                 0 |
| stage010_quality_add_risk_proxy | 2026-01              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |              0 |                0 |                0 |                     |                  |                   |                                 0 |

## 过拟合反思

- 运行前判断：有风险但可控。候选来自 Stage009 closed-lot 元标签；本阶段只冻结一个条件和固定 25% 非挤占比例，不扫 rank/topN/产品/日期。
- 运行后判断：有风险但可控。本阶段仍是 proxy，不可直接上线；若下一步进真实引擎，必须继续冻结条件和比例。
- 原因：本阶段冻结一个候选和一个比例；若失败后调 rank/topN/比例或产品方向，就是过拟合。

## 继续价值反思

- 运行前判断：有价值。它直接检验 Stage009 质量候选是否能转成多起点资金曲线改善，而不是只看逐笔均值。
- 运行后判断：有但未达标。候选能改善左尾数量并保留收益，下一步归因剩余负窗口或进更严格 proxy。

## 输出文件

- lot_deltas: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage010_quality_add_risk_proxy/rebuilt_c9_v2_stage010_quality_add_risk_proxy_lot_deltas_stage010_quality_add_risk_proxy_v1.csv.gz`
- curves: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage010_quality_add_risk_proxy/rebuilt_c9_v2_stage010_quality_add_risk_proxy_curves_stage010_quality_add_risk_proxy_v1.csv`
- summary: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage010_quality_add_risk_proxy/rebuilt_c9_v2_stage010_quality_add_risk_proxy_summary_stage010_quality_add_risk_proxy_v1.csv`
- ab_summary: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage010_quality_add_risk_proxy/rebuilt_c9_v2_stage010_quality_add_risk_proxy_ab_summary_stage010_quality_add_risk_proxy_v1.csv`
- goal_aggregate: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage010_quality_add_risk_proxy/rebuilt_c9_v2_stage010_quality_add_risk_proxy_goal_aggregate_stage010_quality_add_risk_proxy_v1.csv`
- retention: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage010_quality_add_risk_proxy/rebuilt_c9_v2_stage010_quality_add_risk_proxy_retention_vs_stage013_stage010_quality_add_risk_proxy_v1.csv`
- chart: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage010_quality_add_risk_proxy/rebuilt_c9_v2_stage010_quality_add_risk_proxy_absolute_equity_chart_stage010_quality_add_risk_proxy_v1.png`
- decision: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage010_quality_add_risk_proxy/rebuilt_c9_v2_stage010_quality_add_risk_proxy_decision_stage010_quality_add_risk_proxy_v1.json`
- report: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage010_quality_add_risk_proxy/rebuilt_c9_v2_stage010_quality_add_risk_proxy_report_stage010_quality_add_risk_proxy_v1.md`
