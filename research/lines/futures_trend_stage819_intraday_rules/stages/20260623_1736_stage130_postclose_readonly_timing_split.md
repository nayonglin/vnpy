# Stage130 post-close 只读检查时序拆分与 15:08 快照任务

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：2026-06-23 17:36 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：官方实盘自动化时序修复；拆分收盘信号报告、日盘收后只读快照、交易时段 fresh gate。
- 是否重要突破：否。属于执行时序与可观测性修复，不改变策略 alpha、AI 池、信号、手数、止损线或真实提交闸门。
- 是否触发A/B：否。

## 外部调研与判断

- 参考资料：
  - 上期所官方交易时间页面显示日盘下午连续竞价到 `15:00`，夜盘品种从上一工作日 `21:00` 开始。
  - 郑商所官方夜盘 FAQ 显示夜盘交易时间为 `21:00-23:30`，夜盘品种交易日从前一工作日夜盘开始至当天 `15:00` 结束。
- 我的判断：用户关于“16:35 可能处在休市/清算，连接交易所或券商前置不稳定”的判断成立。16:35 仍应保留，因为 Stage935/Stage922 的数据 ready 口径是 `16:30`，此时适合做收盘数据、AI池 preflight 和理论信号报告；但不应把 CTP 只读刷新、tick 订阅、盘中监控作为 16:35 邮件的硬依赖。更稳妥的设计是 15:08 尝试日盘收后 broker/contract 只读快照，16:35 发理论信号报告，20:55/交易时段再做 fresh broker/tick/final reprice gate。

## 本次变更

- 新增脚本：无
- 新增 launchd：
  - `examples/portfolio_backtesting/launchd/local.qmt-roll.official-live.15w.day-close-readonly.plist`
- 修改脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_stage903_official_live_phase_d_controller.py`
  - `examples/portfolio_backtesting/run_qmt_roll_stage929_official_live_15w_timed_cycle.py`
  - `examples/portfolio_backtesting/run_qmt_roll_stage930_official_live_c9_session_daemon.py`
  - `examples/portfolio_backtesting/run_qmt_roll_stage934_official_live_automation_health_check.py`
  - `skills/futures-live-automation-startup/SKILL.md`
- 删除脚本：无
- 新增参数：无
- 修改参数/时序：
  - 新增 `15:08` Stage907 production-live read-only refresh 任务，只读刷新账户/持仓/合约快照，不提交订单。
  - Stage929 `post-close` 在 `--readonly-refresh-mode auto` 时，传给 Stage903 的有效模式改为 `plan-only`。
  - Stage903 在非 `market_and_execution` 时段，`--readonly-refresh-mode auto` 不再触发 Stage907 refresh。
  - Stage903 在非 `market_and_execution` 时段，Stage608 临近 tick 刷新强制 `skip`，Stage904 返回 `intraday_monitor_skipped_outside_market_session`。
  - Stage930 守护进程自身在非 `market_and_execution` 时段，也跳过独立 Stage608 tick refresh，避免盘后后台循环再次连接 CTP。
- 删除参数：无

## 回测/归因参数

- 数据区间：不适用
- 账户规模：`150,000`
- 成本口径：不适用
- 样本过滤：不适用
- 策略/归因口径：不改策略，只调整执行检查发生的时段和报告语义。

## 结果

- 期末权益：不适用
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：不适用
- 总交易次数：不适用
- 胜率：不适用
- 其他关键指标：
  - `local.qmt-roll.official-live.15w.day-close-readonly` 已安装到 `/Users/bytedance/Library/LaunchAgents/` 并 `launchctl bootstrap/enable` 成功。
  - `launchctl print` 显示新 label loaded，触发时间 `15:08`，环境变量 `OFFICIAL_LIVE_PHASE_D_READONLY_REFRESH_ENABLED=1`。
  - Stage934 健康检查通过：`health_status=healthy_stage930_live_real_daemon_running_submit_blocked`，blockers/warnings 均为空，新 `readonly_launchd.day_close_readonly` 已被纳入检查。
  - Stage929 post-close 验证：`requested_readonly_refresh_mode=auto`，`effective_readonly_refresh_mode=plan-only`，`order_api_called_count=0`。
  - 最新 Stage903 live-real post_close 验证：`stage907_refresh_status=readonly_refresh_plan_only`、`stage907_refresh_attempted=0`、`stage608_intraday_tick_status=intraday_tick_refresh_skipped_by_mode`、`stage904_monitor_status=intraday_monitor_skipped_outside_market_session`、订单 API `0`。
  - 最新 Stage930 live-real daemon post_close 验证：`tick_refresh=tick_refresh_skipped_outside_market_session`、tick command `[]`、Stage907 `readonly_refresh_plan_only`、Stage608 `intraday_tick_refresh_skipped_by_mode`、Stage904 `intraday_monitor_skipped_outside_market_session`、订单 API `0`。

## 输出文件

- Stage929 验证 summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage929_official_live_15w_timed_cycle_summary_post-close_20260623_20260623_173041_stage929_official_live_15w_timed_cycle_v1.json`
- Stage903 验证 summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage903_official_live_phase_d_controller_summary_20260623_173507_stage903_official_live_phase_d_controller_v1.json`
- Stage930 验证 summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage930_official_live_c9_session_daemon_summary_20260623_173837_stage930_official_live_c9_session_daemon_v1.json`
- Stage934 latest summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage934_official_live_automation_health_check_latest_summary.json`
- launchd repo plist：`examples/portfolio_backtesting/launchd/local.qmt-roll.official-live.15w.day-close-readonly.plist`
- installed plist：`/Users/bytedance/Library/LaunchAgents/local.qmt-roll.official-live.15w.day-close-readonly.plist`

## 结论

- 本阶段结论：16:35 不应再作为 broker/CTP 连接硬检查时点。它保留为收盘数据和理论信号邮件；15:08 新增只读快照尝试；Stage930 后台循环在盘后也不再主动连 CTP 做 tick refresh；20:55/交易时段继续做 fresh broker/tick/final reprice 才能真实提交。
- 是否进入下一步：是。下一步观察明天 15:08 的 Stage907 是否能拿到 broker snapshot，并观察 16:35 邮件是否不再因休市连接失败而把理论信号表达成混乱的 blocked。
- 下一步：如果 15:08 仍拿不到账户/持仓/合约，说明券商前置该时段也不可用；届时保留 15:08 best-effort，但实盘执行仍完全依赖 20:55/08:55 fresh gate。

## 过拟合反思

- 运行前判断：否。这是交易时段与执行检查职责拆分，不涉及策略收益、参数或样本选择。
- 运行后判断：否。改动只影响什么时候尝试 CTP 只读连接，以及 post_close 是否跳过盘中 tick/monitor；真实提交闸门不放松。
- 原因：16:35 连接失败不能作为策略信号失败的证据，应该从报告语义上解耦。

## 继续价值反思

- 运行前判断：是。16:35 邮件被休市 CTP 状态污染，会让用户误判是否有交易信号。
- 运行后判断：是。新时序能把“有无理论信号”和“能否实盘执行”分开，降低误报，并让 20:55/交易时段 fresh gate 继续承担真实提交安全。
- 原因：自动化进入实盘后，时序和状态表达比继续调参更关键。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage130 摘要。
- 是否更新 `research/registry.md`：否。未改变研究线状态或 live profile。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段是执行自动化时序修复，不改变正式策略版本。
