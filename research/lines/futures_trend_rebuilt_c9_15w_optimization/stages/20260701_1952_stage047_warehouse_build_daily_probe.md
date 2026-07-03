# Stage047 - 仓单 build 条件日级冷启动探针

- 记录时间：`2026-07-01T19:52`
- line_id：`futures_trend_rebuilt_c9_15w_optimization`
- model_tag：`stage047_warehouse_build_daily_probe_v1`
- 是否重要突破版本：`否`
- 决策：`stage047_warehouse_daily_probe_not_left_tail_solution_no_param_rescue`

## 本次版本变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_optimization/tools/stage047_warehouse_build_daily_probe.py`
- 新增参数：日级探针 bucket quota `{'stage046_worst': 20, 'stage013_worst': 12}`；交易侧仍只使用 `selector=external_warehouse_build_20d` 和 `ADD_RISK_FRACTION=0.25`。
- 修改参数：无，Stage013/Stage046/官方 C9 配置未改。
- 删除参数：无。
- 新增回测结果：真实日级冷启动 Stage013 + Stage046 仓单 build closed-lot proxy。
- 本阶段不连接 CTP，不调用订单 API，不触发 A/B。

## 调研和判断结论

- 库存、仓单、基差和 carry 具有商品期货经济含义，但资料也提示这类信号必须点时化、低自由度并通过组合路径验证。Stage047 因此只验证 Stage046 已冻结的仓单 build 条件在真实日级冷启动上的表现，不继续搜索仓单窗口、分位、品种或倍率。

## 结果

- 探针起点数：`32`。
- bucket 分布：`{'stage013_worst': 12, 'stage046_worst': 20}`。
- Stage013 有负结束日的探针起点：`32`。
- Stage047 proxy 有负结束日的探针起点：`32`。
- Stage013 探针最差收益：`-36.5967%`。
- Stage047 proxy 探针最差收益：`-40.7967%`。
- Stage013 到 `2026-06-30` 最差收益：`55.0954%`。
- Stage047 到 `2026-06-30` 最差收益：`75.1229%`。
- Stage047 proxy delta：`1,393,656.25`。

## 探针起点

|   probe_rank | requested_start   | probe_bucket   | source_variant                          | source_start_month   | source_window_type   | source_end_date   |   source_return_pct |
|-------------:|:------------------|:---------------|:----------------------------------------|:---------------------|:---------------------|:------------------|--------------------:|
|            1 | 2022-07-15        | stage046_worst | stage046_warehouse_build_add_risk_proxy | 2022-07              | all_gt_1y            | 2023-07-17        |            -44.4543 |
|            2 | 2022-07-19        | stage046_worst | stage046_warehouse_build_add_risk_proxy | 2022-07              | all_gt_1y            | 2023-07-24        |            -35.1011 |
|            3 | 2022-07-14        | stage046_worst | stage046_warehouse_build_add_risk_proxy | 2022-07              | all_gt_1y            | 2023-07-17        |            -34.4882 |
|            4 | 2022-03-30        | stage046_worst | stage046_warehouse_build_add_risk_proxy | 2022-01              | all_gt_1y            | 2023-07-07        |            -34.2781 |
|            5 | 2022-07-18        | stage046_worst | stage046_warehouse_build_add_risk_proxy | 2022-07              | all_gt_1y            | 2023-07-24        |            -34.2478 |
|            6 | 2022-03-07        | stage046_worst | stage046_warehouse_build_add_risk_proxy | 2021-07              | all_gt_1y            | 2023-10-23        |            -33.9552 |
|            7 | 2022-03-09        | stage046_worst | stage046_warehouse_build_add_risk_proxy | 2021-07              | all_gt_1y            | 2023-10-23        |            -33.2162 |
|            8 | 2022-03-31        | stage046_worst | stage046_warehouse_build_add_risk_proxy | 2021-07              | all_gt_1y            | 2023-10-23        |            -32.5658 |
|            9 | 2022-04-01        | stage046_worst | stage046_warehouse_build_add_risk_proxy | 2021-07              | all_gt_1y            | 2023-10-23        |            -32.2631 |
|           10 | 2022-07-21        | stage046_worst | stage046_warehouse_build_add_risk_proxy | 2022-07              | all_gt_1y            | 2023-07-24        |            -32.2154 |
|           11 | 2022-07-22        | stage046_worst | stage046_warehouse_build_add_risk_proxy | 2022-07              | all_gt_1y            | 2023-07-24        |            -32.2154 |
|           12 | 2022-07-20        | stage046_worst | stage046_warehouse_build_add_risk_proxy | 2022-07              | all_gt_1y            | 2023-07-24        |            -32.0863 |
|           13 | 2022-03-08        | stage046_worst | stage046_warehouse_build_add_risk_proxy | 2021-07              | all_gt_1y            | 2023-10-20        |            -32.028  |
|           14 | 2022-04-06        | stage046_worst | stage046_warehouse_build_add_risk_proxy | 2021-07              | all_gt_1y            | 2023-10-20        |            -32.027  |
|           15 | 2021-10-26        | stage046_worst | stage046_warehouse_build_add_risk_proxy | 2021-07              | all_gt_1y            | 2023-10-23        |            -31.9272 |
|           16 | 2022-03-11        | stage046_worst | stage046_warehouse_build_add_risk_proxy | 2021-07              | all_gt_1y            | 2023-10-20        |            -31.735  |
|           17 | 2022-04-08        | stage046_worst | stage046_warehouse_build_add_risk_proxy | 2021-07              | all_gt_1y            | 2023-10-23        |            -31.4346 |
|           18 | 2022-04-07        | stage046_worst | stage046_warehouse_build_add_risk_proxy | 2021-07              | all_gt_1y            | 2023-10-23        |            -31.3993 |
|           19 | 2022-03-10        | stage046_worst | stage046_warehouse_build_add_risk_proxy | 2021-07              | all_gt_1y            | 2023-10-20        |            -31.1107 |
|           20 | 2022-04-15        | stage046_worst | stage046_warehouse_build_add_risk_proxy | 2022-01              | all_gt_1y            | 2023-07-07        |            -30.7957 |
|           21 | 2021-10-27        | stage013_worst | stage013_engine                         | 2021-07              | all_gt_1y            | 2023-10-23        |            -34.1485 |
|           22 | 2021-10-25        | stage013_worst | stage013_engine                         | 2021-07              | all_gt_1y            | 2023-10-20        |            -33.2666 |
|           23 | 2021-10-29        | stage013_worst | stage013_engine                         | 2021-07              | all_gt_1y            | 2023-10-20        |            -32.3819 |
|           24 | 2022-08-22        | stage013_worst | stage013_engine                         | 2021-07              | all_gt_1y            | 2023-10-20        |            -31.7281 |
|           25 | 2021-10-18        | stage013_worst | stage013_engine                         | 2019-01              | all_gt_1y            | 2022-12-02        |            -31.4938 |
|           26 | 2022-08-02        | stage013_worst | stage013_engine                         | 2021-07              | all_gt_1y            | 2023-10-20        |            -30.8216 |
|           27 | 2022-07-27        | stage013_worst | stage013_engine                         | 2021-07              | all_gt_1y            | 2023-10-20        |            -30.8216 |
|           28 | 2022-08-01        | stage013_worst | stage013_engine                         | 2021-07              | all_gt_1y            | 2023-10-20        |            -30.8216 |
|           29 | 2022-07-28        | stage013_worst | stage013_engine                         | 2021-07              | all_gt_1y            | 2023-10-20        |            -30.8216 |
|           30 | 2022-07-29        | stage013_worst | stage013_engine                         | 2021-07              | all_gt_1y            | 2023-10-23        |            -30.8216 |
|           31 | 2022-08-19        | stage013_worst | stage013_engine                         | 2021-07              | all_gt_1y            | 2023-10-23        |            -30.8216 |
|           32 | 2022-08-16        | stage013_worst | stage013_engine                         | 2021-07              | all_gt_1y            | 2023-10-20        |            -30.8216 |

## 聚合审计

| variant                                         |   probe_start_count |   negative_probe_start_count |   window_count |   negative_count |   min_return_pct |   to_final_min_return_pct |   end_equity_min |   max_dd_min_pct |   sharpe_median |
|:------------------------------------------------|--------------------:|-----------------------------:|---------------:|-----------------:|-----------------:|--------------------------:|-----------------:|-----------------:|----------------:|
| stage013_daily_cold_start_engine                |                  32 |                           32 |          24501 |             7864 |         -36.5967 |                   55.0954 |           232643 |         -37.7002 |          0.7617 |
| stage047_daily_cold_start_warehouse_build_proxy |                  32 |                           32 |          24501 |             7780 |         -40.7967 |                   75.1229 |           262684 |         -40.7967 |          0.8594 |

## 输出

- probe_starts：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage047_warehouse_build_daily_probe/rebuilt_c9_stage047_warehouse_build_daily_probe_probe_starts_stage047_warehouse_build_daily_probe_v1.csv`
- summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage047_warehouse_build_daily_probe/rebuilt_c9_stage047_warehouse_build_daily_probe_summary_stage047_warehouse_build_daily_probe_v1.csv`
- aggregate：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage047_warehouse_build_daily_probe/rebuilt_c9_stage047_warehouse_build_daily_probe_aggregate_stage047_warehouse_build_daily_probe_v1.csv`
- curves：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage047_warehouse_build_daily_probe/rebuilt_c9_stage047_warehouse_build_daily_probe_curves_stage047_warehouse_build_daily_probe_v1.csv`
- lot_deltas：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage047_warehouse_build_daily_probe/rebuilt_c9_stage047_warehouse_build_daily_probe_lot_deltas_stage047_warehouse_build_daily_probe_v1.csv`
- decision：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage047_warehouse_build_daily_probe/rebuilt_c9_stage047_warehouse_build_daily_probe_decision_stage047_warehouse_build_daily_probe_v1.json`
- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage047_warehouse_build_daily_probe/rebuilt_c9_stage047_warehouse_build_daily_probe_report_stage047_warehouse_build_daily_probe_v1.md`

## 反思

- 运行前过拟合反思：否。Stage047 只把 Stage046 固定条件搬到日级冷启动探针，不新增交易规则、不调阈值。
- 运行后过拟合反思：否。本阶段仍是预声明 proxy；若根据结果改仓单窗口、分位、产品、年份、方向或倍率就是过拟合。
- 运行前继续价值反思：有。Stage046 只在半年源曲线上部分改善，必须验证具体日级起点是否也改善。
- 运行后继续价值反思：有限。若日级探针不能减少负起点，应停止救仓单 build 参数，转新外生源或真实路径归因。
