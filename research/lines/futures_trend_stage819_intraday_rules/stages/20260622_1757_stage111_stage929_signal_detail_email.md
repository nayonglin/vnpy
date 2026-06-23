# Stage111 Stage929 交易信号邮件明细补充

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：day
- 记录时间：2026-06-22 17:57 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：官方实盘报告链路增强 / 邮件可读性修复
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：vn.py GitHub 与官方文档中，实盘委托链路以 `OrderRequest` / gateway `send_order` 为核心；公开资料只提供委托接口语义，无法替代本仓库 Stage260/905/927/931 的本地执行闸门和报告细节。
- 我的判断：本次问题本质不是策略信号缺失，而是 Stage929 定时邮件只给出汇总计数，无法直接看到 pending order 的合约、手数、止损和资金占用；应增强报告解释层，不改策略参数、不改报单闸门。

## 本次变更

- 新增脚本：无
- 修改脚本：`examples/portfolio_backtesting/run_qmt_roll_stage929_official_live_15w_timed_cycle.py`
- 删除脚本：无
- 新增参数：无
- 修改参数：无
- 删除参数：无
- 变更内容：
  - Stage929 读取 Stage901 pending orders、Stage901 entry_risk、Stage260 daily execution gate、Stage905 dry-run intents、只读合约快照，拼出逐信号明细。
  - 邮件 subject 增加首个待处理信号摘要，例如 `rb2610.SHFE short/open 11手`。
  - 邮件正文和 Markdown 报告新增 `交易信号明细`、`风险与资金补充`、`执行闸门` 表格。
  - 补充字段包括品种、合约、方向、开平、手数、委托价、策略入场价、止损价、止损距离、单手风险、总风险、保证金率、预估保证金、占可用资金、合约乘数、最小跳动、每手保证金、broker10 压力保证金、风险/权益、风险/保证金/单笔上限手数、只读闸门、Stage260/905 阻断原因。
  - 修复 `_format_number(decimals=0)` 对整数末尾 `0` 的误删问题，避免合约乘数 `10` 被显示成 `1`。
  - 增加从 `rb2610.SHFE` 兜底解析 `rb.SHFE` 的品种名逻辑。

## 回测/归因参数

- 数据区间：不适用，本阶段未跑策略回测。
- 账户规模：C9/15w official live profile，Stage901 entry_risk 中估算权益 `150000.0`。
- 成本口径：不适用。
- 样本过滤：只读取当前 official live 输出文件。
- 策略/归因口径：不改 Stage847-C9-15w 策略，仅汇总现有 Stage901/260/905 结果。

## 结果

- 期末权益：不适用
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：不适用
- 总交易次数：不适用
- 胜率：不适用
- 其他关键指标：
  - 安全干跑命令：`OFFICIAL_LIVE_EMAIL_DRY_RUN=1 .py311/bin/python examples/portfolio_backtesting/run_qmt_roll_stage929_official_live_15w_timed_cycle.py --phase manual --target-date 2026-06-22 --shadow-refresh-mode plan-only --readonly-refresh-mode plan-only --timeout-seconds 1200`
  - `wrapper_exit_code=0`
  - `order_api_called_count=0`
  - 邮件状态：`dry_run_written`
  - 邮件 subject：`[C9/15w 官方报告][warning] 2026-06-22 待处理=1 可提交=0 下单API=0 rb2610.SHFE short/open 11手`
  - 修正版 post-close 补发命令：`env -u OFFICIAL_LIVE_EMAIL_DRY_RUN .py311/bin/python examples/portfolio_backtesting/run_qmt_roll_stage929_official_live_15w_timed_cycle.py --phase post-close --target-date 2026-06-22 --shadow-refresh-mode plan-only --readonly-refresh-mode plan-only --timeout-seconds 1200`
  - 修正版 post-close 补发状态：`email_status=sent`，`sent_to_count=1`，`order_api_called_count=0`
  - rb 明细：`rb2610.SHFE short open 11手`，委托价 `3126`，策略入场价 `3127`，止损价 `3133`，止损距离 `6`，合约乘数 `10`，单手风险 `60`，总风险 `660`，保证金率 `10%`，预估保证金 `34397`，broker10 压力保证金 `56755.05`，风险/权益 `0.44%`。
  - 执行状态：Stage260 `blocked/readonly_gate_not_passed`，Stage905 `blocked/stage902_blocking_failure_count=1;contract_not_found;stage260_no_executable_open_gate`。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage929_official_live_15w_timed_cycle_report_manual_20260622_20260622_175328_stage929_official_live_15w_timed_cycle_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage929_official_live_15w_timed_cycle_summary_manual_20260622_20260622_175328_stage929_official_live_15w_timed_cycle_v1.json`
- email dry-run：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_live_email_dry_run_20260622_175348_stage929_manual.eml`
- sent report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage929_official_live_15w_timed_cycle_report_post-close_20260622_20260622_175530_stage929_official_live_15w_timed_cycle_v1.md`
- sent summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage929_official_live_15w_timed_cycle_summary_post-close_20260622_20260622_175530_stage929_official_live_15w_timed_cycle_v1.json`
- orders：不适用，订单 API `0`
- daily：不适用
- quality：`.py311/bin/python -m py_compile examples/portfolio_backtesting/run_qmt_roll_stage929_official_live_15w_timed_cycle.py` 通过；`git diff --check -- examples/portfolio_backtesting/run_qmt_roll_stage929_official_live_15w_timed_cycle.py` 通过。

## 结论

- 本阶段结论：Stage929 的 16:35/21:05 定时邮件已能直接展示交易信号和资金/风险/闸门明细；对于今日 rb 信号，邮件正文已经能看出是 `rb2610.SHFE` 空头开仓 `11` 手、止损 `3133`、预估保证金 `34397`，但当前执行闸门仍因只读 broker 快照不可用而 fail-closed。17:55 已按 post-close phase 补发一封修正版 warning 邮件。
- 是否进入下一步：是
- 下一步：等待 20:55 session daemon 真实会话触发；若 CTP 只读刷新成功，继续看 Stage260/905/927/931 是否全部放行。若 21:05 报告邮件仍 warning/block，需要优先修 CTP 只读快照而不是手工追单。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段只增强实盘报告字段与格式化，不改变 AI 池、入场信号、仓位、止损、风控参数或回测样本选择。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是。
- 原因：自动化实盘不是只会下单，还必须让人能快速读懂为什么下/为什么不下；补齐邮件明细能降低误判和手工追单风险。

## 合入建议

- 是否更新本线 `LINE.md`：是
- 是否更新 `research/registry.md`：否，本次不是跨线/正式候选状态变化。
- 是否追加根目录 `memory.md/back_log.md`：否，本次不是策略突破或路线合并。
