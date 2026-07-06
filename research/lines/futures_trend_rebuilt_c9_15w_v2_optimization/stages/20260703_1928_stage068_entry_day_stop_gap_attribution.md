# Stage068 开仓日/止损滑穿归因

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-03T19:28:19
- 工作区：`/Users/bytedance/Desktop/person/vnpy`
- 是否重要突破：否，执行路径法证；不改策略、不调参数
- 是否触发A/B：否，本阶段不提出上线候选

## 外部调研与判断

- 止损单只保证触发，不保证成交在止损价；跳空或日线回测会导致按下一可成交价成交。
- 因此本阶段同时看 `initial_stop_price -> exit_price` 和 `trigger event price -> fill price` 两种偏离。
- 本次判断：要区分信号/止损逻辑是否错、以及日线/下一日成交模型是否放大亏损。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage068_stage067_entry_day_stop_gap_attribution.py`
- 修改正式入口：无
- 删除文件：无
- 新增参数：无交易参数；复用 Stage067 最长水下 8 条关键路径
- 修改参数：无
- 删除参数：无

## 归因口径

- 开仓日贡献：若同日平仓，用 realized_pnl；否则按开仓日收盘相对开仓价估算 mark PnL。
- 后续贡献：`realized_pnl - entry_day_mark_pnl`。
- 初始止损滑穿：long 用 `initial_stop_price - exit_price`，short 用 `exit_price - initial_stop_price`，只统计正值。
- 触发到成交滑穿：匹配同合约、同 exit_reason、entry_date 到 exit_date 内最后一个 trade_event，用 event price 到实际 fill price 的不利偏离。
- 关键路径重放校验：`8/8` 通过。

## 结果摘要

- 亏损 lot：`737`，合计 realized_pnl `-1,553,884.40`。
- 同日出场亏损 lot：`78`。
- 最大不利点出现在开仓日的亏损 lot：`150`。
- 开仓日负贡献 `-583,364.40`，后续负贡献 `-1,102,700.00`，开仓日负贡献占比 `34.60%`。
- 亏损 stop lot：`667`；其中相对初始止损更差成交 `467` 笔，额外不利 `681,101.00`。
- 有触发事件匹配的亏损 stop lot 中，触发到成交更差 `322` 笔，额外不利 `156,020.00`。

## Entry-Day vs Later

| sample               |   lots |      realized_pnl |   same_day_exit_lots |   same_day_exit_realized_pnl |   mae_on_entry_day_lots |   mae_within_3d_lots |   entry_day_loss_component |   post_entry_loss_component |   entry_day_loss_share_of_negative_components |   median_holding_days |
|:---------------------|-------:|------------------:|---------------------:|-----------------------------:|------------------------:|---------------------:|---------------------------:|----------------------------:|----------------------------------------------:|----------------------:|
| all_losing_lots      |    737 |      -1.55388e+06 |                   78 |                     -77834.4 |                     150 |                  391 |                    -583364 |                -1.1027e+06  |                                      0.345992 |                     3 |
| stop_losing_lots     |    667 |      -1.4049e+06  |                   51 |                     -53394.4 |                     102 |                  330 |                    -502574 |                -1.05544e+06 |                                      0.322575 |                     4 |
| non_stop_losing_lots |     70 | -148985           |                   27 |                     -24440   |                      48 |                   61 |                     -80790 |            -47265           |                                      0.630901 |                     1 |

## Exit Reason Summary

| exit_reason                             |   losing_lots |   realized_pnl |   median_holding_days |   same_day_exit_lots |   mae_on_entry_day_lots |   entry_day_loss_component |   post_entry_loss_component |   initial_stop_worse_count |   initial_stop_worse_cash |   initial_stop_worse_r_median |   event_to_fill_worse_count |   event_to_fill_worse_cash |   event_to_fill_worse_r_median |
|:----------------------------------------|--------------:|---------------:|----------------------:|---------------------:|------------------------:|---------------------------:|----------------------------:|---------------------------:|--------------------------:|------------------------------:|----------------------------:|---------------------------:|-------------------------------:|
| long_prev2day_stop                      |           261 |      -686650   |                     6 |                    0 |                       0 |                   -93950   |                     -701410 |                        205 |                    381061 |                      0.555177 |                         115 |                      32280 |                      0         |
| long_base_stop                          |           158 |      -319760   |                     2 |                    0 |                      28 |                  -206460   |                     -105020 |                        124 |                    147156 |                      0.651306 |                         108 |                      76230 |                      0.15      |
| short_prev2day_stop                     |           128 |      -187130   |                     7 |                    0 |                       7 |                   -23880   |                     -199370 |                         84 |                     73661 |                      0.222222 |                          64 |                      22850 |                      0.0454545 |
| short_base_stop                         |            49 |      -138245   |                     2 |                    0 |                      16 |                   -95690   |                      -49635 |                         35 |                     66763 |                      0.78953  |                          35 |                      24660 |                      0.277778  |
| long_risk_cluster_heat_deleverage       |            23 |       -74700   |                     1 |                    0 |                      13 |                   -34410   |                       -5130 |                          9 |                     42000 |                      0        |                           0 |                          0 |                    nan         |
| short_risk_cluster_heat_deleverage      |            12 |       -38165   |                     1 |                    0 |                       8 |                   -21940   |                      -23895 |                          4 |                     17580 |                      0        |                           0 |                          0 |                    nan         |
| stage847_intraday_05r_stop_no_reentry   |            32 |       -28904.4 |                     0 |                   32 |                      24 |                   -28904.4 |                           0 |                          0 |                         0 |                      0        |                           0 |                          0 |                      0         |
| nan                                     |            27 |       -24440   |                     0 |                   27 |                      27 |                   -24440   |                           0 |                          0 |                         0 |                      0        |                           0 |                          0 |                    nan         |
| long_ma_stop                            |            20 |       -19720   |                     1 |                    0 |                       8 |                   -29200   |                           0 |                          0 |                         0 |                      0        |                           0 |                          0 |                      0         |
| stage827_intraday_c2_1r_stop            |            13 |       -13610   |                     0 |                   13 |                      13 |                   -13610   |                           0 |                         13 |                      4980 |                      0.545455 |                           0 |                          0 |                      0         |
| rollover_close                          |             8 |       -11680   |                     2 |                    0 |                       0 |                        0   |                      -18240 |                          8 |                      8160 |                      2.31818  |                           0 |                          0 |                    nan         |
| stage847_intraday_retry_failed_05r_stop |             6 |       -10880   |                     0 |                    6 |                       6 |                   -10880   |                           0 |                          6 |                      7480 |                      2.2      |                           0 |                          0 |                      0         |

## 决策

- 决策：`entry_day_stop_gap_forensics_keep_research_only`
- 原因：最长水下路径的亏损不是全部开仓当天实现，开仓日不利波动很常见，但主要亏损额更多来自持仓后继续亏；部分 stop 出场确实存在触发日到实际成交日的更差成交，且相对初始止损价有明显越界，但这不是全部亏损的唯一来源。

## 后续规划和 TODO

- 若继续，优先做 stop event 到 fill 的执行模型审计，确认日线下一日成交是否过度保守或贴近真实。
- 再做开仓后 1-3 日不利路径识别，但不能按 2022-04/2022-08 单月救参。
- 不做基于本次最差 stop lot 的品种/方向黑名单。

## 过拟合反思

- 运行前：否。只读法证，不改变止损、开仓、储备释放或品种参数。
- 运行后：否。结论用于解释执行路径和数据粒度，不据此做单品种黑名单或止损价补丁。

## 继续价值反思

- 运行前：有。用户的问题直指长水下是否由开仓日亏损或止损滑穿导致，需要逐笔核实。
- 运行后：有。下一步若继续，应研究执行/止损成交模型和开仓后不利路径识别，但不能按最差月份救参。

## 输出

- closed_lots: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage068_stage067_entry_day_stop_gap_attribution/rebuilt_c9_v2_stage068_stage067_entry_day_stop_gap_attribution_closed_lots_stage068_stage067_entry_day_stop_gap_attribution_v1.csv.gz`
- path_summary: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage068_stage067_entry_day_stop_gap_attribution/rebuilt_c9_v2_stage068_stage067_entry_day_stop_gap_attribution_path_summary_stage068_stage067_entry_day_stop_gap_attribution_v1.csv`
- exit_reason_summary: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage068_stage067_entry_day_stop_gap_attribution/rebuilt_c9_v2_stage068_stage067_entry_day_stop_gap_attribution_exit_reason_summary_stage068_stage067_entry_day_stop_gap_attribution_v1.csv`
- worst_initial_stop_gaps: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage068_stage067_entry_day_stop_gap_attribution/rebuilt_c9_v2_stage068_stage067_entry_day_stop_gap_attribution_worst_initial_stop_gaps_stage068_stage067_entry_day_stop_gap_attribution_v1.csv`
- worst_event_to_fill_gaps: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage068_stage067_entry_day_stop_gap_attribution/rebuilt_c9_v2_stage068_stage067_entry_day_stop_gap_attribution_worst_event_to_fill_gaps_stage068_stage067_entry_day_stop_gap_attribution_v1.csv`
- entry_day_vs_later: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage068_stage067_entry_day_stop_gap_attribution/rebuilt_c9_v2_stage068_stage067_entry_day_stop_gap_attribution_entry_day_vs_later_stage068_stage067_entry_day_stop_gap_attribution_v1.csv`
- rerun_validation: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage068_stage067_entry_day_stop_gap_attribution/rebuilt_c9_v2_stage068_stage067_entry_day_stop_gap_attribution_rerun_validation_stage068_stage067_entry_day_stop_gap_attribution_v1.csv`
- chart: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage068_stage067_entry_day_stop_gap_attribution/rebuilt_c9_v2_stage068_stage067_entry_day_stop_gap_attribution_entry_day_stop_gap_chart_stage068_stage067_entry_day_stop_gap_attribution_v1.png`
- report: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage068_stage067_entry_day_stop_gap_attribution/rebuilt_c9_v2_stage068_stage067_entry_day_stop_gap_attribution_report_stage068_stage067_entry_day_stop_gap_attribution_v1.md`
