# Stage047 独立收益腿资格闸门

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-02T10:12:58
- 阶段性质：只读候选资格审计；不回测、不改策略、不连接 CTP、不调用下单
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：AQR Demystifying Managed Futures、Moskowitz/Ooi/Pedersen Time Series Momentum、Fuertes/Miffre/Fernandez-Perez commodity momentum/term-structure/idiosyncratic volatility、pysystemtrade diversification multiplier。
- 我的判断：独立收益腿是当前目标继续推进的正确大方向，但只有当前重建 C9 口径、真实引擎、密集多起点目标通过、右尾保留的候选才可晋级；历史旧口径只能作为重建优先级。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage047_independent_sleeve_gate.py`
- 新增测试：`tests/test_rebuilt_c9_v2_stage047_independent_sleeve_gate.py`
- 新增参数：无交易参数
- 修改参数：无正式策略参数修改
- 删除参数：无

## 结果

- decision：`stage047_independent_sleeve_no_current_promotion_rebuild_xsmom_first`
- best_next_rebuild_route：`historical_stage208_xsmom_true_carry`
- candidate_count：`7`
- promotion_candidate_count：`0`
- rebuild_priority_count：`1`
- rejected_no_param_rescue_count：`5`
- immediate_strategy_candidate_count：`0`
- 策略变更：`False`
- true engine：`False`
- order API：`0`
- CTP：`False`

## Gate Table

| candidate_id                              | structure_family                | evidence_scope                              | gate_status                  | promote_now   | needs_current_rebuild   | blocking_reasons                                                                                                                                                                                                                                    | recommended_next_action                                                                    |
|:------------------------------------------|:--------------------------------|:--------------------------------------------|:-----------------------------|:--------------|:------------------------|:----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|:-------------------------------------------------------------------------------------------|
| historical_stage208_xsmom_true_carry      | independent_xsmom_carry_sleeve  | historical_different_baseline               | rebuild_priority             | False         | True                    | historical_different_baseline,current_artifacts_missing_or_not_current,no_current_true_engine_evidence,current_dense_goal_not_passed                                                                                                                | rebuild_current_c9_true_independent_xsmom_sleeve_from_stage020_inputs_before_any_promotion |
| stage021_current_xsmom_curve_overlay      | independent_xsmom_curve_overlay | current_rebuilt_c9                          | rejected_no_param_rescue     | False         | False                   | known_refuted_or_materiality_failed,parameter_rescue_forbidden,no_current_true_engine_evidence,current_dense_goal_not_passed,materiality_not_proven                                                                                                 | do_not_sweep_xsmom_weight_cost_or_lookback                                                 |
| stage022_028_xsmom_confirmation           | xsmom_confirmation_add_risk     | current_rebuilt_c9                          | rejected_no_param_rescue     | False         | False                   | current_true_engine_refuted,parameter_rescue_forbidden,current_dense_goal_not_passed,right_tail_not_preserved                                                                                                                                       | do_not_sweep_confirmation_thresholds_or_rounding                                           |
| historical_stage418_jd_independent_sleeve | jd_independent_sleeve           | historical_different_baseline               | rejected_no_param_rescue     | False         | False                   | known_refuted_or_materiality_failed,parameter_rescue_forbidden,historical_different_baseline,current_artifacts_missing_or_not_current,no_current_true_engine_evidence,current_dense_goal_not_passed,materiality_not_proven                          | keep_independent_risk_slot_as_structure_principle_but_do_not_rescue_jd                     |
| historical_stage420_low_risk_scout_sleeve | low_risk_scout_sleeve           | historical_different_baseline               | rejected_no_param_rescue     | False         | False                   | known_refuted_or_materiality_failed,parameter_rescue_forbidden,historical_different_baseline,current_artifacts_missing_or_not_current,no_current_true_engine_evidence,current_dense_goal_not_passed,materiality_not_proven,right_tail_not_preserved | do_not_continue_low_risk_scout_capital_or_maxpos_sweep                                     |
| upstream_stage073_term_structure          | term_structure_carry            | upstream_current_rebuild_family             | rejected_no_param_rescue     | False         | False                   | known_refuted_or_materiality_failed,parameter_rescue_forbidden,upstream_current_rebuild_family,no_current_true_engine_evidence,current_dense_goal_not_passed,materiality_not_proven,right_tail_not_preserved                                        | do_not_sweep_term_structure_percentiles_or_month_gap                                       |
| futures_range_line_current                | range_reversion                 | separate_line_no_structured_current_history | needs_separate_line_evidence | False         | False                   | separate_line_no_structured_current_history,current_artifacts_missing_or_not_current,no_current_true_engine_evidence,current_dense_goal_not_passed,materiality_not_proven,right_tail_not_preserved                                                  | continue_range_line_inside_its_own_isolation_before_any_combo                              |

## Family Summary

| structure_family                |   candidate_count |   promotion_candidate_count |   rebuild_priority_count |   rejected_count | best_gate_status             | candidate_ids                             |
|:--------------------------------|------------------:|----------------------------:|-------------------------:|-----------------:|:-----------------------------|:------------------------------------------|
| independent_xsmom_carry_sleeve  |                 1 |                           0 |                        1 |                0 | rebuild_priority             | historical_stage208_xsmom_true_carry      |
| independent_xsmom_curve_overlay |                 1 |                           0 |                        0 |                1 | rejected_no_param_rescue     | stage021_current_xsmom_curve_overlay      |
| jd_independent_sleeve           |                 1 |                           0 |                        0 |                1 | rejected_no_param_rescue     | historical_stage418_jd_independent_sleeve |
| low_risk_scout_sleeve           |                 1 |                           0 |                        0 |                1 | rejected_no_param_rescue     | historical_stage420_low_risk_scout_sleeve |
| range_reversion                 |                 1 |                           0 |                        0 |                0 | needs_separate_line_evidence | futures_range_line_current                |
| term_structure_carry            |                 1 |                           0 |                        0 |                1 | rejected_no_param_rescue     | upstream_stage073_term_structure          |
| xsmom_confirmation_add_risk     |                 1 |                           0 |                        0 |                1 | rejected_no_param_rescue     | stage022_028_xsmom_confirmation           |

## 过拟合反思

- 运行前判断：否。本阶段不扫参数，只审计现有独立 sleeve 证据是否足够进入当前 C9 重建验证。
- 运行后判断：否。只有 Stage208 历史 xsmom true-carry 被列为重建优先，不把旧结果当当前候选。

## 继续价值反思

- 运行前判断：有。当前本地字段和外部数据合同都没有立即候选，必须寻找结构不同的独立收益源。
- 运行后判断：有但应聚焦：先复建当前 C9 口径的 true independent xsmom sleeve；若仍失败，则转 forward OOS 或完全独立策略线。

## 输出文件

- candidate_inventory：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage047_independent_sleeve_gate/rebuilt_c9_v2_stage047_independent_sleeve_gate_candidate_inventory_stage047_independent_sleeve_gate_v1.csv`
- gate_table：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage047_independent_sleeve_gate/rebuilt_c9_v2_stage047_independent_sleeve_gate_gate_table_stage047_independent_sleeve_gate_v1.csv`
- family_summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage047_independent_sleeve_gate/rebuilt_c9_v2_stage047_independent_sleeve_gate_family_summary_stage047_independent_sleeve_gate_v1.csv`
- decision：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage047_independent_sleeve_gate/rebuilt_c9_v2_stage047_independent_sleeve_gate_decision_stage047_independent_sleeve_gate_v1.json`
- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage047_independent_sleeve_gate/rebuilt_c9_v2_stage047_independent_sleeve_gate_report_stage047_independent_sleeve_gate_v1.md`
