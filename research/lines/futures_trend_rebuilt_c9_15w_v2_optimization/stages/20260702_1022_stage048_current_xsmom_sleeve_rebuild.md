# Stage048 当前 C9 xsmom 独立 sleeve 重建

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-02T10:22:05
- 阶段性质：当前重建 C9/15w 上的固定 xsmom 独立日级收益腿；只读，不改官方 live config、不连接 CTP、不调用下单
- 是否重要突破：否
- 是否触发A/B：否。若本阶段通过，也必须先做真实整数手/保证金/分钟成交 ledger。

## 外部调研与判断

- 参考资料：Moskowitz/Ooi/Pedersen Time Series Momentum、AQR Demystifying Managed Futures、pysystemtrade backtesting/diversification multiplier、商品期货 momentum/carry 研究。
- 我的判断：低相关 xsmom sleeve 仍是合理方向，但必须按当前重建 C9 和当前输入重新验证；旧 Stage208 只能提供结构灵感，不能当作当前证据。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage048_current_xsmom_sleeve_rebuild.py`
- 新增测试：`tests/test_rebuilt_c9_v2_stage048_current_xsmom_sleeve_rebuild.py`
- 新增参数：`SLEEVE_CAPITAL=15000.0`、`PREDECLARED_SPECS=['mom_12m_skip1m', 'mom_6m_skip1m']`、`DEFAULT_COST_BPS=10.0`
- 修改参数：无正式策略参数修改
- 删除参数：无

## 回测/归因参数

- 基础曲线：Stage167 当前重建 C9/15w 多起点曲线。
- xsmom 输入：Stage020 `satellite_daily`，含 `jd.DCE`。
- 叠加公式：`account_equity = c9_account_equity + 15000 * (xsmom_nav - 1)`。
- 审计：所有 `2020-01-01` 到 `2025-06-30` 曲线内交易日起点，所有 `>365` 天终点；到 `2026-06-30` 终点；固定 horizon；80% 收益保留 vs C9。
- 输入就绪：`True`；阻塞原因：``。

## 结果

- 基准 C9 严格 `>1` 年负窗口：`267708`，最差 `-54.6931%`
- 最优 sleeve：`stage048_current_mom_12m_skip1m_sleeve10pct_cost10bps`
- 最优 sleeve 严格 `>1` 年负窗口：`268217`，最差 `-55.3624%`
- 最优 sleeve 最小收益保留：`1.0019`
- 最优 sleeve 多起点中位收益：`185.8834%`
- 最优 sleeve 最差最大回撤：`-55.8638%`
- 目标通过 variant 数：`0`
- 决策：`stage048_current_xsmom_sleeve_not_promoted_keep_readonly`
- 策略变更：`False`
- order API：`0`
- CTP：`False`

## 预声明规格

| variant                                               | xsmom_spec     |   cost_bps |   sleeve_capital | source_stage   | current_c9_only   | no_parameter_sweep   |
|:------------------------------------------------------|:---------------|-----------:|-----------------:|:---------------|:------------------|:---------------------|
| stage048_current_mom_12m_skip1m_sleeve10pct_cost10bps | mom_12m_skip1m |         10 |            15000 | Stage020       | True              | True                 |
| stage048_current_mom_6m_skip1m_sleeve10pct_cost10bps  | mom_6m_skip1m  |         10 |            15000 | Stage020       | True              | True                 |

## 目标门汇总

| variant                                               |   all_gt1y_negative_count |   all_gt1y_min_return_pct |   to_final_negative_count |   min_retention |   median_total_return_pct |   worst_max_drawdown_pct |   objective_pass |
|:------------------------------------------------------|--------------------------:|--------------------------:|--------------------------:|----------------:|--------------------------:|-------------------------:|-----------------:|
| c9_base                                               |                    267708 |                  -54.6931 |                         0 |         1       |                   179.443 |                 -55.3701 |                0 |
| stage048_current_mom_12m_skip1m_sleeve10pct_cost10bps |                    268217 |                  -55.3624 |                         0 |         1.00191 |                   185.883 |                 -55.8638 |                0 |
| stage048_current_mom_6m_skip1m_sleeve10pct_cost10bps  |                    273103 |                  -55.3683 |                         0 |         1.00029 |                   181.595 |                 -55.8859 |                0 |

## 最优候选多起点摘要

| requested_start_month   |   total_return_pct |   max_drawdown_pct |   sharpe |   sleeve_pnl_delta_end |   sleeve_turnover_sum |
|:------------------------|-------------------:|-------------------:|---------:|-----------------------:|----------------------:|
| 2020-01                 |          3893.62   |           -55.3854 | 1.39766  |               11148.5  |              33.6667  |
| 2020-07                 |          3155      |           -54.7552 | 1.40736  |               11148.5  |              33.6667  |
| 2021-01                 |          1503.29   |           -54.3878 | 1.28917  |                9689.75 |              31.6667  |
| 2021-07                 |           246.329  |           -47.7618 | 0.845231 |                7443.75 |              29.3333  |
| 2022-01                 |           121.5    |           -40.8262 | 0.698074 |                8451.19 |              26       |
| 2022-07                 |           207.797  |           -55.8638 | 0.940025 |                6231.35 |              22       |
| 2023-01                 |           129.136  |           -26.1913 | 0.932232 |                5633.99 |              18.3333  |
| 2023-07                 |           185.883  |           -23.7672 | 1.23071  |                9659.9  |              15       |
| 2024-01                 |           129.788  |           -22.0819 | 1.25303  |                5382.66 |              12       |
| 2024-07                 |            54.4539 |           -22.7166 | 0.829322 |                4828.12 |              10.3333  |
| 2025-01                 |            35.2853 |           -22.0114 | 0.787843 |                4360.51 |               7.33333 |

## 最优候选目标审计

| variant                                               | source_start_month   | audit_scope                 | objective_start_min   | objective_start_max   |   window_count |   positive_count |   negative_count |   negative_rate_pct |   min_return_pct |   mean_return_pct |   is_independent_daily_cold_start |
|:------------------------------------------------------|:---------------------|:----------------------------|:----------------------|:----------------------|---------------:|-----------------:|-----------------:|--------------------:|-----------------:|------------------:|----------------------------------:|
| stage048_current_mom_12m_skip1m_sleeve10pct_cost10bps | 2020-01              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |         882036 |           836537 |            45499 |            5.15841  |        -54.3945  |          660.597  |                                 0 |
| stage048_current_mom_12m_skip1m_sleeve10pct_cost10bps | 2020-01              | start_to_2026_06_30_only    | 2020-01-01            | 2025-06-30            |           1328 |             1328 |                0 |            0        |         17.9526  |          776.714  |                                 0 |
| stage048_current_mom_12m_skip1m_sleeve10pct_cost10bps | 2020-07              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |         733565 |           686240 |            47325 |            6.45137  |        -53.7756  |          403.057  |                                 0 |
| stage048_current_mom_12m_skip1m_sleeve10pct_cost10bps | 2020-07              | start_to_2026_06_30_only    | 2020-01-01            | 2025-06-30            |           1211 |             1211 |                0 |            0        |         18.1418  |          459.427  |                                 0 |
| stage048_current_mom_12m_skip1m_sleeve10pct_cost10bps | 2021-01              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |         589005 |           534281 |            54724 |            9.29092  |        -53.3649  |          206.369  |                                 0 |
| stage048_current_mom_12m_skip1m_sleeve10pct_cost10bps | 2021-01              | start_to_2026_06_30_only    | 2020-01-01            | 2025-06-30            |           1085 |             1085 |                0 |            0        |         18.1141  |          256.169  |                                 0 |
| stage048_current_mom_12m_skip1m_sleeve10pct_cost10bps | 2021-07              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |         467873 |           392025 |            75848 |           16.2112   |        -47.1814  |           74.5801 |                                 0 |
| stage048_current_mom_12m_skip1m_sleeve10pct_cost10bps | 2021-07              | start_to_2026_06_30_only    | 2020-01-01            | 2025-06-30            |            967 |              967 |                0 |            0        |         12.3828  |          112.808  |                                 0 |
| stage048_current_mom_12m_skip1m_sleeve10pct_cost10bps | 2022-01              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |         354785 |           327710 |            27075 |            7.63138  |        -40.1531  |           86.7584 |                                 0 |
| stage048_current_mom_12m_skip1m_sleeve10pct_cost10bps | 2022-01              | start_to_2026_06_30_only    | 2020-01-01            | 2025-06-30            |            842 |              842 |                0 |            0        |         21.4556  |          121.844  |                                 0 |
| stage048_current_mom_12m_skip1m_sleeve10pct_cost10bps | 2022-07              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |         263196 |           246361 |            16835 |            6.39637  |        -55.3624  |           99.0972 |                                 0 |
| stage048_current_mom_12m_skip1m_sleeve10pct_cost10bps | 2022-07              | start_to_2026_06_30_only    | 2020-01-01            | 2025-06-30            |            725 |              725 |                0 |            0        |         22.4941  |          126.077  |                                 0 |
| stage048_current_mom_12m_skip1m_sleeve10pct_cost10bps | 2023-01              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |         180432 |           179521 |              911 |            0.504899 |         -9.10496 |          100.754  |                                 0 |
| stage048_current_mom_12m_skip1m_sleeve10pct_cost10bps | 2023-01              | start_to_2026_06_30_only    | 2020-01-01            | 2025-06-30            |            600 |              600 |                0 |            0        |         24.2241  |          108.387  |                                 0 |
| stage048_current_mom_12m_skip1m_sleeve10pct_cost10bps | 2023-07              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |         116529 |           116529 |                0 |            0        |          6.58544 |          100.249  |                                 0 |
| stage048_current_mom_12m_skip1m_sleeve10pct_cost10bps | 2023-07              | start_to_2026_06_30_only    | 2020-01-01            | 2025-06-30            |            482 |              482 |                0 |            0        |         18.7669  |           95.5408 |                                 0 |
| stage048_current_mom_12m_skip1m_sleeve10pct_cost10bps | 2024-01              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |          64285 |            64285 |                0 |            0        |          2.47509 |           76.0892 |                                 0 |
| stage048_current_mom_12m_skip1m_sleeve10pct_cost10bps | 2024-01              | start_to_2026_06_30_only    | 2020-01-01            | 2025-06-30            |            358 |              358 |                0 |            0        |         20.7536  |           70.4637 |                                 0 |
| stage048_current_mom_12m_skip1m_sleeve10pct_cost10bps | 2024-07              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |          29059 |            29059 |                0 |            0        |          6.99204 |           58.3159 |                                 0 |
| stage048_current_mom_12m_skip1m_sleeve10pct_cost10bps | 2024-07              | start_to_2026_06_30_only    | 2020-01-01            | 2025-06-30            |            241 |              241 |                0 |            0        |         21.4729  |           52.1976 |                                 0 |
| stage048_current_mom_12m_skip1m_sleeve10pct_cost10bps | 2025-01              | all_trading_end_dates_gt_1y | 2020-01-01            | 2025-06-30            |           6738 |             6738 |                0 |            0        |         11.8358  |           47.4401 |                                 0 |
| stage048_current_mom_12m_skip1m_sleeve10pct_cost10bps | 2025-01              | start_to_2026_06_30_only    | 2020-01-01            | 2025-06-30            |            116 |              116 |                0 |            0        |         11.9203  |           37.8792 |                                 0 |

## 收益保留

| variant                                               | requested_start_month   | xsmom_spec     |   cost_bps |   sleeve_capital |   total_return_pct |   c9_total_return_pct |   return_retention_vs_c9 |   passes_80pct_retention |
|:------------------------------------------------------|:------------------------|:---------------|-----------:|-----------------:|-------------------:|----------------------:|-------------------------:|-------------------------:|
| stage048_current_mom_12m_skip1m_sleeve10pct_cost10bps | 2020-01                 | mom_12m_skip1m |         10 |            15000 |          3893.62   |             3886.19   |                  1.00191 |                        1 |
| stage048_current_mom_12m_skip1m_sleeve10pct_cost10bps | 2020-07                 | mom_12m_skip1m |         10 |            15000 |          3155      |             3147.57   |                  1.00236 |                        1 |
| stage048_current_mom_12m_skip1m_sleeve10pct_cost10bps | 2021-01                 | mom_12m_skip1m |         10 |            15000 |          1503.29   |             1496.83   |                  1.00432 |                        1 |
| stage048_current_mom_12m_skip1m_sleeve10pct_cost10bps | 2021-07                 | mom_12m_skip1m |         10 |            15000 |           246.329  |              241.367  |                  1.02056 |                        1 |
| stage048_current_mom_12m_skip1m_sleeve10pct_cost10bps | 2022-01                 | mom_12m_skip1m |         10 |            15000 |           121.5    |              115.866  |                  1.04863 |                        1 |
| stage048_current_mom_12m_skip1m_sleeve10pct_cost10bps | 2022-07                 | mom_12m_skip1m |         10 |            15000 |           207.797  |              203.642  |                  1.0204  |                        1 |
| stage048_current_mom_12m_skip1m_sleeve10pct_cost10bps | 2023-01                 | mom_12m_skip1m |         10 |            15000 |           129.136  |              125.38   |                  1.02996 |                        1 |
| stage048_current_mom_12m_skip1m_sleeve10pct_cost10bps | 2023-07                 | mom_12m_skip1m |         10 |            15000 |           185.883  |              179.443  |                  1.03589 |                        1 |
| stage048_current_mom_12m_skip1m_sleeve10pct_cost10bps | 2024-01                 | mom_12m_skip1m |         10 |            15000 |           129.788  |              126.199  |                  1.02843 |                        1 |
| stage048_current_mom_12m_skip1m_sleeve10pct_cost10bps | 2024-07                 | mom_12m_skip1m |         10 |            15000 |            54.4539 |               51.2352 |                  1.06282 |                        1 |
| stage048_current_mom_12m_skip1m_sleeve10pct_cost10bps | 2025-01                 | mom_12m_skip1m |         10 |            15000 |            35.2853 |               32.3783 |                  1.08978 |                        1 |

## 过拟合反思

- 运行前判断：否。Stage048 只沿 Stage047 指定的历史 xsmom true-carry 路线，在当前 Stage020/Stage167 输入上复建固定口径。
- 运行后判断：否。本阶段没有按最差窗口调参；若接下来根据这次结果微调 lookback、成本、品种或 sleeve capital，就是过拟合风险。

## 继续价值反思

- 运行前判断：有。Stage047 已确认当前没有可直接晋级的独立收益腿，历史 Stage208 路线是最值得重建验证的方向。
- 运行后判断：有限。固定 xsmom sleeve 未改善当前 C9 目标门，不应继续围绕同源 lookback/权重细调。

## 输出文件

- curves：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage048_current_xsmom_sleeve_rebuild/rebuilt_c9_v2_stage048_current_xsmom_sleeve_rebuild_curves_stage048_current_xsmom_sleeve_rebuild_v1.csv`
- summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage048_current_xsmom_sleeve_rebuild/rebuilt_c9_v2_stage048_current_xsmom_sleeve_rebuild_summary_stage048_current_xsmom_sleeve_rebuild_v1.csv`
- goal_aggregate：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage048_current_xsmom_sleeve_rebuild/rebuilt_c9_v2_stage048_current_xsmom_sleeve_rebuild_goal_aggregate_stage048_current_xsmom_sleeve_rebuild_v1.csv`
- goal_to_final：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage048_current_xsmom_sleeve_rebuild/rebuilt_c9_v2_stage048_current_xsmom_sleeve_rebuild_goal_to_final_windows_stage048_current_xsmom_sleeve_rebuild_v1.csv`
- goal_fixed_horizon：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage048_current_xsmom_sleeve_rebuild/rebuilt_c9_v2_stage048_current_xsmom_sleeve_rebuild_goal_fixed_horizon_windows_stage048_current_xsmom_sleeve_rebuild_v1.csv`
- goal_worst_windows：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage048_current_xsmom_sleeve_rebuild/rebuilt_c9_v2_stage048_current_xsmom_sleeve_rebuild_goal_worst_windows_stage048_current_xsmom_sleeve_rebuild_v1.csv`
- retention：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage048_current_xsmom_sleeve_rebuild/rebuilt_c9_v2_stage048_current_xsmom_sleeve_rebuild_retention_vs_c9_stage048_current_xsmom_sleeve_rebuild_v1.csv`
- variant_goal：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage048_current_xsmom_sleeve_rebuild/rebuilt_c9_v2_stage048_current_xsmom_sleeve_rebuild_variant_goal_table_stage048_current_xsmom_sleeve_rebuild_v1.csv`
- readiness：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage048_current_xsmom_sleeve_rebuild/rebuilt_c9_v2_stage048_current_xsmom_sleeve_rebuild_readiness_stage048_current_xsmom_sleeve_rebuild_v1.json`
- chart：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage048_current_xsmom_sleeve_rebuild/rebuilt_c9_v2_stage048_current_xsmom_sleeve_rebuild_absolute_equity_chart_stage048_current_xsmom_sleeve_rebuild_v1.png`
- decision：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage048_current_xsmom_sleeve_rebuild/rebuilt_c9_v2_stage048_current_xsmom_sleeve_rebuild_decision_stage048_current_xsmom_sleeve_rebuild_v1.json`
- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage048_current_xsmom_sleeve_rebuild/rebuilt_c9_v2_stage048_current_xsmom_sleeve_rebuild_report_stage048_current_xsmom_sleeve_rebuild_v1.md`
