# Stage105 开盘穿越执行压力审计

> 说明：本记录为 Stage105 v1 初版，已被 `20260705_2112_stage105_open_penetration_execution_stress_audit.md` 的 v2 `stage105_open_penetration_execution_stress_audit_v2_reviewed_sorted_unique` 覆盖。后续引用请以 v2 为准。

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-05 21:08 CST
- 工作区：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读执行压力；不改策略、不跑 true engine
- 是否重要突破：否
- 是否触发A/B：否，本阶段未产生策略候选

## 外部调研与判断

- 参考资料：Charles Schwab stop/gap、Backtrader order execution、CFTC futures stop orders、backtesting.py GitHub discussion。
- 我的判断：开盘穿越确实是 stop-market 执行风险，但是否能作为策略优化，必须看 material + breadth；不能因为少数事故事件就调止损倍数。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage105_open_penetration_execution_stress_audit.py`
- 修改脚本：无正式交易入口修改。
- 删除脚本：无。
- 新增参数：只读审计闸门：行级额外压力 `250,000`、去重 worst 额外压力 `150,000`、最大单事件占比 `35%`。
- 修改参数：无正式策略参数。
- 删除参数：无。

## 回测/审计参数

- 输入：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage104_intraday_stop_minute_path_slippage_audit/rebuilt_c9_v2_stage104_intraday_stop_minute_path_slippage_audit_event_panel_stage104_intraday_stop_minute_path_slippage_audit_v2_reviewed_unique_gate.csv.gz`
- Stage104 decision：`stage104_intraday_stop_actual_exit_no_material_adverse_slippage_candidate`
- true engine：未运行。
- 订单 API：`0`
- CTP：未连接。

## 结果摘要

- 决策：`stage105_open_penetration_execution_stress_concentrated_warning_no_rule_candidate`
- 样本行数：`81`
- 去重物理事件数：`20`
- 开盘穿越行数：`21`
- 开盘穿越去重物理事件数：`5`
- 开盘穿越去重品种数：`5`
- 行级 stress delta：`-252,356.60`
- 行级 stress loss abs：`253,040.00`
- 去重 first stress delta：`-104,443.20`
- 去重 first stress loss abs：`104,805.00`
- 去重 worst stress delta：`-104,483.40`
- 去重 worst stress loss abs：`104,805.00`
- 最大单事件 loss share：`0.5217`
- row_material：`True`
- unique_material：`False`
- broad_unique：`False`
- 候选规则数：`0`

## By Start

| requested_start_month   |   rows |   unique_physical_events |   open_penetration_rows |   open_penetration_unique_events |   stress_delta_pnl_sum |   stress_loss_abs_sum |   stress_gain_sum |   unique_first_stress_delta_sum |   unique_first_stress_loss_abs_sum |   unique_first_stress_gain_sum |   realized_pnl_sum |   stress_realized_pnl_sum |   stress_to_actual_pnl_abs_ratio |
|:------------------------|-------:|-------------------------:|------------------------:|---------------------------------:|-----------------------:|----------------------:|------------------:|--------------------------------:|-----------------------------------:|-------------------------------:|-------------------:|--------------------------:|---------------------------------:|
| 2020-01                 |     20 |                       20 |                       5 |                                5 |              -104443   |                104805 |             361.8 |                       -104443   |                             104805 |                          361.8 |          -404718   |                 -509161   |                         0.258958 |
| 2020-07                 |     18 |                       18 |                       5 |                                5 |               -87418.4 |                 87740 |             321.6 |                        -87418.4 |                              87740 |                          321.6 |          -331903   |                 -419321   |                         0.264355 |
| 2021-01                 |     12 |                       12 |                       3 |                                3 |               -40880   |                 40880 |               0   |                        -40880   |                              40880 |                            0   |          -150153   |                 -191033   |                         0.272255 |
| 2021-07                 |      7 |                        7 |                       2 |                                2 |                -7790   |                  7790 |               0   |                         -7790   |                               7790 |                            0   |           -29270.1 |                  -37060.1 |                         0.266142 |
| 2022-01                 |      4 |                        4 |                       2 |                                2 |                -3725   |                  3725 |               0   |                         -3725   |                               3725 |                            0   |           -12256   |                  -15981   |                         0.303933 |
| 2022-07                 |      4 |                        4 |                       1 |                                1 |                -2025   |                  2025 |               0   |                         -2025   |                               2025 |                            0   |           -18431.3 |                  -20456.3 |                         0.109867 |
| 2023-01                 |      3 |                        3 |                       1 |                                1 |                -2025   |                  2025 |               0   |                         -2025   |                               2025 |                            0   |           -11325.6 |                  -13350.6 |                         0.178798 |
| 2023-07                 |      3 |                        3 |                       1 |                                1 |                -2025   |                  2025 |               0   |                         -2025   |                               2025 |                            0   |           -13759.8 |                  -15784.8 |                         0.147168 |
| 2024-01                 |      3 |                        3 |                       1 |                                1 |                -2025   |                  2025 |               0   |                         -2025   |                               2025 |                            0   |           -10656   |                  -12681   |                         0.190034 |
| 2024-07                 |      2 |                        2 |                       0 |                                0 |                    0   |                     0 |               0   |                             0   |                                  0 |                            0   |            -6877.2 |                   -6877.2 |                         0        |
| 2025-01                 |      2 |                        2 |                       0 |                                0 |                    0   |                     0 |               0   |                             0   |                                  0 |                            0   |            -6207.6 |                   -6207.6 |                         0        |
| 2025-07                 |      2 |                        2 |                       0 |                                0 |                    0   |                     0 |               0   |                             0   |                                  0 |                            0   |            -6207.6 |                   -6207.6 |                         0        |
| 2026-01                 |      1 |                        1 |                       0 |                                0 |                    0   |                     0 |               0   |                             0   |                                  0 |                            0   |            -2678.4 |                   -2678.4 |                         0        |

## By Exit Reason

| exit_reason                             |   rows |   unique_physical_events |   open_penetration_rows |   open_penetration_unique_events |   stress_delta_pnl_sum |   stress_loss_abs_sum |   stress_gain_sum |   unique_first_stress_delta_sum |   unique_first_stress_loss_abs_sum |   unique_first_stress_gain_sum |   realized_pnl_sum |   stress_realized_pnl_sum |   stress_to_actual_pnl_abs_ratio |
|:----------------------------------------|-------:|-------------------------:|------------------------:|---------------------------------:|-----------------------:|----------------------:|------------------:|--------------------------------:|-----------------------------------:|-------------------------------:|-------------------:|--------------------------:|---------------------------------:|
| stage847_intraday_05r_stop_no_reentry   |     50 |                       11 |                      14 |                                3 |              -159540   |                159540 |               0   |                        -66045   |                              66045 |                            0   |            -698047 |                   -857587 |                         0.228552 |
| stage847_intraday_retry_failed_05r_stop |     22 |                        7 |                       7 |                                2 |               -92816.6 |                 93500 |             683.4 |                        -38398.2 |                              38760 |                          361.8 |            -136977 |                   -229793 |                         0.682598 |
| stage827_intraday_c2_1r_stop            |      9 |                        2 |                       0 |                                0 |                    0   |                     0 |               0   |                             0   |                                  0 |                            0   |            -169420 |                   -169420 |                         0        |

## Top Physical Events

| physical_event_key                                                                                     | vt_symbol   | direction   | entry_date          | exit_date           | exit_reason                             |   row_count |   start_count |   open_penetration_rows | has_open_penetration   | first_representative_start   |   first_representative_stress_delta | worst_representative_start   |   worst_representative_stress_delta |   row_stress_delta_sum |   row_stress_loss_abs_sum |   row_stress_gain_sum |   realized_pnl_sum |   stress_realized_pnl_sum |
|:-------------------------------------------------------------------------------------------------------|:------------|:------------|:--------------------|:--------------------|:----------------------------------------|------------:|--------------:|------------------------:|:-----------------------|:-----------------------------|------------------------------------:|:-----------------------------|------------------------------------:|-----------------------:|--------------------------:|----------------------:|-------------------:|--------------------------:|
| cu2503.SHFE|2025-01-20|2025-01-20|long|76340.0|76205.0|stage847_intraday_05r_stop_no_reentry           | cu2503.SHFE | long        | 2025-01-20 00:00:00 | 2025-01-20 00:00:00 | stage847_intraday_05r_stop_no_reentry   |           9 |             9 |                       9 | True                   | 2020-01                      |                            -54675   | 2020-01                      |                            -54675   |              -133650   |                    133650 |                   0   |           -44550   |                 -178200   |
| fu2205.SHFE|2022-03-25|2022-03-25|long|4269.0|4237.0|stage847_intraday_retry_failed_05r_stop           | fu2205.SHFE | long        | 2022-03-25 00:00:00 | 2022-03-25 00:00:00 | stage847_intraday_retry_failed_05r_stop |           5 |             5 |                       5 | True                   | 2020-01                      |                            -38760   | 2020-01                      |                            -38760   |               -93500   |                     93500 |                   0   |           -88000   |                 -181500   |
| hc2110.SHFE|2021-06-11|2021-06-11|short|5455.0|5485.5|stage847_intraday_05r_stop_no_reentry            | hc2110.SHFE | short       | 2021-06-11 00:00:00 | 2021-06-11 00:00:00 | stage847_intraday_05r_stop_no_reentry   |           3 |             3 |                       3 | True                   | 2020-01                      |                            -11160   | 2020-01                      |                            -11160   |               -25575   |                     25575 |                   0   |           -16775   |                  -42350   |
| jm2009.DCE|2020-07-10|2020-07-10|long|1218.0|1207.25|stage847_intraday_05r_stop_no_reentry             | jm2009.DCE  | long        | 2020-07-10 00:00:00 | 2020-07-10 00:00:00 | stage847_intraday_05r_stop_no_reentry   |           2 |             2 |                       2 | True                   | 2020-01                      |                              -210   | 2020-01                      |                              -210   |                 -315   |                       315 |                   0   |            -1935   |                   -2250   |
| SM109.CZCE|2021-07-30|2021-07-30|long|7980.0|7902.0|stage827_intraday_c2_1r_stop                       | SM109.CZCE  | long        | 2021-07-30 00:00:00 | 2021-07-30 00:00:00 | stage827_intraday_c2_1r_stop            |           4 |             4 |                       0 | False                  | 2020-01                      |                                 0   | 2020-01                      |                                 0   |                    0   |                         0 |                   0   |           -61620   |                  -61620   |
| rb2005.SHFE|2020-01-09|2020-01-09|long|3617.0|3594.0|stage847_intraday_05r_stop_no_reentry             | rb2005.SHFE | long        | 2020-01-09 00:00:00 | 2020-01-09 00:00:00 | stage847_intraday_05r_stop_no_reentry   |           1 |             1 |                       0 | False                  | 2020-01                      |                                 0   | 2020-01                      |                                 0   |                    0   |                         0 |                   0   |            -2300   |                   -2300   |
| lh2109.DCE|2021-04-12|2021-04-12|short|26830.0|26950.0|stage847_intraday_retry_failed_05r_stop         | lh2109.DCE  | short       | 2021-04-12 00:00:00 | 2021-04-12 00:00:00 | stage847_intraday_retry_failed_05r_stop |           2 |             2 |                       0 | False                  | 2020-01                      |                                 0   | 2020-01                      |                                 0   |                    0   |                         0 |                   0   |            -3840   |                   -3840   |
| cu2212.SHFE|2022-10-28|2022-10-28|long|63630.0|63140.0|stage827_intraday_c2_1r_stop                    | cu2212.SHFE | long        | 2022-10-28 00:00:00 | 2022-10-28 00:00:00 | stage827_intraday_c2_1r_stop            |           5 |             5 |                       0 | False                  | 2020-01                      |                                 0   | 2020-01                      |                                 0   |                    0   |                         0 |                   0   |          -107800   |                 -107800   |
| cu2012.SHFE|2020-11-17|2020-11-17|long|53520.0|53043.6|stage847_intraday_05r_stop_no_reentry           | cu2012.SHFE | long        | 2020-11-17 00:00:00 | 2020-11-17 00:00:00 | stage847_intraday_05r_stop_no_reentry   |           2 |             2 |                       0 | False                  | 2020-01                      |                                 0   | 2020-01                      |                                 0   |                    0   |                         0 |                   0   |            -4764   |                   -4764   |
| sp2105.SHFE|2021-02-22|2021-02-22|long|6972.0|6902.28|stage847_intraday_retry_failed_05r_stop          | sp2105.SHFE | long        | 2021-02-22 00:00:00 | 2021-02-22 00:00:00 | stage847_intraday_retry_failed_05r_stop |           3 |             3 |                       0 | False                  | 2020-01                      |                                 0   | 2020-01                      |                                 0   |                    0   |                         0 |                   0   |            -8366.4 |                   -8366.4 |
| SM109.CZCE|2021-06-02|2021-06-02|long|7736.0|7720.0|stage847_intraday_retry_failed_05r_stop            | SM109.CZCE  | long        | 2021-06-02 00:00:00 | 2021-06-02 00:00:00 | stage847_intraday_retry_failed_05r_stop |           3 |             3 |                       0 | False                  | 2020-01                      |                                 0   | 2020-01                      |                                 0   |                    0   |                         0 |                   0   |            -8160   |                   -8160   |
| SM101.CZCE|2020-12-17|2020-12-17|long|6624.0|6567.0|stage847_intraday_05r_stop_no_reentry              | SM101.CZCE  | long        | 2020-12-17 00:00:00 | 2020-12-17 00:00:00 | stage847_intraday_05r_stop_no_reentry   |           2 |             2 |                       0 | False                  | 2020-01                      |                                 0   | 2020-01                      |                                 0   |                    0   |                         0 |                   0   |           -10545   |                  -10545   |
| SH605.CZCE|2026-03-03|2026-03-03|short|2079.0|2101.3199999999997|stage847_intraday_05r_stop_no_reentry | SH605.CZCE  | short       | 2026-03-03 00:00:00 | 2026-03-03 00:00:00 | stage847_intraday_05r_stop_no_reentry   |          13 |            13 |                       0 | False                  | 2020-01                      |                                 0   | 2020-01                      |                                 0   |                    0   |                         0 |                   0   |          -289267   |                 -289267   |
| SH601.CZCE|2025-08-25|2025-08-25|long|2745.0|2715.59|stage847_intraday_05r_stop_no_reentry             | SH601.CZCE  | long        | 2025-08-25 00:00:00 | 2025-08-25 00:00:00 | stage847_intraday_05r_stop_no_reentry   |          12 |            12 |                       0 | False                  | 2020-01                      |                                 0   | 2020-01                      |                                 0   |                    0   |                         0 |                   0   |          -310570   |                 -310570   |
| SA205.CZCE|2022-01-24|2022-01-24|long|2717.0|2687.38|stage847_intraday_05r_stop_no_reentry             | SA205.CZCE  | long        | 2022-01-24 00:00:00 | 2022-01-24 00:00:00 | stage847_intraday_05r_stop_no_reentry   |           3 |             3 |                       0 | False                  | 2020-01                      |                                 0   | 2020-01                      |                                 0   |                    0   |                         0 |                   0   |           -10663.2 |                  -10663.2 |
| SA105.CZCE|2021-03-18|2021-03-18|long|2000.0|1978.53|stage847_intraday_retry_failed_05r_stop           | SA105.CZCE  | long        | 2021-03-18 00:00:00 | 2021-03-18 00:00:00 | stage847_intraday_retry_failed_05r_stop |           3 |             3 |                       0 | False                  | 2020-01                      |                                 0   | 2020-01                      |                                 0   |                    0   |                         0 |                   0   |            -9446.8 |                   -9446.8 |
| OI201.CZCE|2021-09-07|2021-09-07|long|10894.0|10852.0|stage847_intraday_retry_failed_05r_stop          | OI201.CZCE  | long        | 2021-09-07 00:00:00 | 2021-09-07 00:00:00 | stage847_intraday_retry_failed_05r_stop |           4 |             4 |                       0 | False                  | 2020-01                      |                                 0   | 2020-01                      |                                 0   |                    0   |                         0 |                   0   |           -11340   |                  -11340   |
| MA101.CZCE|2020-12-14|2020-12-14|long|2422.0|2404.15|stage847_intraday_05r_stop_no_reentry             | MA101.CZCE  | long        | 2020-12-14 00:00:00 | 2020-12-14 00:00:00 | stage847_intraday_05r_stop_no_reentry   |           2 |             2 |                       0 | False                  | 2020-01                      |                                 0   | 2020-01                      |                                 0   |                    0   |                         0 |                   0   |            -4998   |                   -4998   |
| sp2005.SHFE|2020-01-14|2020-01-14|long|4684.0|4663.0|stage847_intraday_05r_stop_no_reentry             | sp2005.SHFE | long        | 2020-01-14 00:00:00 | 2020-01-14 00:00:00 | stage847_intraday_05r_stop_no_reentry   |           1 |             1 |                       0 | False                  | 2020-01                      |                                 0   | 2020-01                      |                                 0   |                    0   |                         0 |                   0   |            -1680   |                   -1680   |
| FG101.CZCE|2020-08-12|2020-08-12|long|1860.0|1836.99|stage847_intraday_retry_failed_05r_stop           | FG101.CZCE  | long        | 2020-08-12 00:00:00 | 2020-08-12 00:00:00 | stage847_intraday_retry_failed_05r_stop |           2 |             2 |                       2 | True                   | 2020-01                      |                               361.8 | 2020-07                      |                               321.6 |                  683.4 |                         0 |                 683.4 |            -7823.4 |                   -7140   |

## 标准回测指标

- 期末权益：不适用，本阶段只读执行压力未重跑策略。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用；本阶段统计 stop-market 开盘穿越代理压力。
- 总交易次数：不适用。
- 胜率：不适用。

## 决策

```json
{
  "stage": "Stage105",
  "model_tag": "stage105_open_penetration_execution_stress_audit_v1",
  "line_id": "futures_trend_rebuilt_c9_15w_v2_optimization",
  "generated_at": "2026-07-05T21:08:54",
  "decision": "stage105_open_penetration_execution_stress_concentrated_warning_no_rule_candidate",
  "candidate_rule_count": 0,
  "best_candidate": "",
  "stage104_decision": "stage104_intraday_stop_actual_exit_no_material_adverse_slippage_candidate",
  "stage104_open_penetration_warning": true,
  "rows": 81,
  "unique_physical_events": 20,
  "open_penetration_rows": 21,
  "open_penetration_unique_events": 5,
  "open_penetration_unique_symbols": 5,
  "row_stress_delta_pnl_sum": -252356.6,
  "row_stress_loss_abs_sum": 253040.0,
  "row_stress_gain_sum": 683.3999999999969,
  "unique_first_stress_delta_sum": -104443.2,
  "unique_first_stress_loss_abs_sum": 104805.0,
  "unique_worst_stress_delta_sum": -104483.4,
  "unique_worst_stress_loss_abs_sum": 104805.0,
  "top_unique_loss_share": 0.5216831258050666,
  "row_material": true,
  "unique_material": false,
  "broad_unique": false,
  "concentrated_warning": true,
  "promote_to_proxy": false,
  "promote_to_true_engine": false,
  "strategy_changed": false,
  "true_engine_run": false,
  "order_api_calls": 0,
  "ctp_connected": false,
  "next_step": "不做开盘穿越规则优化；仅把该压力作为 execution stress caveat。继续转向非日内止损的账户层暴露、持仓趋势衰退或组合相关性。",
  "overfit_after": "否。固定 open-penetration 代理和预声明宽样本闸门，结果不够宽时停止。",
  "continue_after": "有但需换主问题",
  "continue_reason": "开盘穿越压力存在但集中于少数物理事件，直接做规则容易过拟合。"
}
```

## 后续规划和 TODO

- 不做开盘穿越规则优化；仅把该压力作为 execution stress caveat。继续转向非日内止损的账户层暴露、持仓趋势衰退或组合相关性。

## 过拟合反思

- 运行前：否，固定 open penetration 代理，不扫阈值/倍数/品种/方向。
- 运行后：否。固定 open-penetration 代理和预声明宽样本闸门，结果不够宽时停止。

## 继续价值反思

- 运行前：有，确认执行压力是否值得进入 proxy stress。
- 运行后：有但需换主问题。开盘穿越压力存在但集中于少数物理事件，直接做规则容易过拟合。

## 输出

- 报告：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage105_open_penetration_execution_stress_audit/rebuilt_c9_v2_stage105_open_penetration_execution_stress_audit_report_stage105_open_penetration_execution_stress_audit_v1.md`
- stress_panel：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage105_open_penetration_execution_stress_audit/rebuilt_c9_v2_stage105_open_penetration_execution_stress_audit_stress_panel_stage105_open_penetration_execution_stress_audit_v1.csv.gz`
- physical_event_summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage105_open_penetration_execution_stress_audit/rebuilt_c9_v2_stage105_open_penetration_execution_stress_audit_physical_event_summary_stage105_open_penetration_execution_stress_audit_v1.csv`
- by_start：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage105_open_penetration_execution_stress_audit/rebuilt_c9_v2_stage105_open_penetration_execution_stress_audit_by_start_stage105_open_penetration_execution_stress_audit_v1.csv`
- by_exit_reason：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage105_open_penetration_execution_stress_audit/rebuilt_c9_v2_stage105_open_penetration_execution_stress_audit_by_exit_reason_stage105_open_penetration_execution_stress_audit_v1.csv`
- by_symbol：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage105_open_penetration_execution_stress_audit/rebuilt_c9_v2_stage105_open_penetration_execution_stress_audit_by_symbol_stage105_open_penetration_execution_stress_audit_v1.csv`
- input_audit：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage105_open_penetration_execution_stress_audit/rebuilt_c9_v2_stage105_open_penetration_execution_stress_audit_input_audit_stage105_open_penetration_execution_stress_audit_v1.csv`
