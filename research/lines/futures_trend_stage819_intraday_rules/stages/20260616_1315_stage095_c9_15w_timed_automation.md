# Stage095 C9/15w 官方自动化定时报告部署

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：`2026-06-16 13:15 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：官方 C9/15w live default 的定时执行与报告部署
- 是否重要突破：是，完成“到点自动跑、晚上看报告”的本机调度闭环
- 是否触发A/B：否，本阶段不改策略参数、不做策略 A/B

## 外部调研与判断

- 参考资料：
  - Apple Developer `Creating Launch Daemons and Agents`：macOS 官方建议用 `launchd`/`launchd.plist` 管理后台任务和日历触发。
  - `launchd.plist(5)` man page：`StartCalendarInterval` 适合指定日历时间触发的用户级任务。
- 我的判断：
  - 今晚目标是“日线完成后自动产出报告”，不是全天候低延迟 tick 执行；因此先用用户级 `launchd` 的两个定时任务，比现在启动一个无限循环常驻进程更稳、更可审计。
  - 对实盘安全而言，真实报单开关不能随自动报告部署一起打开；当前只部署 shadow/read-only/dry-run/report 链路，`OFFICIAL_LIVE_PHASE_D_REAL_SUBMIT_ENABLED` 继续保持关闭。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_stage929_official_live_15w_timed_cycle.py`
  - `examples/portfolio_backtesting/launchd/local.qmt-roll.official-live.15w.postclose.plist`
  - `examples/portfolio_backtesting/launchd/local.qmt-roll.official-live.15w.evening-report.plist`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - Stage929 `--phase {post-close,evening-report,manual}`
  - Stage929 `--target-date`
  - Stage929 `--shadow-refresh-mode {auto,run,plan-only,skip}`
  - Stage929 `--readonly-refresh-mode {auto,run,plan-only,skip}`
  - Stage929 `--timeout-seconds`
  - launchd post-close：每天 `16:35`
  - launchd evening-report：每天 `21:05`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：不适用，本阶段是执行调度部署；手动自检目标日 `2026-06-16`
- 账户规模：`150,000`
- 成本口径：不新增回测
- 样本过滤：不适用
- 策略/归因口径：当前官方 live default `official_live_stage847_c9_15w_stage819_05r_stop_retry_once`，shadow 起点 `2026-06-16`

## 结果

- 期末权益：不适用
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：不适用
- 总交易次数：不适用
- 胜率：不适用
- 其他关键指标：
  - `py_compile` 通过
  - 两个 launchd plist `plutil -lint` 通过
  - Stage929 手动自检：`wrapper_exit_code=0`
  - 自检目标日：`2026-06-16`
  - 自检 `order_api_called_count=0`
  - 自检账户快照：`balance=150000.449813`、`available=150000.449813`、非零持仓行 `0`
  - 自检 Stage903：`phase_d_controller_dry_run_blocked`
  - 自检 Stage909：`shadow_refresh_plan_only`
  - 自检 Stage907：`readonly_refresh_plan_only`
  - 自检 Stage905：`executor_no_intents`
  - 自检 signal rows `1`、pending orders `0`、current positions `0`
  - launchd 已加载：
    - `local.qmt-roll.official-live.15w.postclose`，日历触发 `16:35`
    - `local.qmt-roll.official-live.15w.evening-report`，日历触发 `21:05`
  - Codex 线程心跳已创建：`c9-15w-evening-report-summary`，用于 `21:10` 后读取 latest 报告并在本线程汇总

## 输出文件

- report：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_live_15w_timed_cycle_latest_report.md`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage929_official_live_15w_timed_cycle_report_manual_20260616_20260616_131328_stage929_official_live_15w_timed_cycle_v1.md`
- summary：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_live_15w_timed_cycle_latest_summary.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage929_official_live_15w_timed_cycle_summary_manual_20260616_20260616_131328_stage929_official_live_15w_timed_cycle_v1.json`
- orders：不适用；本阶段未调用订单 API
- daily：不适用
- quality：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_live_15w_timed_cycle_latest_command.log`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage929_launchd_postclose.out.log`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage929_launchd_postclose.err.log`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage929_launchd_evening_report.out.log`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage929_launchd_evening_report.err.log`

## 结论

- 本阶段结论：
  - 不需要现在启动一个无限循环常驻进程；已经用 macOS 用户级 `launchd` 部署两个定时任务。
  - `16:35` 任务负责收盘后自动运行 C9/15w timed cycle；`21:05` 任务负责夜盘前后生成稳定 latest 报告。
  - 当前自动化是 shadow/read-only/dry-run/report 自动化，不是实盘自动报单自动化；真实下单开关仍关闭。
- 是否进入下一步：是
- 下一步：
  - 今晚 `21:05` 后检查 latest 报告和 launchd stdout/stderr。
  - 若要从“自动报告”升级到“无人值守真实报单”，必须另做 live-submit adapter review、Stage927 arming gate、账户/持仓强对账、kill switch 与显式 real-submit 开关确认。

## 过拟合反思

- 运行前判断：否
- 运行后判断：否
- 原因：
  - 本阶段不修改 C9 alpha、不新增交易阈值、不改变 `0.5R`、重试次数、品种池、方向或窗口。
  - 自动化只改变执行与报告时序，不把今晚或近期结果反馈到策略参数。

## 继续价值反思

- 运行前判断：是
- 运行后判断：是
- 原因：
  - 用户需要晚上 9 点后直接看报告，定时执行能减少人工漏跑。
  - 同时保留真实报单 fail-closed，有利于继续推进完全自动化但不牺牲执行安全。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 C9/15w 定时报告已部署
- 是否更新 `research/registry.md`：是，更新当前研究线状态和下一步
- 是否追加根目录 `memory.md/back_log.md`：是，本阶段属于官方实盘自动化部署里程碑
