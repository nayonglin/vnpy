# Stage081 国内会员排名特征方向/OOS 审计

- line_id：`futures_trend_rebuilt_c9_15w_optimization`
- 当前模式：day
- 记录时间：2026-07-02 02:27:44 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读信号方向/OOS 审计，不改线上、不改 AI 池、不接 CTP/SimNow。
- 是否重要突破：否，除非后续 proxy/真引擎证明可改善目标。
- 是否触发A/B：否。

## 外部调研与判断

- 参考资料：CFTC COT、CME open interest、国内商品成交持仓排名因子研报、我国商品期货持仓额信息含量研究、pysystemtrade。
- 我的判断：会员排名有经济含义，但必须从净持仓方向/净变化这类低自由度特征开始，并经过 OOS、年份、品种、source 稳定性门；覆盖达标不等于信号有效。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_optimization/tools/stage081_member_rank_signal_audit.py`。
- 新增测试：`tests/test_rebuilt_c9_stage081_member_rank_signal_audit.py`。
- 修改脚本：无正式交易脚本修改。
- 删除脚本：无。
- 新增参数：`MIN_COUNT=120`、`MIN_SOURCE_COUNT=8`、`MIN_YEAR_COUNT=4`、`MIN_PRODUCT_COUNT=8`、`MIN_OOS_FOLDS=3`、`MIN_MEAN_PNL_LIFT=1.2`。
- 修改参数：无正式交易参数修改。
- 删除参数：无。

## 回测/归因参数

- 数据区间：Stage038 opened flat-entry 样本 + Stage080 补数后的会员排名 T+1 as-of 特征。
- 账户规模：不适用，本阶段无资金曲线回测。
- 成本口径：不适用，本阶段无交易回放。
- 样本过滤：会员排名必须 `member_rank_available=True` 才形成方向特征；OOS fold 沿用 Stage038。
- 策略/归因口径：只读候选级 realized PnL/OOS/年份/品种/source 审计，不生成真实订单或资金曲线。

## 结果

- 期末权益：不适用。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：不适用。
- 胜率：不适用。
- 决策：`stage081_member_rank_no_stable_signal_candidate_keep_readonly`。
- 会员排名可用覆盖：`1566/2787` = `56.1895%`。
- stable candidate count：`0`。
- 最佳候选：``。

## 输出文件

- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage081_member_rank_signal_audit/rebuilt_c9_stage081_member_rank_signal_audit_report_stage081_member_rank_signal_audit_v1.md`
- summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage081_member_rank_signal_audit/rebuilt_c9_stage081_member_rank_signal_audit_summary_stage081_member_rank_signal_audit_v1.csv`
- fold_detail：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage081_member_rank_signal_audit/rebuilt_c9_stage081_member_rank_signal_audit_fold_detail_stage081_member_rank_signal_audit_v1.csv`
- year_detail：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage081_member_rank_signal_audit/rebuilt_c9_stage081_member_rank_signal_audit_year_detail_stage081_member_rank_signal_audit_v1.csv`
- product_detail：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage081_member_rank_signal_audit/rebuilt_c9_stage081_member_rank_signal_audit_product_detail_stage081_member_rank_signal_audit_v1.csv`
- prepared_matrix：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage081_member_rank_signal_audit/rebuilt_c9_stage081_member_rank_signal_audit_prepared_matrix_stage081_member_rank_signal_audit_v1.csv`
- decision：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage081_member_rank_signal_audit/rebuilt_c9_stage081_member_rank_signal_audit_decision_stage081_member_rank_signal_audit_v1.json`
- chart：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage081_member_rank_signal_audit/rebuilt_c9_stage081_member_rank_signal_audit_candidate_chart_stage081_member_rank_signal_audit_v1.png`

## 候选摘要

| condition                                            | member_rank_signal_candidate   |   count |         total_pnl |   mean_pnl_lift_vs_base |   oos_positive_fold_count |   oos_test_fold_count |   oos_min_fold_pnl |    worst_year_pnl | failure_reasons                                                                                                          |
|:-----------------------------------------------------|:-------------------------------|--------:|------------------:|------------------------:|--------------------------:|----------------------:|-------------------:|------------------:|:-------------------------------------------------------------------------------------------------------------------------|
| account_injured_and_member_position_flow_aligned     | False                          |     301 |       8.14948e+06 |                  1.2007 |                         3 |                     3 |   248644           |      -1.24337e+06 | positive_year_count,worst_year_pnl                                                                                       |
| ai_rank_1_6_and_member_net_flow_aligned              | False                          |     402 |       7.82326e+06 |                  0.8631 |                         1 |                     3 |       -2.42133e+06 |      -1.65341e+06 | oos_positive_fold_count,oos_min_fold_pnl,positive_year_count,worst_year_pnl,mean_pnl_lift                                |
| member_rank_aligned_and_turnover_low                 | False                          |     305 |       4.8763e+06  |                  0.709  |                         1 |                     3 |       -2.73918e+06 |      -2.3041e+06  | oos_positive_fold_count,oos_min_fold_pnl,positive_year_count,worst_year_pnl,mean_pnl_lift                                |
| full_market_ai_top8_and_member_net_position_aligned  | False                          |     110 |       1.68124e+06 |                  0.6778 |                         2 |                     3 |  -484450           | -395840           | count,product_count,oos_positive_fold_count,oos_min_fold_pnl,positive_year_count,worst_year_pnl,mean_pnl_lift            |
| member_rank_net_position_and_flow_aligned            | False                          |     428 |       5.82451e+06 |                  0.6035 |                         2 |                     3 |       -1.54973e+06 |      -1.24337e+06 | oos_positive_fold_count,oos_min_fold_pnl,positive_year_count,worst_year_pnl,mean_pnl_lift                                |
| member_rank_aligned_and_turnover_high                | False                          |     273 |       3.70318e+06 |                  0.6016 |                         1 |                     3 |       -1.73905e+06 |      -1.16358e+06 | product_count,oos_positive_fold_count,oos_min_fold_pnl,positive_year_count,worst_year_pnl,mean_pnl_lift                  |
| member_rank_net_flow_aligned                         | False                          |     819 |       8.39575e+06 |                  0.4546 |                         1 |                     3 |       -3.09547e+06 |      -1.74002e+06 | oos_positive_fold_count,oos_min_fold_pnl,positive_year_count,worst_year_pnl,mean_pnl_lift                                |
| member_rank_net_position_aligned                     | False                          |     769 |       6.2411e+06  |                  0.3599 |                         3 |                     3 |        1.62436e+06 |      -2.40695e+06 | positive_year_count,worst_year_pnl,mean_pnl_lift                                                                         |
| member_rank_net_position_or_flow_aligned             | False                          |    1160 |       8.81234e+06 |                  0.3369 |                         2 |                     3 |       -3.60933e+06 |      -1.83095e+06 | oos_positive_fold_count,oos_min_fold_pnl,positive_year_count,worst_year_pnl,mean_pnl_lift                                |
| full_market_ai_top8_and_member_position_flow_aligned | False                          |      56 |  373320           |                  0.2956 |                         2 |                     3 |  -438750           |  -65700           | count,year_count,product_count,oos_positive_fold_count,oos_min_fold_pnl,positive_year_count,worst_year_pnl,mean_pnl_lift |
| full_market_ai_top8_and_member_net_flow_aligned      | False                          |     138 |  297710           |                  0.0957 |                         2 |                     3 |       -1.84164e+06 | -800500           | product_count,oos_positive_fold_count,oos_min_fold_pnl,positive_year_count,worst_year_pnl,mean_pnl_lift                  |
| ai_rank_1_6_and_member_net_position_aligned          | False                          |     380 | -903374           |                 -0.1054 |                         1 |                     3 |       -3.0534e+06  |      -2.47667e+06 | oos_positive_fold_count,oos_min_fold_pnl,positive_year_count,worst_year_pnl,total_pnl,mean_pnl_lift                      |
| member_rank_net_position_against                     | False                          |     797 |       7.14952e+06 |                  0.3978 |                         1 |                     3 |       -7.42664e+06 |      -3.60547e+06 | not_promotion_eligible,oos_positive_fold_count,oos_min_fold_pnl,positive_year_count,worst_year_pnl,mean_pnl_lift         |
| member_rank_available                                | False                          |    1566 |       1.33906e+07 |                  0.3792 |                         1 |                     3 |       -4.57481e+06 |      -3.08269e+06 | not_promotion_eligible,oos_positive_fold_count,oos_min_fold_pnl,positive_year_count,worst_year_pnl,mean_pnl_lift         |
| member_rank_net_flow_against                         | False                          |     747 |       4.99488e+06 |                  0.2965 |                         2 |                     3 |       -1.9873e+06  |      -4.85948e+06 | not_promotion_eligible,oos_positive_fold_count,oos_min_fold_pnl,positive_year_count,worst_year_pnl,mean_pnl_lift         |

## 结论

- 本阶段结论：`stage081_member_rank_no_stable_signal_candidate_keep_readonly`。
- 是否进入下一步：只有 stable candidate 存在时，才允许冻结一个候选进入 Stage082 proxy；本阶段不能直接上线或改真实引擎。
- 下一步：若有候选，做固定 `+25%` 或更保守非挤占 proxy；若无候选，关闭会员排名交易化方向。

## 过拟合反思

- 运行前判断：否；只读审计预声明会员排名方向特征，不根据结果调阈值。
- 运行后判断：若继续围绕失败条件改符号、分位、年份、品种、方向或 topN，就是过拟合。
- 原因：会员排名信号必须能穿越 source/year/product/fold，而不是解释单段左尾。

## 继续价值反思

- 运行前判断：有；Stage080 已修复左尾覆盖。
- 运行后判断：取决于 stable candidate；即便存在也只是进入 proxy 验真。
- 原因：覆盖只是资格，真正价值要看 OOS 与组合路径。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Stage081 结论和下一步边界。
- 是否更新 `research/registry.md`：是，最新关键阶段推进到 Stage081。
- 是否追加根目录 `memory.md/back_log.md`：仅追加 `back_log.md` 重要摘要，不改 `memory.md`。
