# Stage001 V2换月感知产品标签路径资格审计

- 决策：`stage001_v2_roll_aware_label_plan_fail_close_no_labels`
- 路径：56272行/1046个qid
- 同合约分段：1125440行
- 换月事件：29361
- 失败：return_bar_missing=6
- close值、收益、标签、fit、predict、回测、CTP、订单和生产写入：全部为0

## 门禁

- `upstream_manifest_gate`：通过
- `input_identity_gate`：通过
- `partition_gate`：通过
- `path_identity_gate`：通过
- `complete_path_gate`：失败
- `pit_mapping_gate`：失败
- `bar_presence_gate`：失败
- `canary_gate`：通过
- `zero_side_effect_gate`：通过
