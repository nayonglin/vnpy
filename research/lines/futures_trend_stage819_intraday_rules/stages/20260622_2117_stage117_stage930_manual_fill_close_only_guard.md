# Stage117 C9/15w 夜盘手动成交后的自动化执行修复

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：day
- 记录时间：2026-06-22 21:17 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：实盘执行事故响应 / Phase D 编排修复
- 是否重要突破：是，修复手动成交后分钟级止损监控与 close-only 降风险通道
- 是否触发A/B：否，本阶段不改 alpha、不改 C9 参数、不做策略候选对比

## 外部调研与判断

- 参考资料：本次为正在运行的本机实盘自动化链路排障，未新增外部网页资料；沿用既有 Phase D/SOP 中关于 vn.py 事件驱动、预交易风控、kill switch、账户/持仓对账和 fail-closed 的执行纪律。
- 我的判断：9 点没有自动交易 rb，不是成交率问题，而是 Stage927/Stage931 按 fail-closed 设计没有放行；用户随后手机手动成交后，系统必须禁止重复开仓，但应允许在 Stage904 触发 0.5R 止损时走只降风险的 close-only 平仓通道。

## 本次变更

- 新增脚本：无。
- 修改脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_stage903_official_live_phase_d_controller.py`
  - `examples/portfolio_backtesting/run_qmt_roll_stage905_official_live_executor_dry_run.py`
  - `examples/portfolio_backtesting/run_qmt_roll_stage906_official_live_reconciliation_worker.py`
  - `examples/portfolio_backtesting/run_qmt_roll_stage930_official_live_c9_session_daemon.py`
  - `examples/portfolio_backtesting/run_qmt_roll_stage931_official_live_ctp_submit_adapter.py`
- 删除脚本：无。
- 新增参数：
  - Stage903：`--intraday-tick-refresh-mode`
  - Stage903：`--intraday-tick-wait-seconds`
  - Stage903：`--intraday-pre-subscribe-wait-seconds`
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：2026-06-22 夜盘实盘运行态。
- 账户规模：150,000。
- 成本口径：不适用。
- 样本过滤：不适用。
- 策略/归因口径：C9/15w `official_live_stage847_c9_15w_stage819_05r_stop_retry_once`，仅执行编排与 broker 快照处理。

## 结果

- 期末权益：不适用。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：不适用。
- 胜率：不适用。
- 其他关键指标：
  - 20:57/20:58/21:00 系统 order API 调用次数均为 `0`，rb 未自动报单。
  - 用户手机手动成交被 CTP 只读快照识别：`rb2610.SHFE` 空开 `11` 手，成交均价 `3125`，成交时间 `2026-06-22 21:01:02`。
  - 修复前 Stage904 因 tick 抓取过早，止损检查时 tick age 约 `82` 秒，触发 `fresh_tick_missing_or_stale` 阻断。
  - 修复后 21:06/21:13/21:16 周期均显示 Stage608 临近 tick 刷新 `readonly_tick_snapshots_received`，Stage904 `intraday_monitor_ready`。
  - CTP 重复仓位回调清洗后，Stage905/906 中 rb broker volume 从误算 `44` 手修正为 `11` 手。
  - 当前最新 21:20 周期：Stage608 只订阅 `rb2610.SHFE`，Stage904 close dry-run `0`，Stage905 `executor_no_ready_intents`，Stage905 blocked `0`，Stage931 未提交，order API `0`。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_live_c9_session_daemon_latest_report.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_live_c9_session_daemon_latest_summary.json`
- orders：不适用，本阶段无真实订单输出。
- daily：不适用。
- quality：`git diff --check` 通过，`py_compile` 通过，内存验证重复仓位清洗与 close-only 判定通过。

## 结论

- 本阶段结论：9 点没有自动开 rb 是预期的 fail-closed 阻断，不是系统偷偷报了没成交；手动成交后系统已能识别 rb 11 手空仓并用 fresh tick 做分钟级监控。已补 close-only 降风险通道：普通开仓仍需要 Stage927 全量放行；若后续 Stage904 触发 0.5R 止损，只允许 Stage904 产生的平仓意图进入 Stage931 最终 broker 持仓/活跃委托/环境变量检查。
- 是否进入下一步：是。
- 下一步：继续观察夜盘守护进程；若 rb 触发止损，立即核对 Stage904 close_dry_run、Stage905 ready、Stage931 order/trade、ledger 与邮件通知。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本次没有修改 C9 的入场、止损 R 倍数、品种池、方向、仓位参数或回测样本，只修复执行时序、重复 broker 回调清洗和降风险平仓通道。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是。
- 原因：当前已进入真实夜盘持仓状态；如果不修复 fresh tick 与 close-only 通道，分钟级止损不会可靠接管手动成交后的 rb 仓位。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Stage117 当前实盘执行修复。
- 是否更新 `research/registry.md`：否，本阶段不改变研究线状态。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段是执行链路修复，不是策略突破或正式候选变更。
