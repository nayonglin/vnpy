# Stage029 下一路线资格审计

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-02T07:52:39
- 阶段性质：只读路线资格审计；不回测、不改策略、不连接 CTP、不调用下单
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考方向：time-series momentum / managed futures、meta-labeling / bet sizing、pysystemtrade 类风险预算框架、GitHub trend-following/backtesting 示例。
- 我的判断：这些资料支持“新 PIT 信息源 + 低自由度 sizing 验证”或“独立稳定 sleeve”，但不支持继续在已反证的 xsmom/OI/仓单/TopN/账户阈值上救参。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage029_next_route_eligibility_audit.py`
- 新增测试：`tests/test_rebuilt_c9_v2_stage029_next_route_eligibility_audit.py`
- 新增参数：无交易参数；仅使用路线分类字段。
- 修改参数：无
- 删除参数：无

## 结果

- route_count：`14`
- immediate_strategy_candidate_count：`0`
- data_acquisition_candidate_count：`2`
- rejected_no_param_rescue_count：`12`
- 决策：`stage029_no_local_unrefuted_route_need_new_pit_or_independent_sleeve`
- 下一方向：`new_pit_source_acquisition_or_independent_sleeve_design`

## 输出文件

- route_inventory：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage029_next_route_eligibility_audit/rebuilt_c9_v2_stage029_next_route_eligibility_audit_route_inventory_stage029_next_route_eligibility_audit_v1.csv`
- family_summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage029_next_route_eligibility_audit/rebuilt_c9_v2_stage029_next_route_eligibility_audit_family_summary_stage029_next_route_eligibility_audit_v1.csv`
- decision：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage029_next_route_eligibility_audit/rebuilt_c9_v2_stage029_next_route_eligibility_audit_decision_stage029_next_route_eligibility_audit_v1.json`
- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage029_next_route_eligibility_audit/rebuilt_c9_v2_stage029_next_route_eligibility_audit_report_stage029_next_route_eligibility_audit_v1.md`

## 过拟合反思

- 运行前判断：否。Stage029 只做冻结证据路线资格审计，不新增交易规则、不按坏窗口调参。
- 运行后判断：否。结论是阻止已反证路线救参；若继续在 xsmom/OI/仓单/TopN/账户阈值上扫相邻参数，就是过拟合。

## 继续价值反思

- 运行前判断：有。Stage028 反证唯一前沿后，必须先决定下一类信息源，否则会在失败字段上空转。
- 运行后判断：有，但下一步价值来自新 PIT 数据或结构不同的独立 sleeve，而不是当前本地字段的阈值救参。

## 合入建议

- 更新本线 `LINE.md`：是。
- 更新 `research/registry.md`：是。
- 追加根目录 `memory.md/back_log.md`：否，本阶段不是正式候选或重要突破，只是路线审计。
