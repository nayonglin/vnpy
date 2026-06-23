# Stage118 Stage930实盘开仓闸门错配修复

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：2026-06-22 21:58 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：实盘执行链路修复 / 只读验证 / 不改策略信号
- 是否重要突破：是。修复 2026-06-22 21:00 有 rb 信号但未自动走到报单 API 的核心闸门错配。
- 是否触发A/B：否。本阶段不改 alpha、参数、品种池、R 倍数、风控比例或回测入口。

## 外部调研与判断

- 参考资料：
  - vn.py `MainEngine.send_order` 只把 `OrderRequest` 交给指定 gateway，不负责我们的账户/持仓/影子盘强对账：https://github.com/vnpy/vnpy/blob/master/vnpy/trader/engine.py
  - vn.py CTA engine 也是构造 `OrderRequest` 后送往 server/gateway，策略侧仍要自管风控边界：https://github.com/vnpy/vnpy_ctastrategy/blob/main/vnpy_ctastrategy/engine.py
  - FIA automated trading risk controls 强调 pre-trade controls、order size/number checks、post-trade analysis 和系统保护：https://www.fia.org/electronic-trading
  - CFTC/Federal Register 对电子交易原则也强调所有电子订单需要交易前风控、测试和可识别来源：https://www.federalregister.gov/documents/2020/07/15/2020-14381/electronic-trading-risk-principles
- 我的判断：
  - 不应该为了避免漏开仓而绕过 broker snapshot、active order、kill switch、final pre-send checks。
  - 但旧 Stage251 是 SimNow/broker-test Phase B 口径，不能作为当前 production-live 开仓的默认硬 blocker。
  - 一手 smoke 是通道级验收/启用前证据，不应该要求每天同 target_date 都重新 smoke，否则每个新交易日都会误挡自动开仓。

## 本次变更

- 新增脚本：无。
- 修改脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_stage902_official_live_phase_d_readiness_gate.py`
  - `examples/portfolio_backtesting/run_qmt_roll_stage903_official_live_phase_d_controller.py`
  - `examples/portfolio_backtesting/run_qmt_roll_stage927_official_live_real_submit_arming_gate.py`
- 删除脚本：无。
- 新增参数：
  - Stage902 新增 `--legacy-stage251-policy {optional,require}`，默认 `optional`。
- 修改参数：
  - Stage902 默认不再要求 executable open 必须通过 Stage251；Stage251 仍可用 `--legacy-stage251-policy require` 显式恢复旧口径。
  - Stage903 周期计划中 Stage251 optional/zero order API 时不再标记 blocked。
  - Stage927 中 Stage925 recovery ack suite 在 Stage924 已显示 `account_recovery_not_required_aligned` 时不再硬阻断。
  - Stage927 中 Stage932 一手 smoke 从同 target_date 硬 blocker 降为 route-level warning。
- 删除参数：无。

## 回测/归因参数

- 数据区间：无新增回测；实盘目标日 `2026-06-22`。
- 账户规模：15万实盘口径。
- 成本口径：不涉及。
- 样本过滤：不涉及。
- 策略/归因口径：C9/15w `official_live_stage847_c9_15w_stage819_05r_stop_retry_once`，只修 Phase D 执行闸门。

## 结果

- 期末权益：不涉及，本阶段未跑策略回测。
- 总收益：不涉及。
- 最大回撤：不涉及。
- Sharpe：不涉及。
- 总滑点：不涉及。
- 总交易次数：不涉及。
- 胜率：不涉及。
- 其他关键指标：
  - `py_compile` 通过。
  - `git diff --check` 通过。
  - 21:55 单跑 Stage902：`overall_status=phase_d_ready_for_live_real`，`ready_for_phase_d_real=1`，`blocking_failure_count=0`，`stage260_executable_count=1`，`legacy_stage251_policy=optional`，`stage251_required=0`，`order_api_called_count=0`。
  - 21:55 单跑 Stage927：Stage925 不再阻断，Stage932 只剩 `warn`；当前仍 blocked 是因为 broker/shadow divergence、controller no-ready 和 fail-closed incident，符合“已手动开仓后禁止重复开仓”的预期。
  - 21:56 重启 night-session 后首轮 Stage930：`daemon_running`，`stage902_overall_status=phase_d_ready_for_live_real`，`stage902_blocking_failure_count=0`，`stage905_executor_status=executor_no_ready_intents`，`stage905_ready_count=0`，`stage905_blocked_count=0`，`stage906_reconciliation_status=reconcile_divergent_fail_closed`，`order_api_called_count=0`。
  - 21:56 Stage905 intents：rb2610.SHFE short/open 计划单被标记为 `skipped_existing_broker_position`，避免对用户手机成交的 11 手 rb 空单重复开仓。

## 输出文件

- report：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage902_official_live_phase_d_readiness_gate_report_20260622_stage902_official_live_phase_d_readiness_gate_v1.md`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage927_official_live_real_submit_arming_gate_report_20260622_stage927_official_live_real_submit_arming_gate_v1.md`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage930_official_live_c9_session_daemon_report_20260622_211459_stage930_official_live_c9_session_daemon_v1.md`
- summary：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage902_official_live_phase_d_readiness_gate_summary_20260622_stage902_official_live_phase_d_readiness_gate_v1.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage927_official_live_real_submit_arming_gate_summary_20260622_stage927_official_live_real_submit_arming_gate_v1.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage930_official_live_c9_session_daemon_summary_20260622_211459_stage930_official_live_c9_session_daemon_v1.json`
- orders：不涉及，真实 order API 调用为 `0`。
- daily：不涉及。
- quality：
  - `py_compile` 通过。
  - `git diff --check` 通过。

## 结论

- 本阶段结论：
  - 2026-06-22 21:00 未自动开仓的主要原因之一已经修复：旧 Stage251 不再作为 production-live 默认开仓硬 blocker。
  - 另一个长期漏开仓风险也已修复：Stage927 不再要求每个 target_date 都有一手 smoke，也不再在 Stage924 无需账户恢复时强制 Stage925。
  - 当前 rb 已经由用户手机成交，系统正确选择不重复开仓，继续监控止损和平仓。
- 是否进入下一步：是。
- 下一步：
  - 继续让 Stage930 夜盘守护运行；若 rb 触发 C9 盘中止损，close-only 通道继续按 Stage931 final pre-send checks 执行。
  - 明天 08:55 launchd 会启动 day-session；09:00 后进入连续竞价才允许真实提交。
  - 下一次账户回到 broker/shadow aligned 且出现新的 Stage905 ready open intent 时，Stage251/Stage925/Stage932 不应再造成“有信号但没有报单 API”的漏开仓。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段只修执行工程闸门，未基于历史盈亏、某品种、某方向或某个交易窗口调整策略参数。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是。
- 原因：这是无人值守实盘执行可靠性的硬问题；即使策略信号正确，闸门错配也会导致漏开仓，必须修到可复验。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：否。本阶段是同一研究线内实盘执行修复。
- 是否追加根目录 `memory.md/back_log.md`：否。先保留在线内阶段记录；若后续首个自动真实开/平仓闭环成功，再追加总账。
