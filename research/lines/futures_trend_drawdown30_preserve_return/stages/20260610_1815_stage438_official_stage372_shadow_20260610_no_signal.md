# Stage438 官方 Stage372/20w 2026-06-10 影子盘

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：2026-06-10 18:15 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：官方实盘 Stage372/20w 日常影子盘与 pending order 审计
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - 上海中期期货 2026 年 6 月交易日历，用于确认 2026-06-10 处于正常交易周语境。
  - GitHub `PyTrendFollow` 等通用 futures trend-following 项目，只作为“趋势跟随是成熟 CTA 形态”的背景参照。
- 我的判断：本次是固定官方实盘口径的日常执行检查，不引入外部策略代码或理念；所有执行结论以本地 `official_live_stage372_20w_recovery_sleeve`、目标日行情闭环和 `active_limit_orders` 审计为准。

## 本次变更

- 新增脚本：无
- 修改脚本：无
- 删除脚本：无
- 新增参数：无
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：2026-01-01 至 2026-06-10
- 数据更新参数：`--mapping-start 2026-06-01 --bar-start 2026-06-10 --end 2026-06-10`
- 账户规模：200,000
- 成本口径：正常成本，`cost_multiplier=1.0`
- 样本过滤：当前官方 AI 池，最新 `eval_date=2026-05-29`
- 策略/归因口径：`official_live_stage372_20w_recovery_sleeve`，即 `stage526_200k_force95_to80_recovery_sleeve_r080_pc25_maxpos4`

## 结果

- 数据更新：`failed_count=0`，`empty_count=0`，`saved_count=19`，`max_saved_date=2026-06-10`
- 期末权益：205,190
- 总收益：2.5950%
- 最大回撤：-16.3027%
- Sharpe：0.3569
- 总滑点：1,700
- 总交易次数：24
- 胜率：46.6667%（非零日收益胜率）
- 其他关键指标：
  - `deployable_pass=1`
  - `days_over_90pct=0`
  - `days_over_100pct=0`
  - `max_broker10_margin_to_equity_pct=55.1058%`
  - 日报 `target_signal_count=0`
  - pending order 审计 `pending_order_count=0`
  - `order_api_called_count=0`

## 信号与候选

- 理论待处理单：无
- 目标日平仓事件：无
- 官方新开仓候选：无
- 被拒绝入场候选：无
- 当前影子持仓：无

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage659_stage372_2026_ytd_latest_ai_shadow_report_stage659_stage372_2026_ytd_latest_ai_shadow_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage659_stage372_2026_ytd_latest_ai_shadow_decision_stage659_stage372_2026_ytd_latest_ai_shadow_v1.json`
- pending audit summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_shadow_pending_audit_20260610_summary.json`
- orders：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_shadow_pending_audit_20260610_pending_orders.csv`
- daily：无新增单独 daily 文件
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_shadow_pending_audit_20260610_target_entry_candidates.csv`

## 结论

- 本阶段结论：2026-06-10 官方 Stage372/20w 影子盘无下一交易时段理论动作；`signal_plan` 和 `active_limit_orders` 审计一致为空。
- 是否进入下一步：否，今天没有需要进入 broker/SimNow 持仓确认的理论订单。
- 下一步：继续按日更新行情并复跑影子盘；如后续出现 close/reduce/reconcile 类订单，再先刷新券商/SimNow 只读持仓，账户状态不匹配则 fail closed。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本次只复跑固定官方配置、更新目标日行情并读取末端 pending order，没有新增参数、没有按结果修改规则，也没有选择性挑窗口。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是。
- 原因：2026-06-09 已出现过 `signal_plan` 为空但末端挂单非空的陷阱；今天虽然无信号，但同时确认 `active_limit_orders` 为空，日常影子盘仍有执行安全价值。

## 合入建议

- 是否更新本线 `LINE.md`：否，日常复跑不构成路线状态变更。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：否。
