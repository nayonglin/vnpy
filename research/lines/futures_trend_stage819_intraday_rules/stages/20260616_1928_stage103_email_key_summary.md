# Stage103 C9/15w实盘邮件关键摘要化

- line_id：futures_trend_stage819_intraday_rules
- 当前模式：day
- 记录时间：2026-06-16 19:28 CST
- 工作区/分支：/Users/bytedance/Desktop/person/vnpy / master
- 阶段性质：官方实盘自动化通知体验优化
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：本阶段不做策略研究，也不改交易信号，未进行新的网上/GitHub 策略调研；依据本地 `skills/futures-live-execution-sop/SKILL.md`、既有邮件脚本与 launchd 自动化链路处理。
- 我的判断：用户现在需要的是实盘操作界面降噪。邮件正文应只承担“我是否要处理”的判断，不应继续承载完整报告、附件正文或本地审计细节；完整文件继续保留在本地审计目录即可。

## 本次变更

- 新增脚本：无
- 修改脚本：
  - `examples/portfolio_backtesting/qmt_roll_official_live_email_notify.py`
  - `examples/portfolio_backtesting/run_qmt_roll_stage929_official_live_15w_timed_cycle.py`
  - `examples/portfolio_backtesting/run_qmt_roll_stage930_official_live_c9_session_daemon.py`
  - `examples/portfolio_backtesting/run_qmt_roll_stage931_official_live_ctp_submit_adapter.py`
  - `examples/portfolio_backtesting/run_qmt_roll_stage932_official_live_ctp_smoke_order.py`
  - `examples/portfolio_backtesting/run_qmt_roll_stage933_official_live_email_notification_check.py`
- 删除脚本：无
- 新增参数：无
- 修改参数：无
- 删除参数：移除邮件 helper 中已无业务作用的 `max_inline_bytes` 配置字段。
- 行为变更：
  - 邮件 helper 固定策略为 `key_summary_only_no_attachments`。
  - 调用方即使传入 report/summary/raw CTP 文件路径，也只写入审计结果，不作为邮件附件，也不把文件正文追加到邮件正文。
  - Stage929/930/931/932/933 邮件正文改为关键摘要：结论、时间/日期、模式、信号/可提交/下单 API 状态、异常或阻断原因、需要用户处理的动作。

## 回测/归因参数

- 数据区间：不适用
- 账户规模：C9/15w 实盘自动化链路
- 成本口径：不适用
- 样本过滤：不适用
- 策略/归因口径：不改 C9 信号、不改下单闸门、不改风控，只改邮件展示层。

## 结果

- 期末权益：不适用
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：不适用
- 总交易次数：不适用
- 胜率：不适用
- 其他关键指标：
  - `py_compile` 通过。
  - Stage933 dry-run 成功生成 `.eml`，配置显示 `attachment_policy=key_summary_only_no_attachments`、`attach_files=0`、`inline_files=[]`。
  - 专项 dry-run 验证传入 `research/registry.md` 作为附件参数时，邮件 MIME 附件数 `0`、内联文件数 `0`、正文仅 `36` 字符。

## 输出文件

- report：不适用
- summary：不适用
- orders：不适用
- daily：不适用
- quality：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_live_email_dry_run_20260616_192522_stage933_email_check.eml`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_live_email_notifications.ndjson`

## 结论

- 本阶段结论：邮件已从“报告型邮件”改为“关键摘要型邮件”。今晚 20:55/21:05 之后新启动的自动化脚本会使用简化后的正文。
- 是否进入下一步：是
- 下一步：若用户仍觉得信息过多，再按事件类型进一步压缩，例如普通无信号邮件只保留“无交易、无需处理、时间”三行。

## 过拟合反思

- 运行前判断：否
- 运行后判断：否
- 原因：本阶段不改策略参数、不筛样本、不影响信号或成交，只改变通知呈现方式。

## 继续价值反思

- 运行前判断：是
- 运行后判断：是
- 原因：实盘自动化最终靠通知闭环降低误判和漏看风险，邮件越接近可执行结论，越适合长期无人值守。

## 合入建议

- 是否更新本线 `LINE.md`：暂不更新；本次只写唯一 stage 文件，避免与并行整理冲突。
- 是否更新 `research/registry.md`：否
- 是否追加根目录 `memory.md/back_log.md`：否
