# Stage112 Stage929 手机邮箱纯文本邮件修正

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：day
- 记录时间：2026-06-22 18:04 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：官方实盘报告链路增强 / 邮件正文格式兼容
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：本阶段未新增外部资料；这是手机邮箱正文渲染兼容问题，核心依据是用户反馈与本地 `.eml` 实际正文。
- 我的判断：Markdown 表格适合本地归档报告，不适合直接作为移动端邮件正文。邮件正文应使用普通文本的“字段：值”段落，避免 `| --- |` 这类 Markdown 表格。

## 本次变更

- 新增脚本：无
- 修改脚本：`examples/portfolio_backtesting/run_qmt_roll_stage929_official_live_15w_timed_cycle.py`
- 删除脚本：无
- 新增参数：无
- 修改参数：无
- 删除参数：无
- 变更内容：
  - 新增 `_format_plain_value()` 与 `_plain_signal_block()`，把信号明细按普通文本输出。
  - Stage929 邮件正文从 Markdown 表格改为移动端可读的逐字段文本块。
  - 本地 Markdown report 继续保留 Markdown 表格，作为归档和本机查看用途。

## 回测/归因参数

- 数据区间：不适用，本阶段未跑策略回测。
- 账户规模：C9/15w official live profile。
- 成本口径：不适用。
- 样本过滤：只读取当前 official live 输出文件。
- 策略/归因口径：不改 Stage847-C9-15w 策略，仅调整邮件正文格式。

## 结果

- 期末权益：不适用
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：不适用
- 总交易次数：不适用
- 胜率：不适用
- 其他关键指标：
  - 语法检查：`.py311/bin/python -m py_compile examples/portfolio_backtesting/run_qmt_roll_stage929_official_live_15w_timed_cycle.py` 通过。
  - dry-run 命令：`OFFICIAL_LIVE_EMAIL_DRY_RUN=1 .py311/bin/python examples/portfolio_backtesting/run_qmt_roll_stage929_official_live_15w_timed_cycle.py --phase manual --target-date 2026-06-22 --shadow-refresh-mode plan-only --readonly-refresh-mode plan-only --timeout-seconds 1200`
  - dry-run 邮件：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_live_email_dry_run_20260622_180218_stage929_manual.eml`
  - EML 解码检查：正文不含 `| 品种 |` 或 `| --- |` Markdown 表格，`contains_markdown_pipe_table=False`。
  - 纯文本 post-close 补发命令：`env -u OFFICIAL_LIVE_EMAIL_DRY_RUN .py311/bin/python examples/portfolio_backtesting/run_qmt_roll_stage929_official_live_15w_timed_cycle.py --phase post-close --target-date 2026-06-22 --shadow-refresh-mode plan-only --readonly-refresh-mode plan-only --timeout-seconds 1200`
  - 纯文本 post-close 补发状态：`email_status=sent`，`sent_to_count=1`，`order_api_called_count=0`。

## 输出文件

- dry-run summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage929_official_live_15w_timed_cycle_summary_manual_20260622_20260622_180151_stage929_official_live_15w_timed_cycle_v1.json`
- dry-run eml：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_live_email_dry_run_20260622_180218_stage929_manual.eml`
- sent summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage929_official_live_15w_timed_cycle_summary_post-close_20260622_20260622_180232_stage929_official_live_15w_timed_cycle_v1.json`
- sent report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage929_official_live_15w_timed_cycle_report_post-close_20260622_20260622_180232_stage929_official_live_15w_timed_cycle_v1.md`
- email audit：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_live_email_notifications.ndjson`

## 结论

- 本阶段结论：Stage929 邮件正文已改为普通文本，手机邮箱不需要 Markdown 渲染也能读到 rb 信号、止损、保证金和闸门原因。18:02 已补发纯文本版 post-close warning 邮件；本次只走报告和邮件链路，订单 API 为 `0`。
- 是否进入下一步：是
- 下一步：今晚 21:05 自动报告会沿用纯文本邮件正文；若仍有 rb pending，会直接以普通字段展示。若执行仍 blocked，优先修 CTP 只读快照链路。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段只改邮件展示格式，不改策略参数、品种池、仓位、止损、AI 池或下单闸门。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是。
- 原因：移动端邮件是实盘监控的第一入口，纯文本正文能降低误读和漏读风险。

## 合入建议

- 是否更新本线 `LINE.md`：是
- 是否更新 `research/registry.md`：否
- 是否追加根目录 `memory.md/back_log.md`：否
