# Stage100 C9/15w 实盘关键报告与交易邮件通知

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：2026-06-16 14:35 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：实盘自动化可观测性 / 通知链路
- 是否重要突破：是，补齐定时报告、会话守护、真实提交适配器和 smoke 的邮件通知入口
- 是否触发A/B：否，不改策略 alpha 或交易参数

## 外部调研与判断

- 参考资料：Python 官方 `email` examples 与 `smtplib` 文档。官方标准库已覆盖 `EmailMessage`、SMTP/SMTP_SSL、STARTTLS 与附件发送，当前不需要引入第三方邮件 SDK。
- 我的判断：邮件通知应作为执行观测旁路，而不是交易闸门的一部分。邮件失败只能落审计告警，不能阻断或触发下单；SMTP 凭据必须留在本机忽略文件或环境变量中，不能写入仓库、报告或 stage 记录。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/qmt_roll_official_live_email_notify.py`
  - `examples/portfolio_backtesting/run_qmt_roll_stage933_official_live_email_notification_check.py`
  - `examples/portfolio_backtesting/official_live_email.example.env`
- 修改脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_stage929_official_live_15w_timed_cycle.py`
  - `examples/portfolio_backtesting/run_qmt_roll_stage930_official_live_c9_session_daemon.py`
  - `examples/portfolio_backtesting/run_qmt_roll_stage931_official_live_ctp_submit_adapter.py`
  - `examples/portfolio_backtesting/run_qmt_roll_stage932_official_live_ctp_smoke_order.py`
- 删除脚本：无
- 新增参数：
  - `OFFICIAL_LIVE_EMAIL_ENABLED`
  - `OFFICIAL_LIVE_EMAIL_DRY_RUN`
  - `OFFICIAL_LIVE_EMAIL_SMTP_HOST`
  - `OFFICIAL_LIVE_EMAIL_SMTP_PORT`
  - `OFFICIAL_LIVE_EMAIL_USE_SSL`
  - `OFFICIAL_LIVE_EMAIL_STARTTLS`
  - `OFFICIAL_LIVE_EMAIL_SMTP_AUTH`
  - `OFFICIAL_LIVE_EMAIL_SMTP_USER`
  - `OFFICIAL_LIVE_EMAIL_SMTP_PASSWORD`
  - `OFFICIAL_LIVE_EMAIL_FROM`
  - `OFFICIAL_LIVE_EMAIL_TO`
  - `OFFICIAL_LIVE_EMAIL_CC`
  - `OFFICIAL_LIVE_EMAIL_TIMEOUT_SECONDS`
  - `OFFICIAL_LIVE_EMAIL_MAX_ATTACHMENT_BYTES`
  - `OFFICIAL_LIVE_EMAIL_DISABLE_ATTACHMENTS`
  - `OFFICIAL_LIVE_EMAIL_ENV_FILE`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：不适用
- 账户规模：C9/15w 当前官方实盘口径
- 成本口径：不适用
- 样本过滤：不适用
- 策略/归因口径：只改执行通知链路，不改 C9 信号、`0.5R`、重试次数、品种、方向、资金口径或 launchd 触发时间

## 结果

- 期末权益：不适用
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：不适用
- 总交易次数：不适用
- 胜率：不适用
- 其他关键指标：
  - Stage933 config-check：当前 `official_live_email.local.env` 不存在，邮件为默认关闭，缺少 SMTP host/from/to/user/password。
  - Stage933 dry-run：使用临时 dummy env 成功生成 `.eml`，`email_status=dry_run_written`，未连接外部 SMTP。
  - Stage929 manual plan-only 验证：`wrapper_exit_code=0`、`order_api_called_count=0`，邮件状态 `disabled`，不会影响报告链路。
  - Stage931 dry-run/no-intent 验证：`adapter_blocked`、`no_ready_stage905_intents`、`send_order=0`、`cancel_order=0`、`order_api=0`，邮件 `skipped_no_key_event`，避免无信号循环刷屏。
  - Stage930 dry-run/submit disabled/max-cycles=1 验证：`daemon_completed_max_cycles`、`order_api_called_count=0`，无关键事件邮件。
  - launchd 复核：夜盘 `local.qmt-roll.official-live.15w.c9-night-session` 仍为 `--mode live-real --submit-mode live-real`，20:55 触发；`postclose` 16:35 和 `evening-report` 21:05 仍在原触发时间；四个 plist `plutil -lint` 通过。

## 输出文件

- report：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage929_official_live_15w_timed_cycle_report_manual_20260616_20260616_143322_stage929_official_live_15w_timed_cycle_v1.md`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage930_official_live_c9_session_daemon_report_20260616_143449_stage930_official_live_c9_session_daemon_v1.md`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage931_official_live_ctp_submit_adapter_report_20260616_stage931_official_live_ctp_submit_adapter_v1.md`
- summary：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage929_official_live_15w_timed_cycle_summary_manual_20260616_20260616_143322_stage929_official_live_15w_timed_cycle_v1.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage930_official_live_c9_session_daemon_summary_20260616_143449_stage930_official_live_c9_session_daemon_v1.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage931_official_live_ctp_submit_adapter_summary_20260616_stage931_official_live_ctp_submit_adapter_v1.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_live_email_notifications.ndjson`
- orders：不适用，本阶段未提交订单
- daily：不适用
- quality：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_live_email_dry_run_20260616_143313_stage933_email_check.eml`

## 结论

- 本阶段结论：C9/15w 实盘自动化已补上邮件通知旁路。Stage929 每次定时报表都会尝试发报告邮件；Stage930 只在 ready intent、订单 API、submit 异常等关键事件发会话级邮件；Stage931 对真实提交/成交/阻断/异常发订单级明细；Stage932 对实盘 smoke 报撤结果发邮件。邮件配置默认关闭，当前不会真实发送。
- 是否进入下一步：是
- 下一步：
  - 在本机创建 `examples/portfolio_backtesting/official_live_email.local.env`，填 SMTP、发件人、收件人，先保持 `OFFICIAL_LIVE_EMAIL_DRY_RUN=1`。
  - 用 Stage933 dry-run 检查 `.eml` 内容，再用 `send-test` 明确确认后发测试邮件。
  - 通过后把 `OFFICIAL_LIVE_EMAIL_DRY_RUN=0`，16:35/20:55/21:05 既有 launchd 任务会在运行时读取本机 env 文件，无需改 plist。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段只做执行通知和审计日志，不读取回测结果来修改参数，也不改变 C9 的信号、止损、重试、品种、方向或资金口径。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是。
- 原因：实盘自动化的主要风险之一是无人值守时“发生了但不知道”。邮件通知能把定时报告、ready intent、真实订单 API、成交/拒单和 smoke 结果推送到用户侧，提高可观测性和事后对账效率；剩余价值在配置真实 SMTP 和做一次发送验收。

## 合入建议

- 是否更新本线 `LINE.md`：是
- 是否更新 `research/registry.md`：是
- 是否追加根目录 `memory.md/back_log.md`：是，属于 C9/15w 实盘执行自动化重要里程碑
