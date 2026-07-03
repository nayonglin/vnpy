# Stage032 公开 raw 种子复水/hash 审计

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-02T08:10:44
- 阶段性质：只读数据工程；引用旧线 raw 种子并重算 hash；不联网、不复制 raw、不回测、不改策略、不连接 CTP、不调用下单
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考交易所公开仓单/排名页面、AKShare 期货数据文档、旧线 Stage091 全量 raw backfill 产物。
- 我的判断：本地旧线 Stage091 raw 若 hash 全量一致，可以作为二期线继续 schema/numeric/right-tail 审计的种子；但不构成策略候选。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage032_public_raw_seed_rehydration_audit.py`
- 新增测试：`tests/test_rebuilt_c9_v2_stage032_public_raw_seed_rehydration.py`
- 新增参数：无交易参数；`asset_mode=upstream_reference_no_copy`。
- 修改参数：无
- 删除参数：无

## 结果

- planned_raw_request_count：`1504`
- seed_ready_count：`1504`
- seed_missing_or_bad_count：`0`
- source_count：`3`
- 决策：`stage032_public_raw_seed_verified_ready_for_schema_binding_no_rule`
- 下一方向：`schema_binding_numeric_parse_and_right_tail_missing_audit`

## 输出文件

- seed_index：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage032_public_raw_seed_rehydration_audit/rebuilt_c9_v2_stage032_public_raw_seed_rehydration_audit_seed_index_stage032_public_raw_seed_rehydration_audit_v1.csv`
- source_summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage032_public_raw_seed_rehydration_audit/rebuilt_c9_v2_stage032_public_raw_seed_rehydration_audit_source_summary_stage032_public_raw_seed_rehydration_audit_v1.csv`
- decision：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage032_public_raw_seed_rehydration_audit/rebuilt_c9_v2_stage032_public_raw_seed_rehydration_audit_decision_stage032_public_raw_seed_rehydration_audit_v1.json`
- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage032_public_raw_seed_rehydration_audit/rebuilt_c9_v2_stage032_public_raw_seed_rehydration_audit_report_stage032_public_raw_seed_rehydration_audit_v1.md`

## 过拟合反思

- 运行前判断：否。Stage032 只做 raw 文件存在性与 hash 复验，不新增收益筛选、阈值、品种方向或交易规则。
- 运行后判断：否。即使 raw 种子全量 ready，也只能说明数据地基可复用；不得把 source ready、schema hash 或命中状态交易化。

## 继续价值反思

- 运行前判断：有。Stage031 已生成 1,504 条请求计划，本阶段确认本地是否已有可复验 raw 种子，避免重复请求交易所。
- 运行后判断：有。若 seed 全量通过，可进入 schema binding、数值解析和右尾缺失安全审计；仍不能直接回测策略。

## 合入建议

- 更新本线 `LINE.md`：是。
- 更新 `research/registry.md`：是。
- 追加根目录 `memory.md/back_log.md`：否，本阶段不是策略候选或重要突破。
