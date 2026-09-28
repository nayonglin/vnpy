# Stage001历史镜像可成交宇宙资格审计

- 决策：`stage001_trailing_horizon_tradeability_fail_close_no_label_values`
- 输入：56272条/1046个qid
- 历史合格并入池：54085条；每qid最小/中位/最大：47/50.0/58
- 未来合格：53738条；不合格：347条
- 未来映射失败：95路径/432leg
- 未来价格失败：131路径/51leg
- 未来容量失败：334路径/248事件
- close、收益、标签、fit、predict、回测、CTP、订单和生产写入：全部为0

## 门禁

- `upstream_manifest_gate`：通过
- `source_manifest_gate`：通过
- `prior_dynamic_manifest_gate`：通过
- `input_identity_gate`：通过
- `upstream_decision_gate`：通过
- `prior_dynamic_identity_gate`：通过
- `frozen_window_gate`：通过
- `trailing_window_structure_gate`：通过
- `daily_mapping_calendar_gate`：通过
- `causal_mapping_candidate_gate`：通过
- `historical_causality_gate`：通过
- `universe_selection_semantics_gate`：通过
- `candidate_breadth_gate`：通过
- `future_leg_structure_gate`：通过
- `future_complete_mapping_gate`：失败
- `future_strict_lag_gate`：通过
- `future_monotone_expiry_gate`：失败
- `future_price_observation_quality_gate`：失败
- `future_execution_event_structure_gate`：失败
- `future_minimum_one_lot_capacity_gate`：失败
- `identity_gate`：通过
- `zero_side_effect_gate`：通过
