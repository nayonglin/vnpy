# Stage055 - 新开仓信号预算只读审计

- 记录时间：`2026-07-01T21:20`
- line_id：`futures_trend_rebuilt_c9_15w_optimization`
- model_tag：`stage055_new_entry_signal_budget_audit_v1`
- 是否重要突破版本：`否`
- 决策：`stage055_has_new_entry_negative_conditions_need_true_budget_engine`

## 本次版本变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_optimization/tools/stage055_new_entry_signal_budget_audit.py`
- 新增测试：`tests/test_rebuilt_c9_stage055_new_entry_signal_budget_audit.py`
- 新增参数：`MIN_CONDITION_COUNT=8`、`MIN_CONDITION_SOURCE_COUNT=2`，只用于只读标记负贡献条件。
- 修改参数：无；Stage013/Stage054/官方 C9 配置均未改。
- 删除参数：无。
- 新增回测结果：Stage054 最差窗口中新开 flat_entry 的 closed-lot PIT feature matrix 和条件 PnL 归因。
- 本阶段不连接 CTP，不调用订单 API，不触发 A/B。

## 调研和判断结论

- 趋势跟踪公开资料和 pysystemtrade/PyTrendFollow 等实现都更支持将信号、目标风险和仓位预算分离。Stage055 因此只审计 Stage054 左尾中新开仓的入场前可见条件，不按亏损品种、方向或日期写规则。参考：https://github.com/pst-group/pysystemtrade ; https://github.com/chrism2671/PyTrendFollow ; https://papers.ssrn.com/sol3/Delivery.cfm/SSRN_ID3231836_code1554519.pdf?abstractid=2063848&mirid=1

## 结果

- 唯一窗口数：`9`。
- feature matrix 行数：`246`。
- Stage054 窗口内 entry 数：`246`。
- 窗口 entry realized PnL：`-474,365.00`。
- 窗口 entry loss_abs：`576,250.00`。
- negative condition 数：`14`。
- top_negative_conditions：`['ai_rank_1_9', 'selected_volume_gt1', 'normal_release_not_full_market_ai_top8', 'oi_confirmed', 'selected_volume_ge5', 'ai_rank_1_6', 'drawdown_abs_ge10', 'account_clean', 'account_injured', 'drawdown_abs_ge20']`。

## 条件 PnL 汇总

| condition                              | description                                 | candidate_eligible   |   count |   source_count |   date_count |   product_count |   total_pnl |   mean_pnl |   median_pnl |   loss_rate_pct |   loss_abs |   loss_abs_share_pct |   selected_volume_sum |   selected_volume_gt1_rate_pct | negative_contributor   |
|:---------------------------------------|:--------------------------------------------|:---------------------|--------:|---------------:|-------------:|----------------:|------------:|-----------:|-------------:|----------------:|-----------:|---------------------:|----------------------:|-------------------------------:|:-----------------------|
| ai_rank_1_9                            | Stage182 AI rank 1-9                        | True                 |     246 |              9 |           40 |              14 |     -474365 |  -1928.31  |       -750   |         76.8293 |     576250 |             100      |                   616 |                        40.6504 | True                   |
| selected_volume_gt1                    | 释放到 1 手以上                             | True                 |     100 |              9 |           26 |              11 |     -474110 |  -4741.1   |      -5040   |         89      |     486770 |              84.472  |                   470 |                       100      | True                   |
| normal_release_not_full_market_ai_top8 | 释放到 1 手以上且不是 full-market AI top8   | True                 |     100 |              9 |           26 |              11 |     -474110 |  -4741.1   |      -5040   |         89      |     486770 |              84.472  |                   470 |                       100      | True                   |
| oi_confirmed                           | OI 与价格方向确认                           | True                 |     117 |              9 |           20 |              11 |     -412910 |  -3529.15  |      -3800   |         82.0513 |     428560 |              74.3705 |                   388 |                        61.5385 | True                   |
| selected_volume_ge5                    | 释放到 5 手及以上                           | True                 |      58 |              9 |           16 |               7 |     -340180 |  -5865.17  |      -5300   |         84.4828 |     349600 |              60.6681 |                   339 |                       100      | True                   |
| ai_rank_1_6                            | Stage182 AI rank 1-6                        | True                 |     127 |              9 |           20 |              12 |     -298760 |  -2352.44  |       -680   |         78.7402 |     345170 |              59.8993 |                   372 |                        51.1811 | True                   |
| drawdown_abs_ge10                      | 入场前回撤绝对值 >=10%                      | True                 |     227 |              9 |           38 |              14 |     -267535 |  -1178.57  |       -680   |         74.8899 |     369420 |              64.1076 |                   515 |                        35.6828 | True                   |
| account_clean                          | 入场前账户干净                              | True                 |      19 |              9 |            5 |               5 |     -206830 | -10885.8   |      -7900   |        100      |     206830 |              35.8924 |                   101 |                       100      | True                   |
| account_injured                        | 入场前账户受伤                              | True                 |     216 |              9 |           37 |              14 |     -206815 |   -957.477 |       -680   |         73.6111 |     308700 |              53.5705 |                   456 |                        32.4074 | True                   |
| drawdown_abs_ge20                      | 入场前回撤绝对值 >=20%                      | True                 |     214 |              9 |           37 |              14 |     -206355 |   -964.276 |       -680   |         73.8318 |     307320 |              53.331  |                   451 |                        31.7757 | True                   |
| normal_release_not_ai_rank_1_6         | 释放到 1 手以上且不是 Stage182 AI rank 1-6  | True                 |      35 |              9 |           14 |               5 |     -168540 |  -4815.43  |      -5150   |         94.2857 |     174040 |              30.2022 |                   160 |                       100      | True                   |
| ai_rank_1_6_and_account_clean          | Stage182 AI rank 1-6 且账户干净             | True                 |      11 |              9 |            4 |               4 |     -143630 | -13057.3   |     -16140   |        100      |     143630 |              24.9249 |                    61 |                       100      | True                   |
| loss_streak_ge2                        | loss_streak >=2                             | True                 |     164 |              9 |           21 |               9 |     -119895 |   -731.067 |       -600   |         68.2927 |     216050 |              37.4924 |                   345 |                        25      | True                   |
| loss_streak_ge3                        | loss_streak >=3                             | True                 |     145 |              9 |           18 |               8 |      -60695 |   -418.586 |       -460   |         64.8276 |     156410 |              27.1427 |                   292 |                        21.3793 | True                   |
| all_stage054_window_entries            | 全部 Stage054 窗口后新开 flat_entry         | False                |     246 |              9 |           40 |              14 |     -474365 |  -1928.31  |       -750   |         76.8293 |     576250 |             100      |                   616 |                        40.6504 | False                  |
| ai_rank_1_6_and_full_market_ai_top8    | Stage182 AI rank 1-6 且 full-market AI top8 | True                 |       1 |              1 |            1 |               1 |       -1650 |  -1650     |      -1650   |        100      |       1650 |               0.2863 |                     1 |                         0      | False                  |
| ai_rank_gt9_or_missing                 | AI rank >9 或缺失                           | True                 |       0 |              0 |            0 |               0 |           0 |      0     |          0   |          0      |          0 |               0      |                     0 |                         0      | False                  |
| full_market_consensus_top8             | full-market AI/simple 共识 top8             | True                 |       0 |              0 |            0 |               0 |           0 |      0     |          0   |          0      |          0 |               0      |                     0 |                         0      | False                  |
| active_positions_ge3                   | 入场前已有活跃持仓 >=3                      | True                 |       0 |              0 |            0 |               0 |           0 |      0     |          0   |          0      |          0 |               0      |                     0 |                         0      | False                  |
| full_market_ai_top8                    | full-market AI top8                         | True                 |      18 |              9 |            3 |               3 |        4845 |    269.167 |        357.5 |         50      |       2130 |               0.3696 |                    18 |                         0      | False                  |

## 校验

| check_type                                     |   actual |   reference |   abs_diff | note                                                                                                   |
|:-----------------------------------------------|---------:|------------:|-----------:|:-------------------------------------------------------------------------------------------------------|
| feature_matrix_rows                            |      246 |             |            | Stage055 rerun closed flat-entry open-trade feature matrix rows                                        |
| stage054_window_entry_rows                     |      246 |             |            | Entries with entry_date strictly after Stage054 window start and <= window end                         |
| stage054_position_net_vs_window_entry_realized |  -474365 |     -877180 |     402815 | This is expected to differ because positions include daily holding PnL and open exposure at window end |

## 输出

- unique_windows：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage055_new_entry_signal_budget_audit/rebuilt_c9_stage055_new_entry_signal_budget_audit_unique_windows_stage055_new_entry_signal_budget_audit_v1.csv`
- trades：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage055_new_entry_signal_budget_audit/rebuilt_c9_stage055_new_entry_signal_budget_audit_trades_stage055_new_entry_signal_budget_audit_v1.csv.gz`
- entry_risk：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage055_new_entry_signal_budget_audit/rebuilt_c9_stage055_new_entry_signal_budget_audit_entry_risk_stage055_new_entry_signal_budget_audit_v1.csv.gz`
- entry_candidates：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage055_new_entry_signal_budget_audit/rebuilt_c9_stage055_new_entry_signal_budget_audit_entry_candidates_stage055_new_entry_signal_budget_audit_v1.csv.gz`
- closed_lots：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage055_new_entry_signal_budget_audit/rebuilt_c9_stage055_new_entry_signal_budget_audit_closed_lots_stage055_new_entry_signal_budget_audit_v1.csv.gz`
- feature_matrix：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage055_new_entry_signal_budget_audit/rebuilt_c9_stage055_new_entry_signal_budget_audit_feature_matrix_stage055_new_entry_signal_budget_audit_v1.csv`
- window_entries：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage055_new_entry_signal_budget_audit/rebuilt_c9_stage055_new_entry_signal_budget_audit_stage054_window_entries_stage055_new_entry_signal_budget_audit_v1.csv`
- condition_summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage055_new_entry_signal_budget_audit/rebuilt_c9_stage055_new_entry_signal_budget_audit_condition_pnl_summary_stage055_new_entry_signal_budget_audit_v1.csv`
- source_summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage055_new_entry_signal_budget_audit/rebuilt_c9_stage055_new_entry_signal_budget_audit_source_summary_stage055_new_entry_signal_budget_audit_v1.csv`
- validation：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage055_new_entry_signal_budget_audit/rebuilt_c9_stage055_new_entry_signal_budget_audit_validation_stage055_new_entry_signal_budget_audit_v1.csv`
- chart：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage055_new_entry_signal_budget_audit/rebuilt_c9_stage055_new_entry_signal_budget_audit_condition_chart_stage055_new_entry_signal_budget_audit_v1.png`
- decision：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage055_new_entry_signal_budget_audit/rebuilt_c9_stage055_new_entry_signal_budget_audit_decision_stage055_new_entry_signal_budget_audit_v1.json`
- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage055_new_entry_signal_budget_audit/rebuilt_c9_stage055_new_entry_signal_budget_audit_report_stage055_new_entry_signal_budget_audit_v1.md`

## 反思

- 运行前过拟合反思：否。Stage055 固定使用 Stage054 已选窗口和日级起点，只做入场前可见条件归因，不新增交易参数。
- 运行后过拟合反思：否。本阶段没有按结果修改策略；如果下一步按单品种、单方向或单日期写预算规则，就是过拟合。
- 运行前继续价值反思：有。Stage054 已证明左尾来自窗口后新增风险暴露，必须拆入场前是否有可见质量差异。
- 运行后继续价值反思：有。Stage054 窗口后的新开仓里存在入场前可见的负贡献条件，但这仍是 closed-lot 归因，下一步必须写真引擎验证预算规则。
