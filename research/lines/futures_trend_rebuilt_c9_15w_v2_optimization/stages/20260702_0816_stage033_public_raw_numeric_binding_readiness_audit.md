# Stage033 公开 raw 数值绑定 readiness 审计

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-02T08:16:24
- 阶段性质：只读数据 readiness；对齐 Stage032 seed 与旧线 Stage095 数值字段；不回测、不改策略、不连接 CTP、不调用下单
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考商品期货库存/basis/会员结构相关公开研究、AKShare 期货数据文档、旧线 Stage093/095 数值解析产物。
- 我的判断：数值字段如果和二期 seed 全量可追溯，可以进入预声明只读信号审计；但仍不构成策略候选。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage033_public_raw_numeric_binding_readiness_audit.py`
- 新增测试：`tests/test_rebuilt_c9_v2_stage033_public_raw_numeric_binding_readiness.py`
- 新增参数：无交易参数。
- 修改参数：无
- 删除参数：无

## 结果

- feature_row_count：`2590`
- numeric_binding_ready_count：`2590`
- present_numeric_ready：`2576/2576`
- right_tail_all_present_numeric_ready：`19/19`
- read_only_signal_audit_allowed_next：`True`
- immediate_strategy_candidate_count：`0`
- 决策：`stage033_public_raw_numeric_binding_ready_for_readonly_signal_audit_no_rule`
- 下一方向：`predeclared_readonly_signal_audit_no_true_engine`

## 输出文件

- binding_rows：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage033_public_raw_numeric_binding_readiness_audit/rebuilt_c9_v2_stage033_public_raw_numeric_binding_readiness_audit_binding_rows_stage033_public_raw_numeric_binding_readiness_audit_v1.csv`
- source_summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage033_public_raw_numeric_binding_readiness_audit/rebuilt_c9_v2_stage033_public_raw_numeric_binding_readiness_audit_source_summary_stage033_public_raw_numeric_binding_readiness_audit_v1.csv`
- field_summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage033_public_raw_numeric_binding_readiness_audit/rebuilt_c9_v2_stage033_public_raw_numeric_binding_readiness_audit_field_summary_stage033_public_raw_numeric_binding_readiness_audit_v1.csv`
- decision：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage033_public_raw_numeric_binding_readiness_audit/rebuilt_c9_v2_stage033_public_raw_numeric_binding_readiness_audit_decision_stage033_public_raw_numeric_binding_readiness_audit_v1.json`
- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage033_public_raw_numeric_binding_readiness_audit/rebuilt_c9_v2_stage033_public_raw_numeric_binding_readiness_audit_report_stage033_public_raw_numeric_binding_readiness_audit_v1.md`

## 过拟合反思

- 运行前判断：否。Stage033 只做二期 seed 与旧线数值绑定结果的可追溯审计，不新增收益阈值或交易规则。
- 运行后判断：否。即使进入只读信号审计，也只能预声明经济语义和固定字段；不得按历史收益直接挑字段、阈值或品种。

## 继续价值反思

- 运行前判断：有。Stage032 证明 raw seed 可复验，本阶段确认数值字段和右尾 lot 是否具备只读信号审计的最低数据条件。
- 运行后判断：有。若本阶段全量通过，下一步可以做预声明 readonly signal audit；仍不能进 true engine 或 A/B。

## 合入建议

- 更新本线 `LINE.md`：是。
- 更新 `research/registry.md`：是。
- 追加根目录 `memory.md/back_log.md`：否，本阶段不是策略候选或重要突破。
