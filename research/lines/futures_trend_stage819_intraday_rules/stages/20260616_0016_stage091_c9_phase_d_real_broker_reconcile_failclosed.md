# Stage091 C9 Phase D real broker reconcile fail-closed

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：`2026-06-16 00:16 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：C9 官方实盘 Phase D 生产 CTP 只读刷新、真实 broker 对账与 fail-closed 验收
- 是否重要突破：是，首次在 C9 Phase D 链路中拿到 production-live fresh broker 持仓快照，并证明当前真实账户与 C9 shadow 不一致时全链路保持 fail-closed
- 是否触发A/B：否；本阶段不改 alpha、不改 C9 参数、不做策略候选 A/B

## 外部调研与判断

- 参考资料：
  - vn.py `MainEngine.send_order -> gateway.send_order` 真实下单边界。
  - FIA automated trading risk controls 对 pre-trade controls、kill switch、订单/成交对账的要求。
  - CFTC electronic trading risk principles 对电子交易系统异常检测、阻断和风控的要求。
- 我的判断：全自动架构必须把 broker 真实持仓作为执行真相源；当 shadow 与 broker 不一致时，应阻断而不是按理论持仓强行平仓。本阶段结果支持继续推进 Phase D 工程，但不允许打开真实自动报单。

## 本次变更

- 新增脚本：无
- 修改脚本：
  - `examples/portfolio_backtesting/run_ctp_stage174_readonly_probe.py`
  - `examples/portfolio_backtesting/run_qmt_roll_stage260_stage78_1_simnow_daily_execution_gate.py`
  - `examples/portfolio_backtesting/run_qmt_roll_stage903_official_live_phase_d_controller.py`
  - `examples/portfolio_backtesting/run_qmt_roll_stage905_official_live_executor_dry_run.py`
  - `examples/portfolio_backtesting/run_qmt_roll_stage906_official_live_reconciliation_worker.py`
  - `examples/portfolio_backtesting/run_qmt_roll_stage913_official_live_phase_d_completion_audit.py`
- 删除脚本：无
- 新增参数：无
- 修改参数：无
- 删除参数：无
- 关键修正：
  - Stage174 输出 exact duplicate position rows 前去重，并用去重后持仓数生成 broker snapshot。
  - Stage260/905/906 读取 broker positions 时先 exact duplicate 去重，防止 CTP 重复回调把真实仓位放大。
  - Stage260 将“持仓不足”单独标记为 `skip_broker_position_mismatch_for_close`，不再混入空仓 skip。
  - Stage903 汇总新增 `stage260_skipped_position_mismatch_count`。
  - Stage913 将 `broker_state` 与 live-real submit readiness 解耦；fresh 只读快照通过后 broker_state 可单独 passed，真实对账仍由 `reconcile` 决定。

## 回测/归因参数

- 数据区间：当前官方 C9 shadow `2026-01-01 -> 2026-06-12`
- 账户规模：`300000`
- 成本口径：沿用 Stage901 当前 C9 官方 live shadow 输出
- 样本过滤：无新增过滤
- 策略/归因口径：不改策略，只验证 Phase D 生产只读刷新、执行闸门、executor、adapter 与对账

## 结果

- 期末权益：`265,860`（沿用 Stage901 C9 2026 YTD shadow）
- 总收益：`-11.38%`
- 最大回撤：`-14.8955%`
- Sharpe：`-1.1331`
- 总滑点：`3,860`
- 总交易次数：`27`
- 胜率：非零日胜率 `45.7143%`
- 其他关键指标：
  - Stage907 production-live read-only refresh：`readonly_refresh_completed_snapshot_ready`，`order_api_called_count=0`
  - Stage174 fresh broker snapshot：`readonly_snapshots_received`，`positions_received`，去重后持仓文件 `1` 行
  - 真实 broker 持仓：`MA609.CZCE Long 10`
  - C9 shadow 持仓：`MA609.CZCE long 12`
  - Stage260：`executable_count=0`，`skipped_position_mismatch_count=1`，原因 `insufficient_position:10.0000<12.0000`
  - Stage905：`executor_dry_run_blocked`，`ready_count=0`，`blocked_count=1`，原因 `insufficient_broker_position:10.0<12.0;stage260_no_executable_close_gate`
  - Stage906：`reconcile_divergent_fail_closed`，`shadow_volume=12`、`broker_volume=10`、`delta=-2`
  - Stage908：`adapter_contract_blocked`，`live_submit_permitted=0`
  - Stage903：`phase_d_controller_dry_run_blocked`，`order_api_called_count=0`
  - Stage910：`controller_alive_fail_closed`，heartbeat age `9.416` 秒，`order_api_called_count=0`
  - Stage912：`phase_d_acceptance_passed_fail_closed`，`30/30` passed，`order_api_called_count=0`
  - Stage913：`phase_d_completion_not_proven`，passed `9`、partial `5`、incomplete `1`，唯一 blocked 为 `reconcile`
  - Stage916：`phase_d_order_boundary_static_audit_passed`，扫描 `17` 个文件，allowed `send_order` 引用 `2`，disallowed `0`

## 输出文件

- report：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage903_official_live_phase_d_controller_report_20260616_001551_stage903_official_live_phase_d_controller_v1.md`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage913_official_live_phase_d_completion_audit_report_20260616_001615_stage913_official_live_phase_d_completion_audit_v1.md`
- summary：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage907_official_live_readonly_refresh_gate_summary_20260616_001509_stage907_official_live_readonly_refresh_gate_v1.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage903_official_live_phase_d_controller_summary_20260616_001551_stage903_official_live_phase_d_controller_v1.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage910_official_live_phase_d_health_check_summary_20260616_001615_stage910_official_live_phase_d_health_check_v1.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage912_official_live_phase_d_acceptance_suite_summary_20260616_001335_stage912_official_live_phase_d_acceptance_suite_v1.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage913_official_live_phase_d_completion_audit_summary_20260616_001615_stage913_official_live_phase_d_completion_audit_v1.json`
- orders：无真实订单；Stage908 submit batch 为空且 blocked
- daily：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage260_official_live_daily_execution_gate_decisions_20260612_stage260_official_live_daily_execution_gate_v1.csv`
- quality：
  - `py_compile` 通过
  - `git diff --check` 通过
  - Stage912 fail-closed acceptance 通过
  - Stage916 静态订单边界通过

## 结论

- 本阶段结论：C9 Phase D 架构已经具备 signal、broker read-only、execution gate、executor dry-run、adapter boundary、kill switch、heartbeat、mock integration 和 completion audit 的证据链；生产 CTP 只读刷新已成功。但当前不能自动执行 C9 pending 平仓，因为真实 broker 账户只有 `MA609.CZCE Long 10`，而 C9 shadow/pending 要平 `12` 手。正确动作是 fail-closed，不下单。
- 是否进入下一步：是
- 下一步：
  - 先做账户差异归因：为什么 broker 是 10 手而 C9 shadow 是 12 手，是此前人工/旧策略成交、保证金风控、缺失成交回报，还是 shadow 起点与真实账户起点不同。
  - 在差异未解释并形成 reconciliation policy 前，不允许真实自动报单。
  - 后续可增加“reconcile mode”：只允许按 broker 实际持仓生成不超过可用仓的降风险草案，但必须独立人工确认，不纳入无人值守自动提交。

## 过拟合反思

- 运行前判断：否
- 运行后判断：否
- 原因：本阶段只修执行安全、持仓去重和对账审计，不改 C9 策略参数、R 倍数、品种、方向或回测窗口。

## 继续价值反思

- 运行前判断：是
- 运行后判断：是
- 原因：Phase D 的核心工程链路已经基本搭好，当前剩余问题变成真实账户与 shadow 的可解释对账；这是全自动实盘上线前必须解决的高价值问题。

## 合入建议

- 是否更新本线 `LINE.md`：建议后续完成账户差异归因后统一更新。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：否；当前是 fail-closed 风险发现，不是全自动完成或正式上线突破。
