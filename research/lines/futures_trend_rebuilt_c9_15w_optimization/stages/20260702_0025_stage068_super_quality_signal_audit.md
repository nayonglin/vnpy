# Stage068 - AI 超高质量信号组合只读审计

- line_id：`futures_trend_rebuilt_c9_15w_optimization`
- 当前模式：`day`
- 记录时间：`2026-07-02T00:25`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读 PIT/OOS 信号质量审计
- 是否重要突破：`否`
- 是否触发A/B：`否`

## 外部调研与判断

- 参考资料：CFA commodity ML、commodity futures trend-following/cross-sectional trend、purged/embargo CV。
- 我的判断：AI 选品优化必须用点时可见、低自由度、OOS 全正的组合；不能把单年高均值或删除前记忆当作可交易规则。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_optimization/tools/stage068_super_quality_signal_audit.py`
- 新增测试：`tests/test_rebuilt_c9_stage068_super_quality_signal_audit.py`
- 修改脚本：无正式策略脚本。
- 删除脚本：无。
- 新增参数：`MIN_COUNT=120`、`MIN_SOURCE_COUNT=8`、`MIN_YEAR_COUNT=4`、`MIN_PRODUCT_COUNT=8`、`MIN_OOS_FOLDS=3`、`MIN_MEAN_PNL_LIFT=1.2`。
- 修改参数：无正式交易参数。
- 删除参数：无。

## 回测/归因参数

- 数据区间：复用 Stage038 `2020-01-02` 到 `2026-06-24` opened flat-entry 聚合矩阵。
- 账户规模：不适用，本阶段非资金曲线回测。
- 成本口径：复用 Stage038 realized PnL，非新增撮合。
- 样本过滤：固定低自由度 AI/full-market/account 组合；OI 与 selected_volume 仅诊断不晋级。
- 策略/归因口径：沿用 Stage038 OOS fold，要求每个命中 fold 和观察年份均为正。

## 结果

- 期末权益：不适用。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：不适用。
- 胜率：见 summary 表。
- 其他关键指标：matrix rows `2787`；stable candidates `4`；new composite candidates `3`；best new `full_market_ai_top8_and_account_injured`。

## 候选摘要

| condition                                        | promotion_eligible   | new_composite   |   count |   year_count |   product_count |    total_pnl |   mean_pnl_lift_vs_base |   oos_positive_fold_count |   oos_test_fold_count |    worst_year_pnl | super_quality_candidate   | failure_reasons                                                                                                                                  |
|:-------------------------------------------------|:---------------------|:----------------|--------:|-------------:|----------------:|-------------:|------------------------:|--------------------------:|----------------------:|------------------:|:--------------------------|:-------------------------------------------------------------------------------------------------------------------------------------------------|
| full_market_ai_top8_and_account_injured          | True                 | True            |     213 |            5 |              12 |  1.92244e+07 |                  4.0027 |                         3 |                     3 |   16200           | True                      |                                                                                                                                                  |
| full_market_ai_top8_and_ai_rank_1_6              | True                 | True            |     227 |            4 |               9 |  1.77944e+07 |                  3.4764 |                         3 |                     3 |  146300           | True                      |                                                                                                                                                  |
| full_market_ai_top8_and_active_positions_lt3     | True                 | True            |     322 |            5 |              13 |  2.05628e+07 |                  2.8321 |                         3 |                     3 |   69720           | True                      |                                                                                                                                                  |
| full_market_ai_top8                              | True                 | False           |     349 |            5 |              14 |  1.95254e+07 |                  2.4811 |                         3 |                     3 |   69720           | True                      |                                                                                                                                                  |
| full_market_ai_top8_ai_rank_1_6_account_injured  | True                 | True            |     147 |            4 |               7 |  1.91718e+07 |                  5.7839 |                         2 |                     3 |   16200           | False                     | product_count,oos_positive_fold_count,oos_min_fold_pnl                                                                                           |
| ai_rank_1_6_and_account_injured                  | True                 | True            |     898 |            7 |              18 |  1.49784e+07 |                  0.7397 |                         4 |                     4 |      -9.6184e+06  | False                     | positive_year_count,worst_year_pnl,mean_pnl_lift                                                                                                 |
| full_market_ai_top8_and_loss_streak_0            | True                 | True            |     137 |            4 |              10 | -1.82383e+06 |                 -0.5904 |                         1 |                     3 |      -2.93694e+06 | False                     | oos_positive_fold_count,oos_min_fold_pnl,positive_year_count,worst_year_pnl,total_pnl,mean_pnl_lift                                              |
| full_market_ai_top8_and_ai_rank_1_3              | True                 | True            |     107 |            4 |               5 | -3.14208e+06 |                 -1.3023 |                         1 |                     3 |      -1.5745e+06  | False                     | count,product_count,oos_positive_fold_count,oos_min_fold_pnl,positive_year_count,worst_year_pnl,total_pnl,mean_pnl_lift                          |
| full_market_ai_top8_and_account_clean            | True                 | True            |      64 |            4 |               8 | -3.92124e+06 |                 -2.7172 |                         0 |                     3 |      -2.05342e+06 | False                     | count,oos_positive_fold_count,oos_min_fold_pnl,positive_year_count,worst_year_pnl,total_pnl,mean_pnl_lift                                        |
| ai_rank_1_6                                      | True                 | False           |    1529 |            7 |              18 |  4.15723e+07 |                  1.2058 |                         4 |                     4 |      -9.63576e+06 | False                     | positive_year_count,worst_year_pnl                                                                                                               |
| full_market_consensus_top8_and_ai_rank_1_6       | False                | True            |      41 |            2 |               3 |  1.21699e+07 |                 13.1637 |                         1 |                     2 | -817320           | False                     | not_promotion_eligible,count,year_count,product_count,oos_fold_count,oos_positive_fold_count,oos_min_fold_pnl,positive_year_count,worst_year_pnl |
| full_market_ai_top8_ai_rank_1_6_not_oi_confirmed | False                | True            |     152 |            4 |               8 |  2.12755e+07 |                  6.2074 |                         3 |                     3 | -550350           | False                     | not_promotion_eligible,positive_year_count,worst_year_pnl                                                                                        |
| full_market_ai_top8_and_not_oi_confirmed         | False                | True            |     224 |            4 |              11 |  2.47632e+07 |                  4.9027 |                         3 |                     3 |  623000           | False                     | not_promotion_eligible                                                                                                                           |
| full_market_ai_top8_and_selected_volume_gt1      | False                | True            |     314 |            5 |              14 |  1.95131e+07 |                  2.756  |                         3 |                     3 |   69720           | False                     | not_promotion_eligible                                                                                                                           |
| ai_rank_1_6_and_not_oi_confirmed                 | False                | True            |     944 |            7 |              17 |  5.23511e+07 |                  2.4594 |                         4 |                     4 |      -5.53086e+06 | False                     | not_promotion_eligible,positive_year_count,worst_year_pnl                                                                                        |
| full_market_consensus_top8                       | False                | False           |      91 |            2 |               6 |  1.2595e+07  |                  6.1381 |                         2 |                     2 |  739150           | False                     | not_promotion_eligible,count,year_count,product_count,oos_fold_count                                                                             |
| account_injured                                  | False                | False           |    1450 |            7 |              19 |  3.40788e+07 |                  1.0423 |                         4 |                     4 |      -7.23738e+06 | False                     | not_promotion_eligible,positive_year_count,worst_year_pnl,mean_pnl_lift                                                                          |

## 输出文件

- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage068_super_quality_signal_audit/rebuilt_c9_stage068_super_quality_signal_audit_report_stage068_super_quality_signal_audit_v1.md`
- summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage068_super_quality_signal_audit/rebuilt_c9_stage068_super_quality_signal_audit_summary_stage068_super_quality_signal_audit_v1.csv`
- fold_detail：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage068_super_quality_signal_audit/rebuilt_c9_stage068_super_quality_signal_audit_fold_detail_stage068_super_quality_signal_audit_v1.csv`
- year_detail：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage068_super_quality_signal_audit/rebuilt_c9_stage068_super_quality_signal_audit_year_detail_stage068_super_quality_signal_audit_v1.csv`
- chart：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage068_super_quality_signal_audit/rebuilt_c9_stage068_super_quality_signal_audit_candidate_chart_stage068_super_quality_signal_audit_v1.png`
- decision：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage068_super_quality_signal_audit/rebuilt_c9_stage068_super_quality_signal_audit_decision_stage068_super_quality_signal_audit_v1.json`

## 结论

- 本阶段结论：`stage068_has_new_composite_super_quality_candidate_needs_proxy`。
- 是否进入下一步：`是`。
- 下一步：`stage069_freeze_one_composite_ai_account_proxy_true_engine_no_param_sweep`。

## 过拟合反思

- 运行前判断：否，固定 Stage038 可见字段与少数理论组合，不扫收益阈值。
- 运行后判断：否，本阶段没有根据结果救参；诊断项不直接晋级。
- 原因：只输出资格审计，不改实盘、不写交易规则、不连接订单链路。

## 继续价值反思

- 运行前判断：有，用户目标包含 AI 高质量信号和加大风险投入，必须先证明质量层存在。
- 运行后判断：`有`。
- 原因：若 new composite 通过，下一步可冻结一个 proxy；若没有，应转账户外层或新 PIT 信息源。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：是。
- 是否追加根目录 `memory.md/back_log.md`：追加 `back_log.md`，`memory.md` 视为非正式突破可不追加。
