# Stage042 - 扩展独立日级冷启动探针

- 记录时间：`2026-07-01T19:00`
- line_id：`futures_trend_rebuilt_c9_15w_optimization`
- model_tag：`stage042_expanded_daily_cold_start_probe_v1`
- 是否重要突破版本：`否`
- 决策：`stage042_expanded_probe_confirms_left_tail_persistent_not_ai_top8_solved`

## 本次版本变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_optimization/tools/stage042_expanded_daily_cold_start_probe.py`
- 新增参数：分层探针 quota `{'both_negative': 16, 'added_negative_absolute_worse': 6, 'added_negative_denominator': 4, 'fixed_by_stage039': 6}`；不新增交易参数。
- 修改参数：无，Stage013/Stage039/官方 C9 配置未改。
- 删除参数：无。
- 新增回测结果：扩展日级冷启动真引擎探针 + Stage039 top8 closed-lot proxy。
- 本阶段不连接 CTP，不调用订单 API，不触发 A/B。

## 调研和判断结论

- Managed futures / trend-following literature commonly emphasizes target volatility, drawdown duration, correlation/volatility regimes and portfolio-level risk budgeting. Stage042 therefore expands true daily cold-start evidence instead of optimizing a new date/product/topN rule.

## 结果

- 探针起点数：`32`。
- bucket 分布：`{'added_negative_absolute_worse': 6, 'added_negative_denominator': 4, 'both_negative': 16, 'fixed_by_stage039': 6}`。
- Stage013 有负结束日的探针起点：`32`。
- Stage042 proxy 有负结束日的探针起点：`32`。
- Stage013 探针最差收益：`-36.5967%`。
- Stage042 proxy 探针最差收益：`-36.4775%`。
- Stage042 proxy delta：`587,167.85`。

## 探针起点

|   probe_rank | requested_start   | probe_bucket                  | source_window_class        |   source_stage039_return_pct |   source_stage013_return_pct |   source_stage039_absolute_end_ge_stage013 |
|-------------:|:------------------|:------------------------------|:---------------------------|-----------------------------:|-----------------------------:|-------------------------------------------:|
|            1 | 2022-07-15        | both_negative                 | both_negative              |                     -44.1402 |                     -43.794  |                                          0 |
|            2 | 2022-07-19        | both_negative                 | both_negative              |                     -34.7842 |                     -34.3804 |                                          0 |
|            3 | 2021-10-26        | both_negative                 | both_negative              |                     -34.354  |                     -35.2888 |                                          1 |
|            4 | 2022-03-07        | both_negative                 | both_negative              |                     -34.1855 |                     -34.943  |                                          1 |
|            5 | 2022-07-14        | both_negative                 | both_negative              |                     -34.1177 |                     -33.7094 |                                          0 |
|            6 | 2022-07-18        | both_negative                 | both_negative              |                     -33.9267 |                     -33.5177 |                                          0 |
|            7 | 2022-03-09        | both_negative                 | both_negative              |                     -33.384  |                     -34.1485 |                                          1 |
|            8 | 2021-10-27        | both_negative                 | both_negative              |                     -33.1973 |                     -34.1485 |                                          1 |
|            9 | 2022-03-30        | both_negative                 | both_negative              |                     -32.6927 |                     -33.8208 |                                          1 |
|           10 | 2021-10-25        | both_negative                 | both_negative              |                     -32.3026 |                     -33.2666 |                                          1 |
|           11 | 2022-03-08        | both_negative                 | both_negative              |                     -32.092  |                     -32.8677 |                                          1 |
|           12 | 2022-07-21        | both_negative                 | both_negative              |                     -31.8844 |                     -31.4627 |                                          0 |
|           13 | 2022-07-22        | both_negative                 | both_negative              |                     -31.8844 |                     -31.4627 |                                          0 |
|           14 | 2022-07-20        | both_negative                 | both_negative              |                     -31.7548 |                     -31.3322 |                                          0 |
|           15 | 2022-08-22        | both_negative                 | both_negative              |                     -31.7532 |                     -31.7281 |                                          1 |
|           16 | 2022-04-01        | both_negative                 | both_negative              |                     -31.7166 |                     -32.1193 |                                          1 |
|           17 | 2022-08-23        | added_negative_absolute_worse | added_negative_by_stage039 |                      -1.7025 |                       0.0246 |                                          0 |
|           18 | 2022-08-26        | added_negative_absolute_worse | added_negative_by_stage039 |                      -1.6488 |                       0.0401 |                                          0 |
|           19 | 2022-09-21        | added_negative_absolute_worse | added_negative_by_stage039 |                      -1.639  |                       0.1476 |                                          0 |
|           20 | 2022-07-29        | added_negative_absolute_worse | added_negative_by_stage039 |                      -1.5081 |                       0.1739 |                                          0 |
|           21 | 2022-07-27        | added_negative_absolute_worse | added_negative_by_stage039 |                      -1.5081 |                       0.1739 |                                          0 |
|           22 | 2022-08-04        | added_negative_absolute_worse | added_negative_by_stage039 |                      -1.5081 |                       0.1739 |                                          0 |
|           23 | 2022-11-08        | added_negative_denominator    | added_negative_by_stage039 |                      -1.6577 |                       0.0127 |                                          1 |
|           24 | 2022-05-05        | added_negative_denominator    | added_negative_by_stage039 |                      -1.6096 |                       0.0236 |                                          1 |
|           25 | 2022-10-28        | added_negative_denominator    | added_negative_by_stage039 |                      -1.6048 |                       0.0998 |                                          1 |
|           26 | 2022-11-18        | added_negative_denominator    | added_negative_by_stage039 |                      -1.6026 |                       0.0239 |                                          1 |
|           27 | 2021-11-12        | fixed_by_stage039             | fixed_by_stage039          |                       0.0566 |                      -1.9939 |                                          1 |
|           28 | 2021-11-05        | fixed_by_stage039             | fixed_by_stage039          |                       0.0451 |                      -1.9284 |                                          1 |
|           29 | 2021-11-08        | fixed_by_stage039             | fixed_by_stage039          |                       0.0559 |                      -1.9268 |                                          1 |
|           30 | 2021-11-10        | fixed_by_stage039             | fixed_by_stage039          |                       0.0559 |                      -1.9268 |                                          1 |
|           31 | 2021-11-09        | fixed_by_stage039             | fixed_by_stage039          |                       0.0559 |                      -1.9268 |                                          1 |
|           32 | 2021-11-11        | fixed_by_stage039             | fixed_by_stage039          |                       0.1529 |                      -1.9092 |                                          1 |

## 聚合审计

| variant                                          |   probe_start_count |   negative_probe_start_count |   window_count |   negative_count |   min_return_pct |   to_final_min_return_pct |   end_equity_min |   max_dd_min_pct |   sharpe_median |
|:-------------------------------------------------|--------------------:|-----------------------------:|---------------:|-----------------:|-----------------:|--------------------------:|-----------------:|-----------------:|----------------:|
| stage013_daily_cold_start_engine                 |                  32 |                           32 |          24422 |             7624 |         -36.5967 |                   55.0954 |           232643 |         -45.8976 |          0.8136 |
| stage042_daily_cold_start_stage039_ai_top8_proxy |                  32 |                           32 |          24422 |             7624 |         -36.4775 |                   64.2809 |           246421 |         -46.2637 |          0.853  |

## 输出

- probe_starts：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage042_expanded_daily_cold_start_probe/rebuilt_c9_stage042_expanded_daily_cold_start_probe_probe_starts_stage042_expanded_daily_cold_start_probe_v1.csv`
- summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage042_expanded_daily_cold_start_probe/rebuilt_c9_stage042_expanded_daily_cold_start_probe_summary_stage042_expanded_daily_cold_start_probe_v1.csv`
- aggregate：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage042_expanded_daily_cold_start_probe/rebuilt_c9_stage042_expanded_daily_cold_start_probe_aggregate_stage042_expanded_daily_cold_start_probe_v1.csv`
- curves：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage042_expanded_daily_cold_start_probe/rebuilt_c9_stage042_expanded_daily_cold_start_probe_curves_stage042_expanded_daily_cold_start_probe_v1.csv`
- lot_deltas：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage042_expanded_daily_cold_start_probe/rebuilt_c9_stage042_expanded_daily_cold_start_probe_lot_deltas_stage042_expanded_daily_cold_start_probe_v1.csv`
- decision：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage042_expanded_daily_cold_start_probe/rebuilt_c9_stage042_expanded_daily_cold_start_probe_decision_stage042_expanded_daily_cold_start_probe_v1.json`
- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage042_expanded_daily_cold_start_probe/rebuilt_c9_stage042_expanded_daily_cold_start_probe_report_stage042_expanded_daily_cold_start_probe_v1.md`

## 反思

- 运行前过拟合反思：否。Stage042 是分层扩展探针，不新增交易规则、不按结果改参数；风险在于样本仍来自失败窗口，因此只能用于诊断。
- 运行后过拟合反思：否。本阶段只扩大真实日级冷启动证据；若据此写日期、品种、方向或 topN 过滤才会过拟合。
- 运行前继续价值反思：有。用户目标是任意日级起点，必须从少量探针扩展到更宽样本。
- 运行后继续价值反思：有。扩展日级样本仍有持续左尾，下一步应转账户外层/真正外生源，或扩大全量日级网格确认分布。
