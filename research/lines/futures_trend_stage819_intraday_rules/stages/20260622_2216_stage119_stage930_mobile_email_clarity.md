# Stage119 Stage930手机邮件可读性修复

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：2026-06-22 22:16 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：实盘通知体验修复 / 不改策略 / 不改报单闸门
- 是否重要突破：否，但属于实盘可操作性必要修复。
- 是否触发A/B：否。

## 外部调研与判断

- 参考资料：
  - Postmark transactional email checklist 强调 clear subject line 和 pre-header/summary。
  - Twilio transactional email guide 强调邮件应包含清晰摘要和下一步。
  - NN/g 邮件可用性资料强调移动端阅读限制，subject 前段需要足够描述性。
- 我的判断：
  - 旧 Stage930 邮件把 `Stage927=0`、`submit_adapter_skipped_not_armed_or_no_ready` 直接发给手机用户，不能回答“有没有下单、为什么没下、我要不要操作”。
  - 盘中守护邮件应该先给操作结论，再给当前信号/仓位、止损状态、下一步自动动作，最后才给内部排查字段。

## 本次变更

- 新增脚本：无。
- 修改脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_stage930_official_live_c9_session_daemon.py`
- 删除脚本：无。
- 新增参数：
  - 新增内部邮件模板版本常量 `EMAIL_CONTENT_VERSION = "stage930_plain_text_v2"`，避免旧 30 分钟 throttle 阻止新版说明邮件发出。
- 修改参数：
  - Stage930 盘中守护邮件 subject 改为人话状态，例如 `[C9/15w][无需操作] 已有rb2610空单11手 不重复开仓`。
  - 邮件 severity 在“已有仓位、不重复开仓、无下单”场景从 `warning` 降为 `info`。
  - 邮件正文改成普通文本结构：结论、当前信号/仓位、盘中止损、下一步、本轮结果、为什么没有下单、排查用内部状态。
- 删除参数：无。

## 回测/归因参数

- 数据区间：不涉及。
- 账户规模：15万实盘口径。
- 成本口径：不涉及。
- 样本过滤：不涉及。
- 策略/归因口径：C9/15w 实盘执行通知，不改策略信号和下单闸门。

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
  - 预览 subject：`[C9/15w][无需操作] 已有rb2610空单11手 不重复开仓`。
  - 预览正文第一屏明确显示：无需操作、本轮没有下单、原计划 rb2610.SHFE 空开 11 手已跳过、券商账户已有空单 11 手、盘中止损正在运行、下一步继续刷新行情/账户/持仓。
  - 22:13 重启 night-session 后新进程 PID `80074` 正在运行。
  - 22:15:09 新版邮件真实发送成功，`email_status=sent`、`severity=info`、`sent_to_count=1`。
  - 22:15:09 Stage930 首轮：`daemon_running`、`cycle_count=1`、`order_api_called_count=0`、Stage904 `intraday_monitor_ready`、Stage905 `executor_no_ready_intents`、Stage902 `phase_d_ready_for_live_real`。

## 输出文件

- report：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage930_official_live_c9_session_daemon_report_20260622_221358_stage930_official_live_c9_session_daemon_v1.md`
- summary：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage930_official_live_c9_session_daemon_summary_20260622_221358_stage930_official_live_c9_session_daemon_v1.json`
- orders：不涉及；真实下单 API 为 `0`。
- daily：不涉及。
- quality：
  - `py_compile` 通过。
  - `git diff --check` 通过。

## 结论

- 本阶段结论：
  - 已修复 Stage930 手机邮件“看不懂”的问题。新版邮件不再把内部 Stage 字段放在第一屏，而是直接说明是否需要操作、为什么不下单、当前 rb 仓位和止损监控状态。
  - 本次只改邮件，不改变自动交易、止损、开仓或对账闸门。
- 是否进入下一步：是。
- 下一步：
  - 继续观察 night-session；若后续有真实下单/止损/异常，邮件也会按同一结构说明“已报单/需关注/异常”。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段是通知文案和状态翻译，不改策略参数、信号、样本或风控比例。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是。
- 原因：实盘自动化必须让手机邮件能直接指导是否人工介入，否则会增加误操作风险。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：否。
