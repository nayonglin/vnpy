# Stage038 - 候选级 PIT 特征矩阵与 OOS 预测力审计

- 记录时间：`2026-07-01T18:18`
- line_id：`futures_trend_rebuilt_c9_15w_optimization`
- model_tag：`stage038_candidate_pit_feature_matrix_audit_v1`
- 是否重要突破版本：`否`
- 决策：`stage038_has_preentry_oos_quality_candidates_needs_proxy_engine`

## 本次版本变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_optimization/tools/stage038_candidate_pit_feature_matrix_audit.py`
- 新增参数：`EMBARGO_DAYS=20`、`N_SPLITS=4`、`MIN_CONDITION_COUNT=60`、`MIN_OOS_TEST_FOLDS=3`。
- 修改参数：无，Stage006/Stage167 母本和官方 C9/15w 配置未改。
- 删除参数：无。
- 新增回测结果：无，本阶段不是收益回测，只做只读特征审计。
- 本阶段不连接 CTP，不调用订单 API，不触发 A/B。

## 调研和判断结论

- CFA commodity ML / futures momentum / OI 资料支持 theory-grounded 商品特征；Lopez de Prado/purged CV 和 backtest-overfitting 资料要求做点时、embargo、OOS 稳定性审计。
- 因此 Stage038 不训练模型、不扫阈值、不写交易规则，只判断现有入场前字段是否具备稳定识别超高质量信号的资格。

## 审计结果

- matrix rows：`2787`。
- entry date：`2020-01-02` -> `2026-06-24`。
- base total pnl：`62,843,641.40`。
- base mean pnl：`22,548.8487`。
- base win rate：`42.4471%`。
- full-market as-of 覆盖：`71.8335%`。
- stable OOS condition count：`3`。
- stable conditions：`full_market_ai_top8, ai_rank_1_6, account_injured`。

## 条件摘要

| condition                               | candidate_eligible   |   count |       total_pnl |   mean_pnl_lift_vs_base |   win_rate_lift_pp |   oos_positive_fold_count |   oos_test_fold_count |   oos_min_fold_pnl | stable_oos_candidate   |
|:----------------------------------------|:---------------------|--------:|----------------:|------------------------:|-------------------:|--------------------------:|----------------------:|-------------------:|:-----------------------|
| full_market_ai_top8                     | True                 |     349 |     1.95254e+07 |                  2.4811 |            -2.0459 |                         3 |                     3 |        1.3513e+06  | True                   |
| ai_rank_1_6                             | True                 |    1529 |     4.15723e+07 |                  1.2058 |            -3.1403 |                         4 |                     4 |        1.68944e+06 | True                   |
| account_injured                         | True                 |    1450 |     3.40788e+07 |                  1.0423 |            -1.1367 |                         4 |                     4 |        1.2854e+06  | True                   |
| full_market_consensus_top8              | True                 |      91 |     1.2595e+07  |                  6.1381 |             2.6079 |                         2 |                     2 |   739150           | False                  |
| ai_rank_1_9_and_full_market_consensus   | True                 |      91 |     1.2595e+07  |                  6.1381 |             2.6079 |                         2 |                     2 |   739150           | False                  |
| ai_rank_1_9_and_account_clean           | True                 |     478 |     1.44394e+07 |                  1.3397 |            -2.2797 |                         2 |                     4 |       -6.31186e+06 | False                  |
| ai_rank_1_3                             | True                 |     730 |     2.12967e+07 |                  1.2938 |             1.6625 |                         3 |                     4 |       -7.36511e+06 | False                  |
| ai_rank_1_9                             | True                 |    2417 |     6.30069e+07 |                  1.1561 |            -0.9494 |                         3 |                     4 |       -1.12538e+06 | False                  |
| ai_rank_1_9_oi_confirm_account_clean    | True                 |     165 |     3.20388e+06 |                  0.8611 |            -7.9016 |                         2 |                     4 |       -5.06114e+06 | False                  |
| account_clean                           | True                 |     689 |     1.10845e+07 |                  0.7135 |            -0.9376 |                         2 |                     4 |       -6.31186e+06 | False                  |
| full_market_simple_top8                 | True                 |     386 |     3.2696e+06  |                  0.3756 |           -13.4315 |                         1 |                     3 |       -6.16082e+06 | False                  |
| ai_oi_account_and_full_market_consensus | True                 |       1 | -1600           |                 -0.071  |           -42.4471 |                         0 |                     1 |    -1600           | False                  |
| loss_streak_0                           | True                 |    1087 |    -2.04843e+06 |                 -0.0836 |            -4.4526 |                         2 |                     4 |       -1.49661e+07 | False                  |
| oi_confirmed                            | True                 |    1036 |    -1.08625e+07 |                 -0.465  |            -8.2772 |                         1 |                     4 |       -1.98623e+07 | False                  |
| ai_rank_1_9_and_oi_confirm              | True                 |     851 |    -1.4285e+07  |                 -0.7444 |           -12.8349 |                         1 |                     4 |       -1.98623e+07 | False                  |
| all_open_trades                         | False                |    2787 |     6.28436e+07 |                  1      |             0      |                         3 |                     4 |       -1.42048e+06 | False                  |
| post_entry_quality_add_passed           | False                |       0 |     0           |                  0      |                    |                         0 |                     0 |                    | False                  |

## 输出

- feature_matrix：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage038_candidate_pit_feature_matrix_audit/rebuilt_c9_stage038_candidate_pit_feature_matrix_audit_feature_matrix_stage038_candidate_pit_feature_matrix_audit_v1.csv`
- condition_summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage038_candidate_pit_feature_matrix_audit/rebuilt_c9_stage038_candidate_pit_feature_matrix_audit_condition_oos_summary_stage038_candidate_pit_feature_matrix_audit_v1.csv`
- fold_summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage038_candidate_pit_feature_matrix_audit/rebuilt_c9_stage038_candidate_pit_feature_matrix_audit_fold_summary_stage038_candidate_pit_feature_matrix_audit_v1.csv`
- feature_coverage：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage038_candidate_pit_feature_matrix_audit/rebuilt_c9_stage038_candidate_pit_feature_matrix_audit_feature_coverage_stage038_candidate_pit_feature_matrix_audit_v1.csv`
- decision：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage038_candidate_pit_feature_matrix_audit/rebuilt_c9_stage038_candidate_pit_feature_matrix_audit_decision_stage038_candidate_pit_feature_matrix_audit_v1.json`
- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage038_candidate_pit_feature_matrix_audit/rebuilt_c9_stage038_candidate_pit_feature_matrix_audit_report_stage038_candidate_pit_feature_matrix_audit_v1.md`

## 反思

- 运行前过拟合反思：否。Stage038 不按收益调参，不写交易规则，只把 Stage037 认定可用的入场前字段做点时矩阵和 OOS 分桶审计。
- 运行后过拟合反思：否。本阶段只报告固定条件的 OOS 表现；如果下一步按本表继续扫 rank/topN/阈值/年份，就是过拟合。
- 运行前继续价值反思：有。用户目标需要 AI 选品识别超高质量信号；在加风险前必须先证明信号不靠未来标签、单年或单 source。
- 运行后继续价值反思：有条件。有稳定候选时只能冻结一个低自由度 proxy 进入 Stage039；没有稳定候选时应回到新信息源或账户外层，而不是继续调参。

## 后续规划和 TODO

- 下一步：`stage039_freeze_one_low_degree_proxy_from_stage038_not_parameter_sweep`。
- 若 stable condition 非空，只允许冻结一个低自由度 Stage039 proxy，不允许扫 rank/topN/阈值。
- 若 stable condition 为空，停止在当前 AI/OI/account 字段上救参，转新外生信息源或账户外层方案。
