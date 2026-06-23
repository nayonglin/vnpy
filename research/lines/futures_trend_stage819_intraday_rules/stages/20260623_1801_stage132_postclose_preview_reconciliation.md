# Stage132 16:35盘后预对账

- line_id：futures_trend_stage819_intraday_rules
- 当前模式：day
- 记录时间：2026-06-23 18:01 CST
- 工作区/分支：/Users/bytedance/Desktop/person/vnpy / master
- 阶段性质：实盘自动化执行时序优化
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：本地 `skills/futures-live-execution-sop/SKILL.md`、Stage903/906/929 代码链路、17:58 post-close dry-run 输出。
- 我的判断：本次不是新的 alpha、风控参数或交易规则研究，外部策略资料不应成为依据。第一性原则是把“提前发现 broker/shadow 仓位不一致”和“允许真实下单”彻底分离；16:35 可以用 15:08 的日盘收后只读快照做预警，但不能因此放宽 20:55/交易时段真实提交所需的 fresh 账户、持仓和盘口闸门。

## 本次变更

- 新增脚本：无。
- 修改脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_stage903_official_live_phase_d_controller.py`
  - `examples/portfolio_backtesting/run_qmt_roll_stage906_official_live_reconciliation_worker.py`
  - `examples/portfolio_backtesting/run_qmt_roll_stage929_official_live_15w_timed_cycle.py`
- 删除脚本：无。
- 新增参数：
  - Stage903：`--reconciliation-max-snapshot-age-seconds`，仅用于 Stage906 对账。
  - Stage929：`--post-close-reconcile-snapshot-age-seconds`，默认 `7200` 秒，仅在 `--phase post-close` 生效。
- 修改参数：Stage929 post-close 调 Stage903 时保留 `--max-snapshot-age-seconds 300`，同时额外传入 Stage906-only 的 `7200` 秒预对账窗口。
- 删除参数：无。

## 回测/归因参数

- 数据区间：不涉及回测；目标日 `2026-06-23`。
- 账户规模：当前实盘口径 `150000`。
- 成本口径：不涉及成交成本。
- 样本过滤：不涉及样本。
- 策略/归因口径：只改执行编排和报告展示，不改 Stage901 信号、AI池、手数、止损、Stage260/902/927/931 下单闸门。

## 结果

- 期末权益：不涉及。
- 总收益：不涉及。
- 最大回撤：不涉及。
- Sharpe：不涉及。
- 总滑点：不涉及。
- 总交易次数：不涉及。
- 胜率：不涉及。
- 其他关键指标：
  - `py_compile` 通过。
  - `git diff --check` 通过。
  - Stage929 post-close dry-run 退出码 `0`，`order_api_called_count=0`。
  - Stage929 `effective_readonly_refresh_mode=plan-only`。
  - Stage929 `effective_reconciliation_snapshot_age_seconds=7200`。
  - Stage903 `stage906_max_snapshot_age_seconds=7200`。
  - Stage903 `stage907_effective_refresh_mode=plan-only`。
  - Stage903 `stage608_intraday_tick_status=intraday_tick_refresh_skipped_by_mode`。
  - Stage903 `stage904_monitor_status=intraday_monitor_skipped_outside_market_session`。
  - Stage906 当前仍为 `reconcile_fail_closed_broker_snapshot_unusable`，原因是本次 15:08 只读任务是在今日 15:08 之后新增，今天还没有可用的日盘收后 broker 快照；这不是放行失败，而是正确 fail-closed。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage929_official_live_15w_timed_cycle_report_post-close_20260623_20260623_175828_stage929_official_live_15w_timed_cycle_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage929_official_live_15w_timed_cycle_summary_post-close_20260623_20260623_175828_stage929_official_live_15w_timed_cycle_v1.json`
- orders：不涉及。
- daily：不涉及。
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage903_official_live_phase_d_controller_summary_20260623_175832_stage903_official_live_phase_d_controller_v1.json`

## 结论

- 本阶段结论：可以在 16:35 先做一次对账预警。实现方式是复用 15:08 只读账户/持仓快照，允许 Stage906 在 post-close 报告里接受最长 `7200` 秒快照年龄，用于提前暴露 broker/shadow 是否一致；但 Stage260/902/927/931 的真实下单前置仍要求交易时段 fresh 快照和 fresh tick，不能拿 16:35 预对账结果直接下单。
- 是否进入下一步：进入实际日常观察。
- 下一步：下一次完整交易日先看 15:08 day-close-readonly 是否生成可用 broker 快照，再看 16:35 邮件是否提前显示 rb/FG 等仓位一致性；20:55 仍必须重新刷新 300 秒内账户/持仓/盘口。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：这次没有修改策略信号、阈值、AI池、手数或止损规则，只把执行链路里的对账预警提前；它不会根据某个品种、某天收益或某次信号改变交易行为。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值。
- 原因：20:55 才发现 broker/shadow 不一致会压缩排障时间；16:35 提前预警能把“看问题”和“准备下单”分开，同时保持真实提交 fail-closed，符合自动化实盘的执行纪律。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：否，本次不是跨线状态变化。
- 是否追加根目录 `memory.md/back_log.md`：否，本次是执行流程加固，未改变正式策略版本或核心研究结论。
