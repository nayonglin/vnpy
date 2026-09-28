# Stage001滞后流动性动态换约资格审计

- 决策：`stage001_lagged_liquidity_roll_fail_close_no_label_values`
- 输入路径：56272行/1046个qid
- leg1保留路径：54876行；每qid候选最小/中位/最大：48/52.0/59
- 动态leg：1097520行；换约：26873次；执行事件：162340行
- 映射失败：463路径/3797leg
- 价格质量失败：500路径/52leg
- 一手容量失败：777路径/327事件
- close、收益、标签、fit、predict、回测、CTP、订单和生产写入：全部为0

## 门禁

- `upstream_manifest_gate`：通过
- `source_manifest_gate`：通过
- `input_identity_gate`：通过
- `upstream_decision_gate`：通过
- `frozen_window_gate`：通过
- `daily_mapping_calendar_gate`：通过
- `causal_candidate_selection_gate`：通过
- `candidate_breadth_gate`：通过
- `dynamic_leg_structure_gate`：通过
- `complete_dynamic_mapping_gate`：失败
- `strict_lag_selection_gate`：通过
- `monotone_expiry_coverage_gate`：失败
- `price_observation_quality_gate`：失败
- `execution_event_structure_gate`：失败
- `minimum_one_lot_capacity_gate`：失败
- `identity_gate`：通过
- `zero_side_effect_gate`：通过
