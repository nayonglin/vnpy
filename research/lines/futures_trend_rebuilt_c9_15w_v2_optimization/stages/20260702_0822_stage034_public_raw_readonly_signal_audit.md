# Stage034 公开 raw 只读信号审计

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-02T08:22:51
- 阶段性质：只读信号稳定性审计；不回测、不改策略、不连接 CTP、不调用下单
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考库存/basis/carry、hedging pressure、商品期货理论约束机器学习相关公开资料。
- 我的判断：公开 raw 数值字段有经济语义，但只有通过固定跨年/跨品种/右尾闸门后，才值得做下一步 proxy；本阶段不直接产生策略。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage034_public_raw_readonly_signal_audit.py`
- 新增测试：`tests/test_rebuilt_c9_v2_stage034_public_raw_readonly_signal_audit.py`
- 新增参数：`MIN_CANDIDATE_LOTS=20`、`MIN_CANDIDATE_YEARS=4`、`MIN_CANDIDATE_PRODUCTS=4`；这些是只读样本门槛，不是交易参数。
- 修改参数：无
- 删除参数：无

## 结果

- lot_count：`188`
- readonly_candidate_count：`0`
- immediate_strategy_candidate_count：`0`
- proxy_audit_allowed_next：`False`
- 决策：`stage034_public_raw_readonly_signal_no_stable_candidate_no_rule`
- 下一方向：`stop_public_raw_signal_or_wait_external_data`

## 输出文件

- lot_signal_panel：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage034_public_raw_readonly_signal_audit/rebuilt_c9_v2_stage034_public_raw_readonly_signal_audit_lot_signal_panel_stage034_public_raw_readonly_signal_audit_v1.csv`
- state_summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage034_public_raw_readonly_signal_audit/rebuilt_c9_v2_stage034_public_raw_readonly_signal_audit_state_summary_stage034_public_raw_readonly_signal_audit_v1.csv`
- candidate_summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage034_public_raw_readonly_signal_audit/rebuilt_c9_v2_stage034_public_raw_readonly_signal_audit_candidate_summary_stage034_public_raw_readonly_signal_audit_v1.csv`
- decision：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage034_public_raw_readonly_signal_audit/rebuilt_c9_v2_stage034_public_raw_readonly_signal_audit_decision_stage034_public_raw_readonly_signal_audit_v1.json`
- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage034_public_raw_readonly_signal_audit/rebuilt_c9_v2_stage034_public_raw_readonly_signal_audit_report_stage034_public_raw_readonly_signal_audit_v1.md`

## 过拟合反思

- 运行前判断：否。Stage034 预声明固定经济语义和闸门，不按结果新增阈值、日期、品种或方向。
- 运行后判断：否。输出最多是 readonly candidate；策略规则、true engine、A/B 和订单 API 仍全部禁止。

## 继续价值反思

- 运行前判断：有。Stage033 已证明数值字段 ready，本阶段判断是否有值得继续 proxy 的稳定外生信息。
- 运行后判断：有候选则进入固定 proxy audit；无候选则停止公开 raw 策略化路线，转授权 orderflow/期权链/执行回放。

## 合入建议

- 更新本线 `LINE.md`：是。
- 更新 `research/registry.md`：是。
- 追加根目录 `memory.md/back_log.md`：否，除非下一步 proxy/engine 有重要突破。
