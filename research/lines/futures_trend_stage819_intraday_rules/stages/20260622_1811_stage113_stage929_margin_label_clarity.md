# Stage113 Stage929 保证金口径标签澄清

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：day
- 记录时间：2026-06-22 18:11 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：官方实盘报告链路增强 / 保证金口径澄清
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：兴证期货 2026-05-18 公告显示，rb2610 等合约的公司基准保证金可为套保持仓 `12%`、一般持仓 `13%`；中粮期货同类公告提示具体保证金比例以交易软件“系统/合约信息”查询为准。
- 我的判断：截图中 `rb2610` 最新价约 `3127`、合约乘数 `10`、手机端每手保证金约 `3752`，对应保证金率约 `3752 / (3127 * 10) = 11.996%`，即约 `12%`。Stage901 entry_risk 中的 `margin_ratio=0.1` 是策略/回测/风控静态保证金口径，不是券商实际冻结保证金口径。差异符合预期，但原邮件字段名“每手保证金/预估保证金”容易误导。

## 本次变更

- 新增脚本：无
- 修改脚本：`examples/portfolio_backtesting/run_qmt_roll_stage929_official_live_15w_timed_cycle.py`
- 删除脚本：无
- 新增参数：无
- 修改参数：无
- 删除参数：无
- 变更内容：
  - 邮件和报告字段改名为 `策略保证金率`、`策略预估保证金`、`策略保证金/可用`、`策略每手保证金`。
  - `broker10压力保证金` 改为 `broker10压力保证金合计`，避免误解成每手保证金。
  - 邮件字段说明增加：`策略保证金/止损/风险来自 Stage901 entry_risk；券商实际保证金以交易软件/CTP为准`。

## 回测/归因参数

- 数据区间：不适用，本阶段未跑策略回测。
- 账户规模：C9/15w official live profile。
- 成本口径：不适用。
- 样本过滤：当前 official live 输出文件。
- 策略/归因口径：不改 Stage847-C9-15w 策略，仅改报告字段含义。

## 结果

- 期末权益：不适用
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：不适用
- 总交易次数：不适用
- 胜率：不适用
- 其他关键指标：
  - Stage901 rb 行：`contract_vt_symbol=rb2610.SHFE`，`margin_ratio=0.1`，`margin_per_contract=3127.0`，`actual_margin_amount=34397.0`，`recovery_sleeve_broker_margin_multiplier=1.65`。
  - 手机截图隐含券商保证金率：`3752 / (3127 * 10) ~= 12%`。
  - dry-run 命令：`OFFICIAL_LIVE_EMAIL_DRY_RUN=1 .py311/bin/python examples/portfolio_backtesting/run_qmt_roll_stage929_official_live_15w_timed_cycle.py --phase manual --target-date 2026-06-22 --shadow-refresh-mode plan-only --readonly-refresh-mode plan-only --timeout-seconds 1200`
  - dry-run 邮件：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_live_email_dry_run_20260622_180957_stage929_manual.eml`
  - 解码检查显示正文包含：`策略保证金率：10%`、`策略每手保证金：3,127`、`broker10压力保证金合计：56,755.05`、字段说明已提示券商实际保证金以交易软件/CTP 为准。
  - `order_api_called_count=0`

## 输出文件

- dry-run summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage929_official_live_15w_timed_cycle_summary_manual_20260622_20260622_180931_stage929_official_live_15w_timed_cycle_v1.json`
- dry-run eml：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_live_email_dry_run_20260622_180957_stage929_manual.eml`

## 结论

- 本阶段结论：截图中 `3752` 与策略 `3127` 差异符合预期，前者是券商约 `12%` 实际保证金口径，后者是策略 `10%` 静态保证金口径。为避免误读，Stage929 邮件已明确标注策略口径，并提示券商实际保证金以交易软件/CTP 为准。
- 是否进入下一步：是
- 下一步：若后续要让邮件直接显示券商实际保证金，需要在 CTP 只读快照或合约信息链路里拿到实际保证金率；在拿到之前，不把策略保证金当成实际冻结金额。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段只改报告标签，不改策略、仓位、风控参数、AI 池或下单闸门。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是。
- 原因：保证金口径直接影响用户对可开手数和资金占用的理解，必须在实盘邮件里标清楚。

## 合入建议

- 是否更新本线 `LINE.md`：是
- 是否更新 `research/registry.md`：否
- 是否追加根目录 `memory.md/back_log.md`：否
