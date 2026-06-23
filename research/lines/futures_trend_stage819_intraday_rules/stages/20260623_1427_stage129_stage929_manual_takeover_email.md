# Stage129 Stage929 手动策略仓接管邮件与 Stage904 监控新鲜度修复

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：2026-06-23 14:27 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：官方实盘自动化报告与执行一致性审计增强；修复 Stage904 在 Stage930 守护循环内过度依赖 10 秒 tick 新鲜度导致的误阻断。
- 是否重要突破：否。属于执行监控和邮件解释修复，不改变策略 alpha、AI 池、手数、止损参数或下单闸门。
- 是否触发A/B：否。本阶段不引入新策略版本，不改变实盘候选。

## 外部调研与判断

- 参考资料：
  - QuantConnect live reconciliation 文档：`https://www.quantconnect.com/docs/v2/writing-algorithms/live-trading/reconciliation`
  - NautilusTrader 文档与事件驱动交易系统设计：`https://nautilustrader.io/`
- 我的判断：实盘和回测一致性不应理解为逐笔成交价完全相同，而应通过同一策略输入、同一信号口径、执行事件账本、broker/shadow 对账和滑点归因来验证。手动补开的策略仓可以进入降风险监控，但必须有清晰接管边界，不能把任意手动仓位静默当成策略仓位。

## 本次变更

- 新增脚本：无
- 修改脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_stage929_official_live_15w_timed_cycle.py`
  - `examples/portfolio_backtesting/run_qmt_roll_stage903_official_live_phase_d_controller.py`
  - `examples/portfolio_backtesting/run_qmt_roll_stage904_official_live_c9_intraday_monitor.py`
- 删除脚本：无
- 新增参数：无命令行参数新增；Stage903 内部为 Stage904 计算 `monitor_max_tick_age_seconds`。
- 修改参数：
  - Stage904 由 Stage903 调用时，监控层 tick 新鲜度从硬限 `10` 秒改为 `max(10, max_controller_cycle_seconds + 15)`，当前为 `45` 秒。
  - Stage931 最终真实报单前重定价仍保持 `10` 秒新鲜 tick 要求，实盘发单口径不放松。
- 删除参数：无

## 回测/归因参数

- 数据区间：验证目标日 `2026-06-22`
- 账户规模：`150,000`
- 成本口径：不适用，本阶段不做收益回测。
- 样本过滤：读取 Stage901 当日 pending open、Stage905 skipped existing broker position、Stage906 broker/shadow 差异、Stage904 盘中监控动作。
- 策略/归因口径：只识别“同日 Stage901 有策略开仓信号、broker 只读成交/持仓可识别、Stage904 显示 entry_day_active=1”的手动策略仓；非策略仓不自动接管。

## 结果

- 期末权益：不适用
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：不适用
- 总交易次数：不适用
- 胜率：不适用
- 其他关键指标：
  - Stage929 新增邮件/报告块：`实盘/回测一致性`
  - 新增字段：策略信号一致、AI池一致、分钟K接入、执行意图一致、实盘仓位一致、实时止损监控、手动策略仓接管、止盈止损接管规则、手动/差异仓位明细。
  - 当前 `rb2610.SHFE` 手动空单识别为手动补开的策略仓：broker `11` 手、shadow `0` 手、成交价 `3125.0`、初始止损 `3133.0`、C9 0.5R 止损 `3129.0`、进展价 `3121.0`。
  - 修复前 Stage904 可因 `tick_age_seconds=21.097` 被 `fresh_tick_missing_or_stale` 阻断；修复后 Stage904 `monitor_action=watch`，`stage847_stop_price=3129.0`，`order_api_called=0`。
  - Stage930 当前 live-real daemon 已在新循环里读取新代码，Stage903 调用 Stage904 时传入 `--max-tick-age-seconds 45`。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage929_official_live_15w_timed_cycle_report_manual_20260622_20260623_142218_stage929_official_live_15w_timed_cycle_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage929_official_live_15w_timed_cycle_summary_manual_20260622_20260623_142218_stage929_official_live_15w_timed_cycle_v1.json`
- latest report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_live_15w_timed_cycle_latest_report.md`
- orders：不适用
- daily：不适用
- quality：`py_compile` 通过；`git diff --check` 通过。

## 手动策略仓接管规则

- 当日策略信号匹配、broker 只读成交/持仓能识别、Stage904 已经能算出 entry-day C9 状态时，C9 0.5R 实时止损可以由 Stage904/905/931 close-only 链路自动执行。
- 真实报单前仍由 Stage931 做最终盘口重定价和 10 秒 fresh tick 检查；若最终 tick 不新鲜，仍 fail-closed，不沿用旧价硬发。
- 日线级止盈、日线级止损、常规策略退出在 broker/shadow 未对齐时不静默接管，必须等待对齐或显式接管确认。
- 非策略手动仓位不自动进入策略止盈止损，避免把主观仓位误当成策略仓位。

## 结论

- 本阶段结论：已把用户关心的“手动补开的策略仓是否被实时止损接管”写入 Stage929 邮件。当前 rb 手动空单在新报告中会显示为“当日 C9 实时止损已接管；日线级退出仍需 broker/shadow 对齐”。
- 是否进入下一步：是。下一步应继续观察 Stage930/904 在夜盘和日盘的 real-time stop 行为，并处理 broker/shadow 对齐，避免日线级退出长期处于差异状态。
- 下一步：若发生 C9 实时止损触发，核对 Stage904 action、Stage905 close-only intent、Stage931 final reprice ledger 和 broker 成交回报，形成实盘 TCA 样本。

## 过拟合反思

- 运行前判断：否。本阶段是执行链路和报告解释问题，不是根据收益结果调策略参数。
- 运行后判断：否。改动只改变监控层读取 fresh tick 的容忍窗口和邮件归因展示；真实发单 fresh tick、止损价、风控和策略逻辑不变。
- 原因：Stage930 轮询周期为 30 秒，Stage608 刷新与多 subprocess 串行执行会让 Stage904 看到 10 秒以上但仍可用的最新快照；监控层用 45 秒只是让守护循环语义一致，最终下单仍保留严格 10 秒检查。

## 继续价值反思

- 运行前判断：是。用户已经出现手动补开策略仓的真实场景，如果邮件和监控边界不清，会直接影响是否误以为系统没有风控。
- 运行后判断：是。修复后邮件能直接说明 rb 手动仓是否被 C9 实时止损监控，且发现并修正了一个会导致监控误阻断的时序问题。
- 原因：当前策略已进入实盘自动化阶段，执行一致性、邮件可解释性和 fail-closed 边界比继续调参更关键。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage129 摘要。
- 是否更新 `research/registry.md`：否。未改变研究线归属或状态。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段是实盘自动化质量修复；若后续真实止损触发并成交，再写入重要实盘执行摘要。
