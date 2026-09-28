# Stage001打分日固定实际合约资格审计

- 决策：`stage001_query_date_fixed_contract_fail_close_no_label_values`
- 输入路径：56272行/1046个qid
- 选择路径：54305行；每qid候选最小/中位/最大：48/51.0/58
- 固定leg：1086100行；执行事件：108610行
- 未来价格质量失败：1916路径/6597leg
- 一手容量失败：3437路径/3453事件
- close、收益、标签、fit、predict、回测、CTP、订单和生产写入：全部为0

## 门禁

- `upstream_manifest_gate`：通过
- `source_manifest_gate`：通过
- `input_identity_gate`：通过
- `upstream_decision_gate`：通过
- `frozen_window_gate`：通过
- `causal_selection_gate`：通过
- `expiry_coverage_gate`：通过
- `candidate_breadth_gate`：通过
- `fixed_leg_structure_gate`：通过
- `execution_event_structure_gate`：通过
- `price_observation_quality_gate`：失败
- `minimum_one_lot_capacity_gate`：失败
- `identity_gate`：通过
- `zero_side_effect_gate`：通过
