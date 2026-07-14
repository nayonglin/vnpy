# Stage134 tail minute session semantics repair

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-11T18:29:25
- 阶段性质：修复夜盘自然日/交易日验收并原子补数；不回测收益、不改官方 live config、不连接 CTP、不调用下单
- 是否重要突破：否
- 是否触发 A/B：否

## 外部调研与判断

- TqSdk 官方支持 datetime 边界的分钟历史回放；本阶段以 Stage020 实际交易日和 Stage208 固定成交窗口定义数据准入。
- 我的判断：Stage120 的 SHFE 失败是 session 语义 bug，不是行情缺失；不能通过放宽自然日计数解决。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage134_tail_minute_session_semantics_repair.py`
- 新增测试：`tests/test_rebuilt_c9_v2_stage134_tail_minute_session_semantics_repair.py`
- 新增参数：`STAGE134_ENABLE_DOWNLOAD`、`STAGE134_MAX_SECONDS_PER_SYMBOL`
- 修改参数：无正式策略参数修改
- 删除参数：无

## 结果

- decision：`stage134_session_semantics_plan_only`
- planned_contract_count：`6`
- downloaded_status_count：`0`
- temp_strict_ready_count：`0`
- published_or_replaced_count：`0`
- post_publish_strict_ready_count：`35/39`
- jd_margin_history_ready：`False`
- ready_for_no_jd_degraded_replay：`False`
- ready_for_full_stage208_true_ledger：`False`
- 策略变更：`False`
- true engine run：`False`
- order API：`0`
- CTP：`False`

## 回测记录字段

- 本阶段不新增回测，因此不新增期末权益、总收益、最大回撤、Sharpe、滑点、交易次数、胜率。

## 过拟合反思

- 运行前：否。固定修复 session 数据语义，不读取策略收益或按品种绩效筛选。
- 运行后：否。结果只改变数据是否可进入账本，不产生或优化策略绩效。

## 继续价值反思

- 运行前：有。Stage120 的三个 SHFE 失败已定位为可复现的自然日/交易日语义错误。
- 运行后：若 39/39 通过，可进入明确降级的 no-JD Stage208 一次性证伪；含 JD 的正式真账本仍需精确逐日保证金。

## 输出

- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage134_tail_minute_session_semantics_repair/rebuilt_c9_v2_stage134_tail_minute_session_semantics_repair_report_stage134_tail_minute_session_semantics_repair_v1.md`
- decision：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage134_tail_minute_session_semantics_repair/rebuilt_c9_v2_stage134_tail_minute_session_semantics_repair_decision_stage134_tail_minute_session_semantics_repair_v1.json`
- post_publish_audit：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage134_tail_minute_session_semantics_repair/rebuilt_c9_v2_stage134_tail_minute_session_semantics_repair_post_publish_audit_stage134_tail_minute_session_semantics_repair_v1.csv`
