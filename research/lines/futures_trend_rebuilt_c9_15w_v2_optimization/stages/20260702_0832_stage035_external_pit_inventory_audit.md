# Stage035 外部 PIT 数据源库存审计

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-02T08:32:08
- 阶段性质：只读数据源库存审计；不回测、不改策略、不连接 CTP、不调用下单
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考 order-flow/depth/MBO、商品期权 IV/skew、vn.py OptionMaster/执行事件链相关资料。
- 我的判断：这些是比当前公开 raw/分钟/OI 更接近“高质量信号”的信息层，但必须先有 PIT 历史、schema、license、hash 和覆盖；研究产物、分钟补数缓存、smoke/read-only 文件和受保护实盘日志都不能替代。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage035_external_pit_inventory_audit.py`
- 新增测试：`tests/test_rebuilt_c9_v2_stage035_external_pit_inventory_audit.py`
- 新增输出：inventory、route_summary、decision、report
- 新增参数：无交易参数；只有文件分类口径。
- 修改参数：无
- 删除参数：无

## 结果

- decision：`stage035_external_pit_inventory_no_local_rule_candidate`
- best_next_direction：`external_data_or_account_outer_layer`
- route_count：`4`
- schema_candidate_file_count：`0`
- accepted_same_source_replay_file_count：`0`
- protected_live_log_count：`3`
- immediate_strategy_candidate_count：`0`
- 策略变更：`False`
- true engine：`False`
- order API：`0`

## 输出文件

- inventory：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage035_external_pit_inventory_audit/rebuilt_c9_v2_stage035_external_pit_inventory_audit_inventory_stage035_external_pit_inventory_audit_v1.csv`
- route_summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage035_external_pit_inventory_audit/rebuilt_c9_v2_stage035_external_pit_inventory_audit_route_summary_stage035_external_pit_inventory_audit_v1.csv`
- decision：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage035_external_pit_inventory_audit/rebuilt_c9_v2_stage035_external_pit_inventory_audit_decision_stage035_external_pit_inventory_audit_v1.json`
- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage035_external_pit_inventory_audit/rebuilt_c9_v2_stage035_external_pit_inventory_audit_report_stage035_external_pit_inventory_audit_v1.md`

## 过拟合反思

- 运行前判断：否。Stage035 只盘点外部 PIT 数据源，不扫收益阈值、不新增交易规则。
- 运行后判断：否。输出继续阻止把研究产物、分钟补数或实盘日志误当成可交易特征。

## 继续价值反思

- 运行前判断：有。Stage034 后公开 raw 路线已停止，必须确认是否存在 orderflow/执行回放/期权链等新 PIT 输入。
- 运行后判断：有，但如果本地仍没有 schema-ready 外部 PIT 文件，下一步价值来自导入授权数据或转账户外层，不是继续在现有本地文件上救参。

## 合入建议

- 更新本线 `LINE.md`：是。
- 更新 `research/registry.md`：是。
- 追加根目录 `memory.md/back_log.md`：否，除非后续真实 PIT 数据到货并产生可复验候选。
