# Stage001换月标签可成交性资格审计

- 决策：`stage001_roll_label_tradeability_fail_close_no_label_values`
- 路径：56272行/1046个qid
- leg：1125440行；执行事件：171264行
- 价格质量失败：777路径/3066leg
- 一手容量失败：1830路径/4063事件
- close、收益、标签、fit、predict、回测、CTP、订单和生产写入：全部为0

## 门禁

- `upstream_manifest_gate`：通过
- `input_identity_gate`：通过
- `upstream_decision_gate`：通过
- `frozen_count_gate`：通过
- `identity_gate`：通过
- `execution_event_structure_gate`：通过
- `fallback_event_coverage_gate`：通过
- `price_observation_quality_gate`：失败
- `minimum_one_lot_capacity_gate`：失败
- `zero_side_effect_gate`：通过
