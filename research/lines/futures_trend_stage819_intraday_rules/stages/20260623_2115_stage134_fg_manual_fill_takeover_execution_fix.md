# Stage134 FG 手动补仓接管与夜盘执行链路修复

- line_id：futures_trend_stage819_intraday_rules
- 当前模式：day
- 记录时间：2026-06-23 21:15 CST
- 工作区/分支：/Users/bytedance/Desktop/person/vnpy
- 阶段性质：实盘执行事故排查与 fail-closed 误判修复
- 是否重要突破：是
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：未新增外部资料。本阶段是生产执行链路事故排查，证据来自 Stage930/903/905/906/904/934 本地实盘日志、CTP 只读快照、launchd 状态与当前官方 live SOP。
- 我的判断：这次不是 FG 没有策略信号，也不是手数/价格问题，而是执行前 fail-closed 闸门误判。修复应限定在对账、快照刷新、会话启动和手动策略仓接管，不应修改 C9 参数、AI池、手数、止损线或报单价格逻辑。

## 本次变更

- 新增脚本：无。
- 修改脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_stage903_official_live_phase_d_controller.py`
  - `examples/portfolio_backtesting/run_qmt_roll_stage904_official_live_c9_intraday_monitor.py`
  - `examples/portfolio_backtesting/run_qmt_roll_stage906_official_live_reconciliation_worker.py`
  - `examples/portfolio_backtesting/run_qmt_roll_stage930_official_live_c9_session_daemon.py`
  - `examples/portfolio_backtesting/run_qmt_roll_stage934_official_live_automation_health_check.py`
  - `examples/portfolio_backtesting/launchd/local.qmt-roll.official-live.15w.c9-day-session.plist`
  - `examples/portfolio_backtesting/launchd/local.qmt-roll.official-live.15w.c9-night-session.plist`
- 删除脚本：无。
- 新增参数：
  - Stage930 新增 `--require-current-session-name`，day-session 只允许 `day_am/day_pm` 启动，night-session 只允许 `night/late_night` 启动。
- 修改参数：
  - Stage903 只读账户快照刷新从“超过 300 秒才刷新”改为预留执行链路 headroom；当前默认 headroom `90` 秒，年龄超过 `210` 秒即刷新。
- 删除参数：无。

## 回测/归因参数

- 数据区间：2026-06-23 夜盘实盘执行链路。
- 账户规模：15w 当前官方实盘口径。
- 成本口径：不涉及回测成本。
- 样本过滤：只针对当晚 `FG609.CZCE` pending open、`rb2610.SHFE` 已有空仓与 broker 只读快照。
- 策略/归因口径：`official_live_stage847_c9_15w_stage819_05r_stop_retry_once`，只改执行接管与安全闸门。

## 结果

- 期末权益：不涉及。
- 总收益：不涉及。
- 最大回撤：不涉及。
- Sharpe：不涉及。
- 总滑点：不涉及。
- 总交易次数：不涉及。
- 胜率：不涉及。
- 其他关键指标：
  - 20:55 night-session 曾因旧 day-session 持有单例锁而退出，旧 day-session 仍在 21:01 看到了 FG。
  - Stage905 在 21:01 已生成 `FG609.CZCE` 空开 `15` 手、限价 `966` 的 ready intent，但 Stage927 因 Stage906 fail-closed 未放行，Stage931 订单 API `0`。
  - Stage906 原先把 shadow 空头 `end_pos=-11` 当成无效仓位丢弃，导致 rb broker 空仓 `11` 被误判为 shadow/broker divergent。
  - Stage903 原先在快照年龄 `265` 秒时不刷新，运行到 Stage906 时超过 `300` 秒导致快照过期。
  - 修复后 Stage906：`reconcile_aligned`，rb `shadow=11/broker=11`，FG `broker=15` 被解释为 `broker_position_matches_stage901_pending_open`，blocking `0`，订单 API `0`。
  - 修复后 Stage905：`executor_no_ready_intents`，FG intent 为 `skipped_existing_broker_position`，broker matching volume `15`，不会重复开仓。
  - 修复后 Stage904：`intraday_monitor_ready`，FG 使用 broker 成交价 `967`、entry_risk 初始止损 `979`，0.5R 止损价 `973`、进展价 `961`；rb 被标记为非当前入场日，不再阻塞监控。
  - 修复后 Stage930/934：已重载 launchd，当前 night label PID `42755` 正常运行，day label not running；Stage934 `health_status=healthy_stage930_live_real_daemon_running_submit_blocked`，top-level blockers/warnings 均为空。submit_blocked 仅因当前无 ready 指令，符合预期。

## 输出文件

- report：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage904_official_live_c9_intraday_monitor_report_20260623_stage904_official_live_c9_intraday_monitor_v1.md`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage906_official_live_reconciliation_worker_report_20260623_stage906_official_live_reconciliation_worker_v1.md`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage934_official_live_automation_health_check_latest_report.md`
- summary：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage930_official_live_c9_session_daemon_summary_20260623_211043_stage930_official_live_c9_session_daemon_v1.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage904_official_live_c9_intraday_monitor_summary_20260623_stage904_official_live_c9_intraday_monitor_v1.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage906_official_live_reconciliation_worker_summary_20260623_stage906_official_live_reconciliation_worker_v1.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage934_official_live_automation_health_check_latest_summary.json`
- orders：不涉及，订单 API `0`。
- daily：不涉及。
- quality：`py_compile`、`plutil -lint`、`git diff --check` 均通过。

## 结论

- 本阶段结论：FG 没自动交易的根因不是无信号，而是执行链路三处问题叠加：Stage906 空头 shadow 负数归一化 bug、Stage903 快照刷新无 headroom、20:55 night label 被错误运行的 day label 单例锁挡住。用户手动开的 FG 已被识别为策略 pending open 的 broker 成仓，系统不会重复开仓，并已恢复 Stage904 入场日实时止损监控。
- 是否进入下一步：是。
- 下一步：继续观察 night-session 后续循环和 Stage929 邮件；若 FG 触发 0.5R 止损，Stage904 应产生 close dry-run，再由 Stage905/931 close-only 通道承接最终重定价和平仓提交。

## 过拟合反思

- 运行前判断：否。排查的是实盘执行一致性和账户对账，不调策略参数。
- 运行后判断：否。本阶段没有改变 C9 alpha、AI池、手数、R 倍数、止损线或回测样本，只修复 live/shadow/broker 对齐和启动时序。
- 原因：所有变更都是让实盘执行更接近既定策略预期，并且保留 fail-closed；没有用当晚价格结果反推交易规则。

## 继续价值反思

- 运行前判断：是。漏开仓和止损不接管会直接破坏全自动实盘可信度。
- 运行后判断：是。修复后当前 FG/rb 已接管且不会重复开仓，后续价值在继续观察自动循环、真实止损触发和邮件可读性。
- 原因：这类问题属于执行工程的基础设施，不修复会让回测和实盘偏离；修复后能降低后续人为补单和漏止损风险。

## 合入建议

- 是否更新本线 `LINE.md`：是，补 Stage134 当前状态。
- 是否更新 `research/registry.md`：否，本阶段不改变研究线总体路线。
- 是否追加根目录 `memory.md/back_log.md`：暂不追加，除非后续观察证明真实止损/平仓通道完整触发。
