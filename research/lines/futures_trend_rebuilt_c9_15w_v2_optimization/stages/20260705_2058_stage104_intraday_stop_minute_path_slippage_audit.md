# Stage104 日内止损分钟路径/滑点法证

> 说明：本记录为 Stage104 v1 初版，已被 `20260705_2105_stage104_intraday_stop_minute_path_slippage_audit.md` 的 v2 `stage104_intraday_stop_minute_path_slippage_audit_v2_reviewed_unique_gate` 覆盖。后续引用请以 v2 为准。

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-05 20:58 CST
- 工作区：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读执行法证；不改策略、不跑 true engine
- 是否重要突破：否
- 是否触发A/B：否，本阶段没有可合入策略候选

## 外部调研与判断

- 参考资料：Backtrader order execution、Backtrader slippage、CFTC futures stop orders、QuantStart transaction cost/slippage。
- 我的判断：止损触发与成交价格必须分开复核；如果实际退出价没有系统性偏离 planned stop，继续围绕日内止损调参会过拟合。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage104_intraday_stop_minute_path_slippage_audit.py`
- 修改脚本：无正式交易入口修改。
- 删除脚本：无。
- 新增参数：只读审计参数 `Stage847=0.5R`、`Stage827=1.0R`、coverage/hit 闸门 `80%`、material adverse slippage `200,000`。
- 修改参数：无正式策略参数。
- 删除参数：无。

## 回测/审计参数

- 样本来源：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage094_stage167_closed_lot_entry_state_audit/rebuilt_c9_v2_stage094_stage167_closed_lot_entry_state_audit_closed_lots_stage094_stage167_closed_lot_entry_state_audit_v1.csv.gz`
- 分钟源目录：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures`
- 止损退出族：`stage847_intraday_05r_stop_no_reentry, stage847_intraday_retry_failed_05r_stop, stage827_intraday_c2_1r_stop`
- true engine：未运行。
- 订单 API：`0`
- CTP：未连接。

## 结果摘要

- 决策：`stage104_intraday_stop_no_material_adverse_slippage_candidate`
- 样本行数：`81`
- 去重物理事件数：`20`
- 分钟覆盖率：`0.9506`
- planned stop 命中率：`0.9506`
- 实际退出价等于 planned stop 比率：`0.0741`
- 实际不利滑点金额：`177,820.00`
- 去重物理事件实际不利滑点金额：`73,790.00`
- 首根命中 bar 开盘穿越金额：`293,211.60`
- 分钟最差穿越仍解释不了实际退出价的行数：`0`
- 候选规则数：`0`
- 最佳候选：`无`

## By Exit Reason

| exit_reason                             |   rows |   unique_physical_events |   start_count |   symbol_count |   realized_pnl_sum |   realized_pnl_mean |   coverage_rate |   planned_stop_hit_rate |   missing_expected_hit_rows |   actual_exact_stop_rate |   adverse_slippage_cash_sum |   adverse_slippage_cash_mean |   adverse_slippage_cash_max |   minute_day_worst_beyond_cash_sum |   first_hit_open_beyond_rate |   first_hit_open_adverse_cash_sum |   actual_exit_worse_than_day_worst_rows |   positive_start_count |   negative_start_count |   unique_event_adverse_slippage_cash_sum |   unique_event_worst_beyond_cash_sum |
|:----------------------------------------|-------:|-------------------------:|--------------:|---------------:|-------------------:|--------------------:|----------------:|------------------------:|----------------------------:|-------------------------:|----------------------------:|-----------------------------:|----------------------------:|-----------------------------------:|-----------------------------:|----------------------------------:|----------------------------------------:|-----------------------:|-----------------------:|-----------------------------------------:|-------------------------------------:|
| stage847_intraday_05r_stop_no_reentry   |     50 |                       11 |            13 |             11 |            -698047 |           -13960.9  |        1        |                1        |                           0 |                 0.06     |                       45980 |                       919.6  |                        8040 |                        1.35018e+06 |                     0.28     |                            124615 |                                       0 |                      0 |                     13 |                                    18300 |                               541589 |
| stage827_intraday_c2_1r_stop            |      9 |                        2 |             5 |              2 |            -169420 |           -18824.4  |        1        |                1        |                           0 |                 0        |                       55400 |                      6155.56 |                       17100 |                   208180           |                     0        |                                 0 |                                       0 |                      0 |                      5 |                                    23600 |                                88250 |
| stage847_intraday_retry_failed_05r_stop |     22 |                        7 |             5 |              7 |            -136977 |            -6226.21 |        0.818182 |                0.818182 |                           0 |                 0.136364 |                       76440 |                      3474.55 |                       30780 |                   383323           |                     0.318182 |                            168597 |                                       0 |                      0 |                      5 |                                    31890 |                               162708 |

## By Start

| requested_start_month   |   rows |   unique_physical_events |   start_count |   symbol_count |   realized_pnl_sum |   realized_pnl_mean |   coverage_rate |   planned_stop_hit_rate |   missing_expected_hit_rows |   actual_exact_stop_rate |   adverse_slippage_cash_sum |   adverse_slippage_cash_mean |   adverse_slippage_cash_max |   minute_day_worst_beyond_cash_sum |   first_hit_open_beyond_rate |   first_hit_open_adverse_cash_sum |   actual_exit_worse_than_day_worst_rows |   positive_start_count |   negative_start_count |   unique_event_adverse_slippage_cash_sum |   unique_event_worst_beyond_cash_sum |
|:------------------------|-------:|-------------------------:|--------------:|---------------:|-------------------:|--------------------:|----------------:|------------------------:|----------------------------:|-------------------------:|----------------------------:|-----------------------------:|----------------------------:|-----------------------------------:|-----------------------------:|----------------------------------:|----------------------------------------:|-----------------------:|-----------------------:|-----------------------------------------:|-------------------------------------:|
| 2020-01                 |     20 |                       20 |             1 |             19 |          -404718   |           -20235.9  |        0.95     |                0.95     |                           0 |                0.15      |                       73790 |                      3689.5  |                       30780 |                           792547   |                     0.25     |                            121693 |                                       0 |                      0 |                      1 |                                    73790 |                             792547   |
| 2020-07                 |     18 |                       18 |             1 |             17 |          -331903   |           -18439    |        0.944444 |                0.944444 |                           0 |                0.111111  |                       62330 |                      3462.78 |                       26460 |                           653707   |                     0.277778 |                            102863 |                                       0 |                      0 |                      1 |                                    62330 |                             653707   |
| 2021-01                 |     12 |                       12 |             1 |             11 |          -150153   |           -12512.8  |        0.916667 |                0.916667 |                           0 |                0.0833333 |                       28060 |                      2338.33 |                       12690 |                           287947   |                     0.25     |                             48220 |                                       0 |                      0 |                      1 |                                    28060 |                             287947   |
| 2021-07                 |      7 |                        7 |             1 |              7 |           -29270.1 |            -4181.44 |        0.857143 |                0.857143 |                           0 |                0         |                        5915 |                       845    |                        2970 |                            55604.9 |                     0.285714 |                              9760 |                                       0 |                      0 |                      1 |                                     5915 |                              55604.9 |
| 2022-01                 |      4 |                        4 |             1 |              4 |           -12256   |            -3064    |        1        |                1        |                           0 |                0         |                        2025 |                       506.25 |                        1350 |                            24769   |                     0.5      |                              4575 |                                       0 |                      0 |                      1 |                                     2025 |                              24769   |
| 2022-07                 |      4 |                        4 |             1 |              4 |           -18431.3 |            -4607.82 |        1        |                1        |                           0 |                0         |                        1935 |                       483.75 |                         900 |                            29973.7 |                     0.25     |                              1525 |                                       0 |                      0 |                      1 |                                     1935 |                              29973.7 |
| 2023-01                 |      3 |                        3 |             1 |              3 |           -11325.6 |            -3775.2  |        1        |                1        |                           0 |                0         |                         720 |                       240    |                         360 |                            20884.4 |                     0.333333 |                              1525 |                                       0 |                      0 |                      1 |                                      720 |                              20884.4 |
| 2023-07                 |      3 |                        3 |             1 |              3 |           -13759.8 |            -4586.6  |        1        |                1        |                           0 |                0         |                         885 |                       295    |                         480 |                            23145.2 |                     0.333333 |                              1525 |                                       0 |                      0 |                      1 |                                      885 |                              23145.2 |
| 2024-01                 |      3 |                        3 |             1 |              3 |           -10656   |            -3552    |        1        |                1        |                           0 |                0         |                         675 |                       225    |                         360 |                            19019   |                     0.333333 |                              1525 |                                       0 |                      0 |                      1 |                                      675 |                              19019   |
| 2024-07                 |      2 |                        2 |             1 |              2 |            -6877.2 |            -3438.6  |        1        |                1        |                           0 |                0         |                         465 |                       232.5  |                         240 |                            10117.8 |                     0        |                                 0 |                                       0 |                      0 |                      1 |                                      465 |                              10117.8 |
| 2025-01                 |      2 |                        2 |             1 |              2 |            -6207.6 |            -3103.8  |        1        |                1        |                           0 |                0         |                         420 |                       210    |                         240 |                             8252.4 |                     0        |                                 0 |                                       0 |                      0 |                      1 |                                      420 |                               8252.4 |
| 2025-07                 |      2 |                        2 |             1 |              2 |            -6207.6 |            -3103.8  |        1        |                1        |                           0 |                0         |                         420 |                       210    |                         240 |                             8252.4 |                     0        |                                 0 |                                       0 |                      0 |                      1 |                                      420 |                               8252.4 |
| 2026-01                 |      1 |                        1 |             1 |              1 |            -2678.4 |            -2678.4  |        1        |                1        |                           0 |                0         |                         180 |                       180    |                         180 |                             7461.6 |                     0        |                                 0 |                                       0 |                      0 |                      1 |                                      180 |                               7461.6 |

## By Symbol

| vt_symbol   |   rows |   unique_physical_events |   start_count |   symbol_count |   realized_pnl_sum |   realized_pnl_mean |   coverage_rate |   planned_stop_hit_rate |   missing_expected_hit_rows |   actual_exact_stop_rate |   adverse_slippage_cash_sum |   adverse_slippage_cash_mean |   adverse_slippage_cash_max |   minute_day_worst_beyond_cash_sum |   first_hit_open_beyond_rate |   first_hit_open_adverse_cash_sum |   actual_exit_worse_than_day_worst_rows |   positive_start_count |   negative_start_count |   unique_event_adverse_slippage_cash_sum |   unique_event_worst_beyond_cash_sum |
|:------------|-------:|-------------------------:|--------------:|---------------:|-------------------:|--------------------:|----------------:|------------------------:|----------------------------:|-------------------------:|----------------------------:|-----------------------------:|----------------------------:|-----------------------------------:|-----------------------------:|----------------------------------:|----------------------------------------:|-----------------------:|-----------------------:|-----------------------------------------:|-------------------------------------:|
| fu2205.SHFE |      5 |                        1 |             5 |              1 |           -88000   |           -17600    |               1 |                       1 |                           0 |                        0 |                       74250 |                     14850    |                       30780 |                           316250   |                            1 |                          167750   |                                       0 |                      0 |                      5 |                                    30780 |                             131100   |
| cu2212.SHFE |      5 |                        1 |             5 |              1 |          -107800   |           -21560    |               1 |                       1 |                           0 |                        0 |                       39600 |                      7920    |                       17100 |                           127600   |                            0 |                               0   |                                       0 |                      0 |                      5 |                                    17100 |                              55100   |
| SH601.CZCE  |     12 |                        1 |            12 |              1 |          -310570   |           -25880.8  |               1 |                       1 |                           0 |                        0 |                       21120 |                      1760    |                        8040 |                            69590.4 |                            0 |                               0   |                                       0 |                      0 |                     12 |                                     8040 |                              26491.8 |
| SH605.CZCE  |     13 |                        1 |            13 |              1 |          -289267   |           -22251.3  |               1 |                       1 |                           0 |                        0 |                       19440 |                      1495.38 |                        7380 |                           805853   |                            0 |                               0   |                                       0 |                      0 |                     13 |                                     7380 |                             305926   |
| SM109.CZCE  |      7 |                        2 |             4 |              1 |           -69780   |            -9968.57 |               1 |                       1 |                           0 |                        0 |                       15800 |                      2257.14 |                        6500 |                           109140   |                            0 |                               0   |                                       0 |                      0 |                      4 |                                     6500 |                              45470   |
| SM101.CZCE  |      2 |                        1 |             2 |              1 |           -10545   |            -5272.5  |               1 |                       1 |                           0 |                        0 |                        4440 |                      2220    |                        2400 |                            53835   |                            0 |                               0   |                                       0 |                      0 |                      2 |                                     2400 |                              29100   |
| FG101.CZCE  |      2 |                        1 |             2 |              1 |            -7823.4 |            -3911.7  |               1 |                       1 |                           0 |                        0 |                        1530 |                       765    |                         810 |                            20226.6 |                            1 |                             846.6 |                                       0 |                      0 |                      2 |                                      810 |                              10708.2 |
| SA205.CZCE  |      3 |                        1 |             3 |              1 |           -10663.2 |            -3554.4  |               1 |                       1 |                           0 |                        0 |                         900 |                       300    |                         400 |                            17236.8 |                            0 |                               0   |                                       0 |                      0 |                      3 |                                      400 |                               7660.8 |
| SA105.CZCE  |      3 |                        1 |             3 |              1 |            -9446.8 |            -3148.93 |               1 |                       1 |                           0 |                        0 |                         660 |                       220    |                         300 |                             5293.2 |                            0 |                               0   |                                       0 |                      0 |                      3 |                                      300 |                               2406   |
| sp2005.SHFE |      1 |                        1 |             1 |              1 |            -1680   |            -1680    |               1 |                       1 |                           0 |                        0 |                          80 |                        80    |                          80 |                              960   |                            0 |                               0   |                                       0 |                      0 |                      1 |                                       80 |                                960   |
| hc2110.SHFE |      3 |                        1 |             3 |              1 |           -16775   |            -5591.67 |               1 |                       1 |                           0 |                        0 |                           0 |                         0    |                           0 |                            66550   |                            1 |                           23650   |                                       0 |                      0 |                      3 |                                        0 |                              29040   |
| OI201.CZCE  |      4 |                        1 |             4 |              1 |           -11340   |            -2835    |               0 |                       0 |                           0 |                        0 |                           0 |                         0    |                           0 |                                0   |                            0 |                               0   |                                       0 |                      0 |                      4 |                                        0 |                                  0   |
| cu2503.SHFE |      9 |                        1 |             9 |              1 |           -44550   |            -4950    |               1 |                       1 |                           0 |                        0 |                           0 |                         0    |                           0 |                           315150   |                            1 |                          100650   |                                       0 |                      0 |                      9 |                                        0 |                             128925   |
| sp2105.SHFE |      3 |                        1 |             3 |              1 |            -8366.4 |            -2788.8  |               1 |                       1 |                           0 |                        1 |                           0 |                         0    |                          -0 |                             3873.6 |                            0 |                               0   |                                       0 |                      0 |                      3 |                                        0 |                               1614   |
| MA101.CZCE  |      2 |                        1 |             2 |              1 |            -4998   |            -2499    |               1 |                       1 |                           0 |                        0 |                           0 |                         0    |                           0 |                            11662   |                            0 |                               0   |                                       0 |                      0 |                      2 |                                        0 |                               6247.5 |
| cu2012.SHFE |      2 |                        1 |             2 |              1 |            -4764   |            -2382    |               1 |                       1 |                           0 |                        0 |                           0 |                         0    |                           0 |                             2736   |                            0 |                               0   |                                       0 |                      0 |                      2 |                                        0 |                               1368   |
| lh2109.DCE  |      2 |                        1 |             2 |              1 |            -3840   |            -1920    |               1 |                       1 |                           0 |                        0 |                           0 |                         0    |                           0 |                             9120   |                            0 |                               0   |                                       0 |                      0 |                      2 |                                        0 |                               4560   |
| rb2005.SHFE |      1 |                        1 |             1 |              1 |            -2300   |            -2300    |               1 |                       1 |                           0 |                        1 |                           0 |                         0    |                          -0 |                             4400   |                            0 |                               0   |                                       0 |                      0 |                      1 |                                        0 |                               4400   |
| jm2009.DCE  |      2 |                        1 |             2 |              1 |            -1935   |             -967.5  |               1 |                       1 |                           0 |                        1 |                           0 |                         0    |                          -0 |                             2205   |                            1 |                             315   |                                       0 |                      0 |                      2 |                                        0 |                               1470   |

## 标准回测指标

- 期末权益：不适用，本阶段只读法证未重跑策略。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用；本阶段统计 planned stop 相对实际退出价的执行偏移。
- 总交易次数：不适用。
- 胜率：不适用。

## 决策

```json
{
  "stage": "Stage104",
  "model_tag": "stage104_intraday_stop_minute_path_slippage_audit_v1",
  "line_id": "futures_trend_rebuilt_c9_15w_v2_optimization",
  "generated_at": "2026-07-05T20:58:09",
  "decision": "stage104_intraday_stop_no_material_adverse_slippage_candidate",
  "candidate_rule_count": 0,
  "best_candidate": "",
  "rows": 81,
  "unique_physical_events": 20,
  "exit_reasons": [
    "stage827_intraday_c2_1r_stop",
    "stage847_intraday_05r_stop_no_reentry",
    "stage847_intraday_retry_failed_05r_stop"
  ],
  "minute_coverage_rate": 0.9506172839506173,
  "planned_stop_hit_rate": 0.9506172839506173,
  "actual_exact_stop_rate": 0.07407407407407407,
  "missing_expected_hit_rows": 0,
  "adverse_slippage_cash_sum": 177820.0,
  "unique_physical_event_adverse_slippage_cash_sum": 73790.0,
  "first_hit_open_adverse_cash_sum": 293211.6,
  "actual_exit_worse_than_day_worst_rows": 0,
  "promote_to_proxy": false,
  "promote_to_true_engine": false,
  "strategy_changed": false,
  "true_engine_run": false,
  "order_api_calls": 0,
  "ctp_connected": false,
  "next_step": "不把日内止损成交滑点作为主优化方向；继续追持仓路径中非日内止损的账户层暴露、趋势衰退或组合相关性。",
  "overfit_after": "否。固定 Stage827/847 止损族和预声明阈值，没有按结果筛选窗口。",
  "continue_after": "有但需换问题",
  "continue_reason": "日内止损本身不是主要系统性穿价来源，继续围绕它调参会过拟合。"
}
```

## 后续规划和 TODO

- 不把日内止损成交滑点作为主优化方向；继续追持仓路径中非日内止损的账户层暴露、趋势衰退或组合相关性。

## 过拟合反思

- 运行前：否，固定样本和止损语义，只审计执行事实。
- 运行后：否。固定 Stage827/847 止损族和预声明阈值，没有按结果筛选窗口。

## 继续价值反思

- 运行前：有，直接回应止损是否被远超止损价成交。
- 运行后：有但需换问题。日内止损本身不是主要系统性穿价来源，继续围绕它调参会过拟合。

## 输出

- 报告：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage104_intraday_stop_minute_path_slippage_audit/rebuilt_c9_v2_stage104_intraday_stop_minute_path_slippage_audit_report_stage104_intraday_stop_minute_path_slippage_audit_v1.md`
- 事件明细：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage104_intraday_stop_minute_path_slippage_audit/rebuilt_c9_v2_stage104_intraday_stop_minute_path_slippage_audit_event_panel_stage104_intraday_stop_minute_path_slippage_audit_v1.csv.gz`
- 退出原因汇总：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage104_intraday_stop_minute_path_slippage_audit/rebuilt_c9_v2_stage104_intraday_stop_minute_path_slippage_audit_by_exit_reason_stage104_intraday_stop_minute_path_slippage_audit_v1.csv`
- 起点汇总：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage104_intraday_stop_minute_path_slippage_audit/rebuilt_c9_v2_stage104_intraday_stop_minute_path_slippage_audit_by_start_stage104_intraday_stop_minute_path_slippage_audit_v1.csv`
- 品种汇总：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage104_intraday_stop_minute_path_slippage_audit/rebuilt_c9_v2_stage104_intraday_stop_minute_path_slippage_audit_by_symbol_stage104_intraday_stop_minute_path_slippage_audit_v1.csv`
- 分钟源审计：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage104_intraday_stop_minute_path_slippage_audit/rebuilt_c9_v2_stage104_intraday_stop_minute_path_slippage_audit_minute_source_audit_stage104_intraday_stop_minute_path_slippage_audit_v1.csv`
- 输入审计：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage104_intraday_stop_minute_path_slippage_audit/rebuilt_c9_v2_stage104_intraday_stop_minute_path_slippage_audit_input_audit_stage104_intraday_stop_minute_path_slippage_audit_v1.csv`
