# Stage013 Guarded Quality Add-risk Proxy

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-02T04:44:27
- 阶段性质：closed-lot 非挤占加风险 proxy；不改官方 live config、不连接 CTP、不调用下单
- 是否重要突破：否
- 是否触发A/B：否；本阶段只是 v2 研究线 proxy，若结果显著再进入真实引擎 A/B

## 外部调研与判断

- 参考资料：Lopez de Prado / Hudson & Thames meta-labeling、trend-following right-tail/risk sizing、pysystemtrade capital/risk overlay。
- 我的判断：二级质量层可以做加风险，但不能在策略自身已经提高 `risk_multiplier` 的状态里盲目重复加风险。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage013_guarded_quality_add_risk_proxy.py`
- 新增测试：`tests/test_rebuilt_c9_v2_stage013_guarded_quality_proxy.py`
- 新增参数：`SELECTOR=ai_rank_1_8_selected_volume_gt1_risk_multiplier_lt2`、`ADD_RISK_FRACTION=0.25`
- 修改参数：无
- 删除参数：Stage010 选中 lot 中 `risk_multiplier>=2` 不参与本阶段加风险 proxy

## 结果

- Stage010 selected lots：`1414`
- Stage013 guarded lots：`903`
- excluded risk_multiplier>=2：`511`
- guarded realized PnL：`59967127.80`
- guarded proxy delta：`14991781.95`
- 期末最差收益：`0.1327%`
- 最差最大回撤：`-40.5376%`
- 80% 收益保留：`16/17`
- 严格 >365 天负窗口：`232390/7215647`
- 严格最差窗口收益：`-40.5376%`
- 决策：`stage013_guarded_proxy_improves_stage010_left_tail_need_true_engine`
- 原因：guarded proxy 相比 Stage010 减少严格负窗口，同时保持 80% 收益保留；下一步应做真实引擎或更细路径校验。

## 多起点摘要

| stage    | model_tag                                  | line_id                                      | variant                                 | requested_start_month   | actual_start   | actual_end   |   trading_days |       end_equity |   total_return_pct |   max_dd_pct |   sharpe |
|:---------|:-------------------------------------------|:---------------------------------------------|:----------------------------------------|:------------------------|:---------------|:-------------|---------------:|-----------------:|-------------------:|-------------:|---------:|
| Stage013 | stage013_guarded_quality_add_risk_proxy_v1 | futures_trend_rebuilt_c9_15w_v2_optimization | stage013_engine                         | 2018-01                 | 2018-01-02     | 2026-06-30   |           2058 |      1.16682e+07 |          7678.8    |     -37.3409 |   1.4011 |
| Stage013 | stage013_guarded_quality_add_risk_proxy_v1 | futures_trend_rebuilt_c9_15w_v2_optimization | stage013_engine                         | 2018-07                 | 2018-07-02     | 2026-06-30   |           1939 |      1.49702e+07 |          9880.13   |     -37.9477 |   1.5074 |
| Stage013 | stage013_guarded_quality_add_risk_proxy_v1 | futures_trend_rebuilt_c9_15w_v2_optimization | stage013_engine                         | 2019-01                 | 2019-01-02     | 2026-06-30   |           1815 |      1.40113e+07 |          9240.88   |     -38.4073 |   1.558  |
| Stage013 | stage013_guarded_quality_add_risk_proxy_v1 | futures_trend_rebuilt_c9_15w_v2_optimization | stage013_engine                         | 2019-07                 | 2019-07-01     | 2026-06-30   |           1697 |      8.09739e+06 |          5298.26   |     -37.5846 |   1.4971 |
| Stage013 | stage013_guarded_quality_add_risk_proxy_v1 | futures_trend_rebuilt_c9_15w_v2_optimization | stage013_engine                         | 2020-01                 | 2020-01-02     | 2026-06-30   |           1571 |      6.04661e+06 |          3931.07   |     -38.1717 |   1.4619 |
| Stage013 | stage013_guarded_quality_add_risk_proxy_v1 | futures_trend_rebuilt_c9_15w_v2_optimization | stage013_engine                         | 2020-07                 | 2020-07-01     | 2026-06-30   |           1454 |      5.00019e+06 |          3233.46   |     -37.3761 |   1.4903 |
| Stage013 | stage013_guarded_quality_add_risk_proxy_v1 | futures_trend_rebuilt_c9_15w_v2_optimization | stage013_engine                         | 2021-01                 | 2021-01-04     | 2026-06-30   |           1328 |      2.32746e+06 |          1451.64   |     -36.7684 |   1.3406 |
| Stage013 | stage013_guarded_quality_add_risk_proxy_v1 | futures_trend_rebuilt_c9_15w_v2_optimization | stage013_engine                         | 2021-07                 | 2021-07-01     | 2026-06-30   |           1210 | 548313           |           265.542  |     -39.4246 |   0.9421 |
| Stage013 | stage013_guarded_quality_add_risk_proxy_v1 | futures_trend_rebuilt_c9_15w_v2_optimization | stage013_engine                         | 2022-01                 | 2022-01-04     | 2026-06-30   |           1085 | 334128           |           122.752  |     -34.2643 |   0.7248 |
| Stage013 | stage013_guarded_quality_add_risk_proxy_v1 | futures_trend_rebuilt_c9_15w_v2_optimization | stage013_engine                         | 2022-07                 | 2022-07-01     | 2026-06-30   |            968 | 507553           |           238.369  |     -43.794  |   1.049  |
| Stage013 | stage013_guarded_quality_add_risk_proxy_v1 | futures_trend_rebuilt_c9_15w_v2_optimization | stage013_engine                         | 2023-01                 | 2023-01-03     | 2026-06-30   |            843 | 351668           |           134.445  |     -24.469  |   0.9422 |
| Stage013 | stage013_guarded_quality_add_risk_proxy_v1 | futures_trend_rebuilt_c9_15w_v2_optimization | stage013_engine                         | 2023-07                 | 2023-07-03     | 2026-06-30   |            725 | 452228           |           201.485  |     -20.2875 |   1.2757 |
| Stage013 | stage013_guarded_quality_add_risk_proxy_v1 | futures_trend_rebuilt_c9_15w_v2_optimization | stage013_engine                         | 2024-01                 | 2024-01-02     | 2026-06-30   |            601 | 357298           |           138.199  |     -18.6307 |   1.2722 |
| Stage013 | stage013_guarded_quality_add_risk_proxy_v1 | futures_trend_rebuilt_c9_15w_v2_optimization | stage013_engine                         | 2024-07                 | 2024-07-01     | 2026-06-30   |            484 | 236338           |            57.5587 |     -20.3312 |   0.861  |
| Stage013 | stage013_guarded_quality_add_risk_proxy_v1 | futures_trend_rebuilt_c9_15w_v2_optimization | stage013_engine                         | 2025-01                 | 2025-01-02     | 2026-06-30   |            359 | 227203           |            51.4687 |     -19.6119 |   0.9879 |
| Stage013 | stage013_guarded_quality_add_risk_proxy_v1 | futures_trend_rebuilt_c9_15w_v2_optimization | stage013_engine                         | 2025-07                 | 2025-07-01     | 2026-06-30   |            242 | 200068           |            33.3787 |     -19.1855 |   1.1407 |
| Stage013 | stage013_guarded_quality_add_risk_proxy_v1 | futures_trend_rebuilt_c9_15w_v2_optimization | stage013_engine                         | 2026-01                 | 2026-01-05     | 2026-06-30   |            116 | 152852           |             1.9011 |     -14.7303 |   0.286  |
| Stage013 | stage013_guarded_quality_add_risk_proxy_v1 | futures_trend_rebuilt_c9_15w_v2_optimization | stage013_guarded_quality_add_risk_proxy | 2018-01                 | 2018-01-02     | 2026-06-30   |           2058 |      1.43597e+07 |          9473.14   |     -35.2232 |   1.502  |
| Stage013 | stage013_guarded_quality_add_risk_proxy_v1 | futures_trend_rebuilt_c9_15w_v2_optimization | stage013_guarded_quality_add_risk_proxy | 2018-07                 | 2018-07-02     | 2026-06-30   |           1939 |      1.8567e+07  |         12278      |     -32.9757 |   1.6172 |
| Stage013 | stage013_guarded_quality_add_risk_proxy_v1 | futures_trend_rebuilt_c9_15w_v2_optimization | stage013_guarded_quality_add_risk_proxy | 2019-01                 | 2019-01-02     | 2026-06-30   |           1815 |      1.73714e+07 |         11480.9    |     -38.1041 |   1.6748 |
| Stage013 | stage013_guarded_quality_add_risk_proxy_v1 | futures_trend_rebuilt_c9_15w_v2_optimization | stage013_guarded_quality_add_risk_proxy | 2019-07                 | 2019-07-01     | 2026-06-30   |           1697 |      9.94132e+06 |          6527.54   |     -37.0287 |   1.6223 |
| Stage013 | stage013_guarded_quality_add_risk_proxy_v1 | futures_trend_rebuilt_c9_15w_v2_optimization | stage013_guarded_quality_add_risk_proxy | 2020-01                 | 2020-01-02     | 2026-06-30   |           1571 |      7.42138e+06 |          4847.58   |     -36.3733 |   1.5883 |
| Stage013 | stage013_guarded_quality_add_risk_proxy_v1 | futures_trend_rebuilt_c9_15w_v2_optimization | stage013_guarded_quality_add_risk_proxy | 2020-07                 | 2020-07-01     | 2026-06-30   |           1454 |      6.14132e+06 |          3994.21   |     -36.0742 |   1.6201 |
| Stage013 | stage013_guarded_quality_add_risk_proxy_v1 | futures_trend_rebuilt_c9_15w_v2_optimization | stage013_guarded_quality_add_risk_proxy | 2021-01                 | 2021-01-04     | 2026-06-30   |           1328 |      2.84942e+06 |          1799.61   |     -35.016  |   1.4835 |
| Stage013 | stage013_guarded_quality_add_risk_proxy_v1 | futures_trend_rebuilt_c9_15w_v2_optimization | stage013_guarded_quality_add_risk_proxy | 2021-07                 | 2021-07-01     | 2026-06-30   |           1210 | 656357           |           337.571  |     -35.9286 |   1.0864 |
| Stage013 | stage013_guarded_quality_add_risk_proxy_v1 | futures_trend_rebuilt_c9_15w_v2_optimization | stage013_guarded_quality_add_risk_proxy | 2022-01                 | 2022-01-04     | 2026-06-30   |           1085 | 378332           |           152.221  |     -33.957  |   0.82   |
| Stage013 | stage013_guarded_quality_add_risk_proxy_v1 | futures_trend_rebuilt_c9_15w_v2_optimization | stage013_guarded_quality_add_risk_proxy | 2022-07                 | 2022-07-01     | 2026-06-30   |            968 | 596592           |           297.728  |     -40.5376 |   1.2022 |
| Stage013 | stage013_guarded_quality_add_risk_proxy_v1 | futures_trend_rebuilt_c9_15w_v2_optimization | stage013_guarded_quality_add_risk_proxy | 2023-01                 | 2023-01-03     | 2026-06-30   |            843 | 397892           |           165.261  |     -25.982  |   1.0658 |
| Stage013 | stage013_guarded_quality_add_risk_proxy_v1 | futures_trend_rebuilt_c9_15w_v2_optimization | stage013_guarded_quality_add_risk_proxy | 2023-07                 | 2023-07-03     | 2026-06-30   |            725 | 524858           |           249.905  |     -18.9214 |   1.4704 |
| Stage013 | stage013_guarded_quality_add_risk_proxy_v1 | futures_trend_rebuilt_c9_15w_v2_optimization | stage013_guarded_quality_add_risk_proxy | 2024-01                 | 2024-01-02     | 2026-06-30   |            601 | 403608           |           169.072  |     -16.7655 |   1.4561 |
| Stage013 | stage013_guarded_quality_add_risk_proxy_v1 | futures_trend_rebuilt_c9_15w_v2_optimization | stage013_guarded_quality_add_risk_proxy | 2024-07                 | 2024-07-01     | 2026-06-30   |            484 | 258463           |            72.3087 |     -16.9919 |   0.9925 |
| Stage013 | stage013_guarded_quality_add_risk_proxy_v1 | futures_trend_rebuilt_c9_15w_v2_optimization | stage013_guarded_quality_add_risk_proxy | 2025-01                 | 2025-01-02     | 2026-06-30   |            359 | 249299           |            66.1996 |     -14.5019 |   1.1696 |
| Stage013 | stage013_guarded_quality_add_risk_proxy_v1 | futures_trend_rebuilt_c9_15w_v2_optimization | stage013_guarded_quality_add_risk_proxy | 2025-07                 | 2025-07-01     | 2026-06-30   |            242 | 213666           |            42.4437 |     -13.9039 |   1.3506 |
| Stage013 | stage013_guarded_quality_add_risk_proxy_v1 | futures_trend_rebuilt_c9_15w_v2_optimization | stage013_guarded_quality_add_risk_proxy | 2026-01                 | 2026-01-05     | 2026-06-30   |            116 | 150199           |             0.1327 |     -15.9341 |   0.1543 |

## 严格窗口摘要

| variant         | source_start_month   | audit_scope                 | objective_start_min   | objective_start_max   |   window_count |   positive_count |   negative_count |   negative_rate_pct |   min_return_pct |   mean_return_pct |   is_independent_daily_cold_start |
|:----------------|:---------------------|:----------------------------|:----------------------|:----------------------|---------------:|-----------------:|-----------------:|--------------------:|-----------------:|------------------:|----------------------------------:|
| stage013_engine | 2018-01              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |         882036 |           853584 |            28452 |              3.2257 |         -31.48   |          747.578  |                                 0 |
| stage013_engine | 2018-01              | start_to_2026_06_30_only    | 2020-01-01            | 2025-06-30            |           1328 |             1328 |                0 |              0      |          28.2836 |          867.706  |                                 0 |
| stage013_engine | 2018-07              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |         882036 |           853463 |            28573 |              3.2394 |         -32.324  |          804.383  |                                 0 |
| stage013_engine | 2018-07              | start_to_2026_06_30_only    | 2020-01-01            | 2025-06-30            |           1328 |             1328 |                0 |              0      |          31.0942 |          915.013  |                                 0 |
| stage013_engine | 2019-01              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |         882036 |           850255 |            31781 |              3.6031 |         -32.8083 |          806.629  |                                 0 |
| stage013_engine | 2019-01              | start_to_2026_06_30_only    | 2020-01-01            | 2025-06-30            |           1328 |             1328 |                0 |              0      |          29.8124 |          969.799  |                                 0 |
| stage013_engine | 2019-07              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |         882036 |           853807 |            28229 |              3.2004 |         -31.3609 |          572.612  |                                 0 |
| stage013_engine | 2019-07              | start_to_2026_06_30_only    | 2020-01-01            | 2025-06-30            |           1328 |             1328 |                0 |              0      |          37.0667 |          732.152  |                                 0 |
| stage013_engine | 2020-01              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |         882036 |           853069 |            28967 |              3.2841 |         -31.6661 |          618.992  |                                 0 |
| stage013_engine | 2020-01              | start_to_2026_06_30_only    | 2020-01-01            | 2025-06-30            |           1328 |             1328 |                0 |              0      |          37.5263 |          782.899  |                                 0 |
| stage013_engine | 2020-07              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |         733565 |           704237 |            29328 |              3.998  |         -31.3553 |          382.049  |                                 0 |
| stage013_engine | 2020-07              | start_to_2026_06_30_only    | 2020-01-01            | 2025-06-30            |           1211 |             1211 |                0 |              0      |          34.2498 |          469.496  |                                 0 |
| stage013_engine | 2021-01              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |         589005 |           552509 |            36496 |              6.1962 |         -31.8738 |          181.192  |                                 0 |
| stage013_engine | 2021-01              | start_to_2026_06_30_only    | 2020-01-01            | 2025-06-30            |           1085 |             1085 |                0 |              0      |          33.1886 |          240.825  |                                 0 |
| stage013_engine | 2021-07              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |         467873 |           392501 |            75371 |             16.1093 |         -39.4246 |           60.8589 |                                 0 |
| stage013_engine | 2021-07              | start_to_2026_06_30_only    | 2020-01-01            | 2025-06-30            |            967 |              967 |                0 |              0      |          28.9906 |          111.01   |                                 0 |
| stage013_engine | 2022-01              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |         354785 |           325689 |            29096 |              8.201  |         -34.0999 |           82.1578 |                                 0 |
| stage013_engine | 2022-01              | start_to_2026_06_30_only    | 2020-01-01            | 2025-06-30            |            842 |              842 |                0 |              0      |          26.8038 |          127.037  |                                 0 |
| stage013_engine | 2022-07              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |         263196 |           249418 |            13778 |              5.2349 |         -43.794  |           92.1383 |                                 0 |
| stage013_engine | 2022-07              | start_to_2026_06_30_only    | 2020-01-01            | 2025-06-30            |            725 |              725 |                0 |              0      |          30.6964 |          131.038  |                                 0 |

## 过拟合反思

- 运行前判断：中等偏低。risk_multiplier<2 来自 Stage012 预声明 guard 家族和既有风险状态；但它是从 Stage011 失败归因里挑出的 near-miss，必须只当 proxy。
- 运行后判断：否，但仍需谨慎。该 proxy 用既有 risk_multiplier 状态过滤，未按产品/日期救参；下一步必须真实引擎验证。

## 继续价值反思

- 运行前判断：有价值。它保留 Stage010 约 99.3% 选中 PnL，同时修复 focus proxy 拖累，值得用完整路径 proxy 验证。
- 运行后判断：有价值。若真实引擎也保留改善，可进入正式 A/B；否则回退。

## 输出文件

- lot_deltas: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage013_guarded_quality_add_risk_proxy/rebuilt_c9_v2_stage013_guarded_quality_add_risk_proxy_lot_deltas_stage013_guarded_quality_add_risk_proxy_v1.csv.gz`
- curves: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage013_guarded_quality_add_risk_proxy/rebuilt_c9_v2_stage013_guarded_quality_add_risk_proxy_curves_stage013_guarded_quality_add_risk_proxy_v1.csv`
- summary: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage013_guarded_quality_add_risk_proxy/rebuilt_c9_v2_stage013_guarded_quality_add_risk_proxy_summary_stage013_guarded_quality_add_risk_proxy_v1.csv`
- ab_summary: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage013_guarded_quality_add_risk_proxy/rebuilt_c9_v2_stage013_guarded_quality_add_risk_proxy_ab_summary_stage013_guarded_quality_add_risk_proxy_v1.csv`
- goal_aggregate: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage013_guarded_quality_add_risk_proxy/rebuilt_c9_v2_stage013_guarded_quality_add_risk_proxy_goal_aggregate_stage013_guarded_quality_add_risk_proxy_v1.csv`
- goal_to_final: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage013_guarded_quality_add_risk_proxy/rebuilt_c9_v2_stage013_guarded_quality_add_risk_proxy_goal_to_final_windows_stage013_guarded_quality_add_risk_proxy_v1.csv`
- goal_fixed_horizon: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage013_guarded_quality_add_risk_proxy/rebuilt_c9_v2_stage013_guarded_quality_add_risk_proxy_goal_fixed_horizon_windows_stage013_guarded_quality_add_risk_proxy_v1.csv`
- goal_worst_windows: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage013_guarded_quality_add_risk_proxy/rebuilt_c9_v2_stage013_guarded_quality_add_risk_proxy_goal_worst_windows_stage013_guarded_quality_add_risk_proxy_v1.csv`
- retention: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage013_guarded_quality_add_risk_proxy/rebuilt_c9_v2_stage013_guarded_quality_add_risk_proxy_retention_vs_stage013_stage013_guarded_quality_add_risk_proxy_v1.csv`
- chart: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage013_guarded_quality_add_risk_proxy/rebuilt_c9_v2_stage013_guarded_quality_add_risk_proxy_absolute_equity_chart_stage013_guarded_quality_add_risk_proxy_v1.png`
- decision: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage013_guarded_quality_add_risk_proxy/rebuilt_c9_v2_stage013_guarded_quality_add_risk_proxy_decision_stage013_guarded_quality_add_risk_proxy_v1.json`
- report: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage013_guarded_quality_add_risk_proxy/rebuilt_c9_v2_stage013_guarded_quality_add_risk_proxy_report_stage013_guarded_quality_add_risk_proxy_v1.md`
