# Stage053 - contract_oi_share_ge50 日级冷启动探针

- 记录时间：`2026-07-01T20:58`
- line_id：`futures_trend_rebuilt_c9_15w_optimization`
- model_tag：`stage053_contract_oi_share_daily_probe_v1`
- 是否重要突破版本：`否`
- 决策：`stage053_contract_oi_daily_probe_not_left_tail_solution_no_param_rescue`

## 本次版本变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_optimization/tools/stage053_contract_oi_share_daily_probe.py`
- 新增测试：`tests/test_rebuilt_c9_stage053_contract_oi_daily_probe.py`
- 新增参数：日级探针 bucket quota `{'stage052_worst': 20, 'stage013_worst': 12}`；交易侧仍只使用 `selector=contract_oi_share_ge50` 和 `ADD_RISK_FRACTION=0.25`。
- 修改参数：无，Stage013/Stage052/官方 C9 配置未改。
- 删除参数：无。
- 新增回测结果：真实日级冷启动 Stage013 + Stage052 OI 份额 closed-lot proxy。
- 本阶段不连接 CTP，不调用订单 API，不触发 A/B。

## 调研和判断结论

- CME 把 OI 作为未平仓参与度和换月节奏的重要市场结构信息；Databento 连续合约资料也强调 OI 是 roll 构造中的核心输入之一。Stage053 因此只把 Stage052 冻结的 `contract_oi_share_ge50` 作为流动性/换月质量 proxy 搬到真实日级冷启动路径，不把 OI 阈值当 alpha 搜参。

## 结果

- 探针起点数：`32`。
- bucket 分布：`{'stage013_worst': 12, 'stage052_worst': 20}`。
- Stage013 有负结束日的探针起点：`32`。
- Stage053 proxy 有负结束日的探针起点：`32`。
- Stage013 探针最差收益：`-36.5967%`。
- Stage053 proxy 探针最差收益：`-43.8208%`。
- Stage013 到 `2026-06-30` 最差收益：`55.0954%`。
- Stage053 到 `2026-06-30` 最差收益：`70.9263%`。
- Stage013 最低期末权益：`232,643.10`。
- Stage053 最低期末权益：`256,389.45`。
- Stage053 proxy delta：`1,479,339.45`。

## 探针起点

|   probe_rank | requested_start   | probe_bucket   | source_variant                                 | source_start_month   | source_window_type   | source_end_date   |   source_return_pct |
|-------------:|:------------------|:---------------|:-----------------------------------------------|:---------------------|:---------------------|:------------------|--------------------:|
|            1 | 2022-07-15        | stage052_worst | stage052_contract_oi_share_ge50_add_risk_proxy | 2022-07              | all_gt_1y            | 2023-07-17        |            -40.3699 |
|            2 | 2022-07-22        | stage052_worst | stage052_contract_oi_share_ge50_add_risk_proxy | 2022-07              | all_gt_1y            | 2023-07-24        |            -33.4227 |
|            3 | 2022-07-21        | stage052_worst | stage052_contract_oi_share_ge50_add_risk_proxy | 2022-07              | all_gt_1y            | 2023-07-24        |            -33.4227 |
|            4 | 2022-03-30        | stage052_worst | stage052_contract_oi_share_ge50_add_risk_proxy | 2022-01              | all_gt_1y            | 2023-07-07        |            -33.3636 |
|            5 | 2022-03-07        | stage052_worst | stage052_contract_oi_share_ge50_add_risk_proxy | 2022-01              | all_gt_1y            | 2023-07-07        |            -31.968  |
|            6 | 2022-03-31        | stage052_worst | stage052_contract_oi_share_ge50_add_risk_proxy | 2022-01              | all_gt_1y            | 2023-07-07        |            -31.5054 |
|            7 | 2022-04-01        | stage052_worst | stage052_contract_oi_share_ge50_add_risk_proxy | 2022-01              | all_gt_1y            | 2023-07-07        |            -31.2524 |
|            8 | 2022-08-22        | stage052_worst | stage052_contract_oi_share_ge50_add_risk_proxy | 2021-07              | all_gt_1y            | 2023-10-20        |            -31.2137 |
|            9 | 2022-07-19        | stage052_worst | stage052_contract_oi_share_ge50_add_risk_proxy | 2022-07              | all_gt_1y            | 2023-07-24        |            -31.1713 |
|           10 | 2022-04-06        | stage052_worst | stage052_contract_oi_share_ge50_add_risk_proxy | 2022-01              | all_gt_1y            | 2023-07-07        |            -31.0311 |
|           11 | 2022-04-07        | stage052_worst | stage052_contract_oi_share_ge50_add_risk_proxy | 2022-01              | all_gt_1y            | 2023-07-07        |            -30.8566 |
|           12 | 2022-07-25        | stage052_worst | stage052_contract_oi_share_ge50_add_risk_proxy | 2022-07              | all_gt_1y            | 2023-07-26        |            -30.8206 |
|           13 | 2022-04-08        | stage052_worst | stage052_contract_oi_share_ge50_add_risk_proxy | 2022-01              | all_gt_1y            | 2023-07-07        |            -30.712  |
|           14 | 2022-04-13        | stage052_worst | stage052_contract_oi_share_ge50_add_risk_proxy | 2022-01              | all_gt_1y            | 2023-07-07        |            -30.7076 |
|           15 | 2022-04-11        | stage052_worst | stage052_contract_oi_share_ge50_add_risk_proxy | 2022-01              | all_gt_1y            | 2023-07-07        |            -30.7076 |
|           16 | 2022-04-14        | stage052_worst | stage052_contract_oi_share_ge50_add_risk_proxy | 2022-01              | all_gt_1y            | 2023-07-07        |            -30.7076 |
|           17 | 2022-04-15        | stage052_worst | stage052_contract_oi_share_ge50_add_risk_proxy | 2022-01              | all_gt_1y            | 2023-07-07        |            -30.7076 |
|           18 | 2022-04-12        | stage052_worst | stage052_contract_oi_share_ge50_add_risk_proxy | 2022-01              | all_gt_1y            | 2023-07-07        |            -30.7076 |
|           19 | 2022-08-16        | stage052_worst | stage052_contract_oi_share_ge50_add_risk_proxy | 2021-07              | all_gt_1y            | 2023-10-20        |            -30.4585 |
|           20 | 2022-08-04        | stage052_worst | stage052_contract_oi_share_ge50_add_risk_proxy | 2021-07              | all_gt_1y            | 2023-10-23        |            -30.4585 |
|           21 | 2021-10-26        | stage013_worst | stage013_engine                                | 2021-07              | all_gt_1y            | 2023-10-20        |            -35.2888 |
|           22 | 2021-10-27        | stage013_worst | stage013_engine                                | 2021-07              | all_gt_1y            | 2023-10-20        |            -34.1485 |
|           23 | 2022-03-09        | stage013_worst | stage013_engine                                | 2021-07              | all_gt_1y            | 2023-10-23        |            -34.1485 |
|           24 | 2022-07-14        | stage013_worst | stage013_engine                                | 2022-07              | all_gt_1y            | 2023-07-17        |            -33.7094 |
|           25 | 2022-07-18        | stage013_worst | stage013_engine                                | 2022-07              | all_gt_1y            | 2023-07-24        |            -33.5177 |
|           26 | 2021-10-25        | stage013_worst | stage013_engine                                | 2021-07              | all_gt_1y            | 2023-10-23        |            -33.2666 |
|           27 | 2022-03-08        | stage013_worst | stage013_engine                                | 2021-07              | all_gt_1y            | 2023-10-20        |            -32.8677 |
|           28 | 2021-10-29        | stage013_worst | stage013_engine                                | 2021-07              | all_gt_1y            | 2023-10-20        |            -32.3819 |
|           29 | 2022-03-11        | stage013_worst | stage013_engine                                | 2021-07              | all_gt_1y            | 2023-10-20        |            -32.1363 |
|           30 | 2022-03-10        | stage013_worst | stage013_engine                                | 2021-07              | all_gt_1y            | 2023-10-23        |            -31.8761 |
|           31 | 2021-10-18        | stage013_worst | stage013_engine                                | 2019-01              | all_gt_1y            | 2022-12-05        |            -31.4938 |
|           32 | 2022-07-20        | stage013_worst | stage013_engine                                | 2022-07              | all_gt_1y            | 2023-07-24        |            -31.3322 |

## 聚合审计

| variant                                           |   probe_start_count |   negative_probe_start_count |   window_count |   negative_count |   min_return_pct |   to_final_min_return_pct |   end_equity_min |   max_dd_min_pct |   sharpe_median |
|:--------------------------------------------------|--------------------:|-----------------------------:|---------------:|-----------------:|-----------------:|--------------------------:|-----------------:|-----------------:|----------------:|
| stage013_daily_cold_start_engine                  |                  32 |                           32 |          24804 |             8191 |         -36.5967 |                   55.0954 |           232643 |         -37.7002 |          0.7607 |
| stage053_daily_cold_start_contract_oi_share_proxy |                  32 |                           32 |          24804 |             8162 |         -43.8208 |                   70.9263 |           256389 |         -45.3616 |          0.8793 |

## 输出

- probe_starts：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage053_contract_oi_share_daily_probe/rebuilt_c9_stage053_contract_oi_share_daily_probe_probe_starts_stage053_contract_oi_share_daily_probe_v1.csv`
- summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage053_contract_oi_share_daily_probe/rebuilt_c9_stage053_contract_oi_share_daily_probe_summary_stage053_contract_oi_share_daily_probe_v1.csv`
- aggregate：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage053_contract_oi_share_daily_probe/rebuilt_c9_stage053_contract_oi_share_daily_probe_aggregate_stage053_contract_oi_share_daily_probe_v1.csv`
- curves：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage053_contract_oi_share_daily_probe/rebuilt_c9_stage053_contract_oi_share_daily_probe_curves_stage053_contract_oi_share_daily_probe_v1.csv`
- lot_deltas：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage053_contract_oi_share_daily_probe/rebuilt_c9_stage053_contract_oi_share_daily_probe_lot_deltas_stage053_contract_oi_share_daily_probe_v1.csv`
- decision：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage053_contract_oi_share_daily_probe/rebuilt_c9_stage053_contract_oi_share_daily_probe_decision_stage053_contract_oi_share_daily_probe_v1.json`
- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage053_contract_oi_share_daily_probe/rebuilt_c9_stage053_contract_oi_share_daily_probe_report_stage053_contract_oi_share_daily_probe_v1.md`
- absolute_equity_chart：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage053_contract_oi_share_daily_probe/rebuilt_c9_stage053_contract_oi_share_daily_probe_absolute_equity_chart_stage053_contract_oi_share_daily_probe_v1.png`
- nav_chart：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage053_contract_oi_share_daily_probe/rebuilt_c9_stage053_contract_oi_share_daily_probe_nav_chart_stage053_contract_oi_share_daily_probe_v1.png`

## 反思

- 运行前过拟合反思：否。Stage053 只复验 Stage052 固定条件和固定 25% 非挤占风险，不新增阈值、窗口、品种或方向选择。
- 运行后过拟合反思：否。本阶段仍是预声明日级 proxy；若根据结果改 `0.50` 阈值、年份、方向、品种或倍率就是过拟合。
- 运行前继续价值反思：有。Stage052 半年源曲线有部分改善，但必须确认逐日起点真实重跑后仍能绑定 OI 并改善左尾。
- 运行后继续价值反思：有限。若日级探针不能减少负起点，应停止救 OI 阈值，转真实路径归因或更强 PIT 信息源。
