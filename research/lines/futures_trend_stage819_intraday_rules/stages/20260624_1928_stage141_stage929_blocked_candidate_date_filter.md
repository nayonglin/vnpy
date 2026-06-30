# Stage141 Stage929 底层候选日期过滤修复

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：day
- 记录时间：2026-06-24 19:28 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：邮件报告口径修复
- 是否重要突破：否，但属于实盘可读性和误操作风险修复
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：本阶段为本地 Stage929 邮件字段归因与代码修复，主要依据 Stage901 `entry_candidates` 原始文件、Stage929 生成逻辑和 `futures-live-execution-sop` 的执行纪律；未做策略 alpha 外部调研。
- 我的判断：用户截图中的 MA/hc/sp/lc 不是 2026-06-24 当日底层候选，而是 2026-06-18、2026-06-22、2026-06-23 的历史候选。Stage929 原逻辑在目标日无候选时 fallback 到全量 `entry_candidates`，导致历史候选被写进今日邮件；执行层并未把这些历史候选当成今日可执行信号。

## 本次变更

- 新增脚本：无
- 修改脚本：`examples/portfolio_backtesting/run_qmt_roll_stage929_official_live_15w_timed_cycle.py`
- 删除脚本：无
- 新增参数：无
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：2026-06-24 邮件报告
- 账户规模：150000
- 成本口径：未修改
- 样本过滤：Stage929 blocked candidate 明细现在必须匹配 `wrapper.target_date`
- 策略/归因口径：只改邮件展示，不改 Stage901 信号、AI 池、执行闸门、下单逻辑

## 结果

- 期末权益：不适用
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：不适用
- 总交易次数：不适用
- 胜率：不适用
- 其他关键指标：
  - 原始 `entry_candidates` 中截图相关日期：MA `2026-06-18`，hc/lc/rb `2026-06-22`，FG/sp `2026-06-23`
  - 修复后 Stage929 `--target-date 2026-06-24 --email-policy never`：`blocked_candidate_details=[]`
  - 最新报告：`交易信号明细 _empty_`，`底层候选但未成最终交易 _empty_`
  - Stage903/Stage929：`signal_count=0`、`pending_order_count=0`、`stage905_ready_count=0`、订单 API `0`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_live_15w_timed_cycle_latest_report.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_live_15w_timed_cycle_latest_summary.json`
- orders：无
- daily：无
- quality：无

## 结论

- 本阶段结论：用户感觉正确。截图里的“底层候选但未成最终交易”确实不是 2026-06-24 当日候选，而是历史候选被 Stage929 fallback 误展示。已修复为目标日无候选则显示空；未来如果确实有当日候选，会额外展示“报告日期/候选日期”，避免把 AI 池月度日期误解为信号日期。
- 是否进入下一步：是，继续观察下一封 16:35/21:05 邮件。
- 下一步：若下一封邮件仍出现历史候选，检查 Stage901 `entry_candidates` 写入日期和 Stage929 latest summary 是否来自新代码。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段只修邮件日期过滤和字段展示，不改变交易规则、AI池、信号、手数、止损或账户闸门。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是。
- 原因：错误展示历史候选会误导用户以为今天有新机会或过滤信号，影响手工判断和信任；修复后邮件与执行层口径一致。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：否。
