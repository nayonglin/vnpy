# Stage021 xsmom 非挤占资金袖 proxy

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-02T06:06:14
- 阶段性质：curve-level 只读 proxy；不改官方 live config、不连接 CTP、不调用下单
- 是否重要突破：否
- 是否触发A/B：否。若 proxy 达标，也必须先做真实组合/保证金/整数手审计。

## 外部调研与判断

- 参考：Rob Carver/pysystemtrade 横截面动量、AQR/managed futures 时间序列动量与趋势跟随研究。
- 我的判断：低相关趋势袖有理论和实践依据，但必须先作为独立资金袖验证路径收益；不能为了修某段窗口去调 lookback、品种或方向。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage021_xsmom_non_crowding_overlay_proxy.py`
- 新增测试：`tests/test_rebuilt_c9_v2_stage021_xsmom_overlay_proxy.py`
- 新增参数：`OVERLAY_WEIGHTS=[0.025, 0.05, 0.075, 0.1, 0.2, 0.3]`、`SPECS=['mom_12m_skip1m', 'mom_6m_skip1m']`、`DEFAULT_COST_BPS=10.0`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 基础曲线：Stage167 当前重建 C9/15w 多起点曲线。
- xsmom 输入：Stage020 `satellite_daily`，19 品种，含 `jd.DCE`。
- 叠加公式：`account_equity = c9_equity + 150000 * weight * (xsmom_nav - 1)`。
- 审计：所有 `2020-01-01` 到 `2025-06-30` 曲线内交易日起点，所有 `>365` 天终点；到 `2026-06-30` 终点；固定 horizon；80% 收益保留 vs C9。

## 结果

- 基准 C9 严格 `>1` 年负窗口：`267708`，最差 `-54.6931%`
- 最优 overlay：`c9_plus_xsmom_mom_12m_skip1m_w2p5_cost10bps`
- 最优 overlay 严格 `>1` 年负窗口：`267868`，最差 `-54.8603%`
- 最优 overlay 最小收益保留：`1.0005`
- 最优 overlay 多起点中位收益：`181.0534%`
- 最优 overlay 最差最大回撤：`-55.3739%`
- 目标通过 variant 数：`0`
- 决策：`stage021_xsmom_overlay_not_promoted_keep_readonly`

## 目标门汇总

| variant                                     |   all_gt1y_negative_count |   all_gt1y_min_return_pct |   to_final_negative_count |   min_retention |   median_total_return_pct |   worst_max_drawdown_pct |   objective_pass |
|:--------------------------------------------|--------------------------:|--------------------------:|--------------------------:|----------------:|--------------------------:|-------------------------:|-----------------:|
| c9_base                                     |                    267708 |                  -54.6931 |                         0 |         1       |                   179.443 |                 -55.3701 |                0 |
| c9_plus_xsmom_mom_12m_skip1m_w2p5_cost10bps |                    267868 |                  -54.8603 |                         0 |         1.00048 |                   181.053 |                 -55.3739 |                0 |
| c9_plus_xsmom_mom_12m_skip1m_w5_cost10bps   |                    268045 |                  -55.0277 |                         0 |         1.00096 |                   182.663 |                 -55.5236 |                0 |
| c9_plus_xsmom_mom_12m_skip1m_w7p5_cost10bps |                    268112 |                  -55.195  |                         0 |         1.00143 |                   184.273 |                 -55.6937 |                0 |
| c9_plus_xsmom_mom_12m_skip1m_w10_cost10bps  |                    268217 |                  -55.3624 |                         0 |         1.00191 |                   185.883 |                 -55.8638 |                0 |
| c9_plus_xsmom_mom_12m_skip1m_w20_cost10bps  |                    268760 |                  -56.0324 |                         0 |         1.00383 |                   192.323 |                 -56.5448 |                0 |
| c9_plus_xsmom_mom_12m_skip1m_w30_cost10bps  |                    269184 |                  -56.703  |                         0 |         1.00574 |                   198.763 |                 -57.2264 |                0 |
| c9_plus_xsmom_mom_6m_skip1m_w2p5_cost10bps  |                    269391 |                  -54.8617 |                         0 |         1.00007 |                   179.981 |                 -55.3822 |                0 |
| c9_plus_xsmom_mom_6m_skip1m_w5_cost10bps    |                    270544 |                  -55.0305 |                         0 |         1.00015 |                   180.519 |                 -55.5345 |                0 |
| c9_plus_xsmom_mom_6m_skip1m_w7p5_cost10bps  |                    271768 |                  -55.1993 |                         0 |         1.00022 |                   181.057 |                 -55.7101 |                0 |
| c9_plus_xsmom_mom_6m_skip1m_w10_cost10bps   |                    273103 |                  -55.3683 |                         0 |         1.00029 |                   181.595 |                 -55.8859 |                0 |
| c9_plus_xsmom_mom_6m_skip1m_w20_cost10bps   |                    277498 |                  -56.0449 |                         0 |         1.00059 |                   183.747 |                 -56.5898 |                0 |
| c9_plus_xsmom_mom_6m_skip1m_w30_cost10bps   |                    282241 |                  -56.7231 |                         0 |         1.00088 |                   185.899 |                 -57.2952 |                0 |

## 最优候选多起点摘要

| requested_start_month   |   total_return_pct |   max_drawdown_pct |   sharpe |   xsmom_pnl_delta_end |
|:------------------------|-------------------:|-------------------:|---------:|----------------------:|
| 2020-01                 |          3888.05   |           -55.3739 | 1.39635  |               2787.13 |
| 2020-07                 |          3149.42   |           -54.7414 | 1.40574  |               2787.13 |
| 2021-01                 |          1498.44   |           -54.3354 | 1.28671  |               2422.44 |
| 2021-07                 |           242.607  |           -47.3991 | 0.837972 |               1860.94 |
| 2022-01                 |           117.275  |           -40.1943 | 0.682479 |               2112.8  |
| 2022-07                 |           204.681  |           -55.3535 | 0.931807 |               1557.84 |
| 2023-01                 |           126.319  |           -24.9001 | 0.918434 |               1408.5  |
| 2023-07                 |           181.053  |           -24.2243 | 1.20301  |               2414.97 |
| 2024-01                 |           127.096  |           -22.4415 | 1.2318   |               1345.66 |
| 2024-07                 |            52.0399 |           -23.2096 | 0.799677 |               1207.03 |
| 2025-01                 |            33.105  |           -22.4902 | 0.749072 |               1090.13 |

## 最优候选目标审计

| variant                                     | source_start_month   | audit_scope                 | objective_start_min   | objective_start_max   |   window_count |   positive_count |   negative_count |   negative_rate_pct |   min_return_pct |   mean_return_pct |   is_independent_daily_cold_start |
|:--------------------------------------------|:---------------------|:----------------------------|:----------------------|:----------------------|---------------:|-----------------:|-----------------:|--------------------:|-----------------:|------------------:|----------------------------------:|
| c9_plus_xsmom_mom_12m_skip1m_w2p5_cost10bps | 2020-01              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |         882036 |           836544 |            45492 |            5.15761  |        -54.3831  |          660.037  |                                 0 |
| c9_plus_xsmom_mom_12m_skip1m_w2p5_cost10bps | 2020-01              | start_to_2026_06_30_only    | 2020-01-01            | 2025-06-30            |           1328 |             1328 |                0 |            0        |         17.9667  |          775.991  |                                 0 |
| c9_plus_xsmom_mom_12m_skip1m_w2p5_cost10bps | 2020-07              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |         733565 |           686179 |            47386 |            6.45969  |        -53.762   |          402.8    |                                 0 |
| c9_plus_xsmom_mom_12m_skip1m_w2p5_cost10bps | 2020-07              | start_to_2026_06_30_only    | 2020-01-01            | 2025-06-30            |           1211 |             1211 |                0 |            0        |         18.1596  |          459.051  |                                 0 |
| c9_plus_xsmom_mom_12m_skip1m_w2p5_cost10bps | 2021-01              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |         589005 |           534255 |            54750 |            9.29534  |        -53.3132  |          206.153  |                                 0 |
| c9_plus_xsmom_mom_12m_skip1m_w2p5_cost10bps | 2021-01              | start_to_2026_06_30_only    | 2020-01-01            | 2025-06-30            |           1085 |             1085 |                0 |            0        |         18.1425  |          255.741  |                                 0 |
| c9_plus_xsmom_mom_12m_skip1m_w2p5_cost10bps | 2021-07              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |         467873 |           391934 |            75939 |           16.2307   |        -46.8249  |           73.6651 |                                 0 |
| c9_plus_xsmom_mom_12m_skip1m_w2p5_cost10bps | 2021-07              | start_to_2026_06_30_only    | 2020-01-01            | 2025-06-30            |            967 |              967 |                0 |            0        |         12.3939  |          111.126  |                                 0 |
| c9_plus_xsmom_mom_12m_skip1m_w2p5_cost10bps | 2022-01              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |         354785 |           328231 |            26554 |            7.48453  |        -39.5316  |           85.4321 |                                 0 |
| c9_plus_xsmom_mom_12m_skip1m_w2p5_cost10bps | 2022-01              | start_to_2026_06_30_only    | 2020-01-01            | 2025-06-30            |            842 |              842 |                0 |            0        |         21.6932  |          119.572  |                                 0 |
| c9_plus_xsmom_mom_12m_skip1m_w2p5_cost10bps | 2022-07              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |         263196 |           246347 |            16849 |            6.40169  |        -54.8603  |           97.3489 |                                 0 |
| c9_plus_xsmom_mom_12m_skip1m_w2p5_cost10bps | 2022-07              | start_to_2026_06_30_only    | 2020-01-01            | 2025-06-30            |            725 |              725 |                0 |            0        |         22.5988  |          123.792  |                                 0 |
| c9_plus_xsmom_mom_12m_skip1m_w2p5_cost10bps | 2023-01              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |         180432 |           179534 |              898 |            0.497694 |         -8.79435 |           98.032  |                                 0 |
| c9_plus_xsmom_mom_12m_skip1m_w2p5_cost10bps | 2023-01              | start_to_2026_06_30_only    | 2020-01-01            | 2025-06-30            |            600 |              600 |                0 |            0        |         24.3606  |          105.438  |                                 0 |
| c9_plus_xsmom_mom_12m_skip1m_w2p5_cost10bps | 2023-07              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |         116529 |           116529 |                0 |            0        |          5.4581  |           98.5681 |                                 0 |
| c9_plus_xsmom_mom_12m_skip1m_w2p5_cost10bps | 2023-07              | start_to_2026_06_30_only    | 2020-01-01            | 2025-06-30            |            482 |              482 |                0 |            0        |         18.9405  |           94.0153 |                                 0 |
| c9_plus_xsmom_mom_12m_skip1m_w2p5_cost10bps | 2024-01              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |          64285 |            64285 |                0 |            0        |          1.31499 |           74.2553 |                                 0 |
| c9_plus_xsmom_mom_12m_skip1m_w2p5_cost10bps | 2024-01              | start_to_2026_06_30_only    | 2020-01-01            | 2025-06-30            |            358 |              358 |                0 |            0        |         20.8289  |           68.8555 |                                 0 |
| c9_plus_xsmom_mom_12m_skip1m_w2p5_cost10bps | 2024-07              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |          29059 |            29059 |                0 |            0        |          5.45331 |           56.182  |                                 0 |
| c9_plus_xsmom_mom_12m_skip1m_w2p5_cost10bps | 2024-07              | start_to_2026_06_30_only    | 2020-01-01            | 2025-06-30            |            241 |              241 |                0 |            0        |         21.5612  |           50.5363 |                                 0 |
| c9_plus_xsmom_mom_12m_skip1m_w2p5_cost10bps | 2025-01              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |           6738 |             6738 |                0 |            0        |         11.8088  |           45.8686 |                                 0 |
| c9_plus_xsmom_mom_12m_skip1m_w2p5_cost10bps | 2025-01              | start_to_2026_06_30_only    | 2020-01-01            | 2025-06-30            |            116 |              116 |                0 |            0        |         11.8303  |           36.9173 |                                 0 |

## 过拟合反思

- 运行前判断：否。xsmom 的两个 lookback、月度调仓、top/bottom3 和成本列来自 Stage345/Stage020 固定输入；本阶段只做预声明粗权重 overlay。
- 运行后判断：否，但若根据本次最差窗口继续微调权重、lookback、品种、方向或成本档，就是过拟合。

## 继续价值反思

- 运行前判断：有价值。Stage018/020 已证明低相关腿有历史线索且输入覆盖完整，必须先看它是否真的改善 C9 路径。
- 运行后判断：有限。若连 proxy 都不能改善左尾或保留收益，不应继续扫同一 xsmom 权重。

## 输出文件

- curves：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage021_xsmom_non_crowding_overlay_proxy/rebuilt_c9_v2_stage021_xsmom_non_crowding_overlay_proxy_curves_stage021_xsmom_non_crowding_overlay_proxy_v1.csv`
- summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage021_xsmom_non_crowding_overlay_proxy/rebuilt_c9_v2_stage021_xsmom_non_crowding_overlay_proxy_summary_stage021_xsmom_non_crowding_overlay_proxy_v1.csv`
- goal_aggregate：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage021_xsmom_non_crowding_overlay_proxy/rebuilt_c9_v2_stage021_xsmom_non_crowding_overlay_proxy_goal_aggregate_stage021_xsmom_non_crowding_overlay_proxy_v1.csv`
- goal_to_final：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage021_xsmom_non_crowding_overlay_proxy/rebuilt_c9_v2_stage021_xsmom_non_crowding_overlay_proxy_goal_to_final_windows_stage021_xsmom_non_crowding_overlay_proxy_v1.csv`
- goal_fixed_horizon：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage021_xsmom_non_crowding_overlay_proxy/rebuilt_c9_v2_stage021_xsmom_non_crowding_overlay_proxy_goal_fixed_horizon_windows_stage021_xsmom_non_crowding_overlay_proxy_v1.csv`
- goal_worst_windows：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage021_xsmom_non_crowding_overlay_proxy/rebuilt_c9_v2_stage021_xsmom_non_crowding_overlay_proxy_goal_worst_windows_stage021_xsmom_non_crowding_overlay_proxy_v1.csv`
- retention：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage021_xsmom_non_crowding_overlay_proxy/rebuilt_c9_v2_stage021_xsmom_non_crowding_overlay_proxy_retention_vs_c9_stage021_xsmom_non_crowding_overlay_proxy_v1.csv`
- variant_goal：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage021_xsmom_non_crowding_overlay_proxy/rebuilt_c9_v2_stage021_xsmom_non_crowding_overlay_proxy_variant_goal_table_stage021_xsmom_non_crowding_overlay_proxy_v1.csv`
- chart：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage021_xsmom_non_crowding_overlay_proxy/rebuilt_c9_v2_stage021_xsmom_non_crowding_overlay_proxy_absolute_equity_chart_stage021_xsmom_non_crowding_overlay_proxy_v1.png`
- decision：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage021_xsmom_non_crowding_overlay_proxy/rebuilt_c9_v2_stage021_xsmom_non_crowding_overlay_proxy_decision_stage021_xsmom_non_crowding_overlay_proxy_v1.json`
- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage021_xsmom_non_crowding_overlay_proxy/rebuilt_c9_v2_stage021_xsmom_non_crowding_overlay_proxy_report_stage021_xsmom_non_crowding_overlay_proxy_v1.md`
