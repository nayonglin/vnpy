# Stage437 官方 Stage372/20w 2026-06-09 影子盘复跑

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：2026-06-09 20:29 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：官方实盘 Stage372/20w 日常影子盘复跑与 pending order 审计
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - 中金所 2026 年节假日休市安排：端午节为 2026-06-19 至 2026-06-21 休市，2026-06-22 起照常开市。
  - 中信期货 2026 年 6 月交易日历页面显示当前日期 2026-06-09。
- 我的判断：外部资料只用于确认日期语境，策略信号仍完全以本地官方 live config、已更新行情和引擎末端 `active_limit_orders` 为准。本次不是 alpha 研究，不参考或复制 GitHub 策略代码。

## 本次变更

- 新增脚本：无
- 修改脚本：无
- 删除脚本：无
- 新增参数：无
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：2026-01-01 至 2026-06-09
- 数据更新参数：`--mapping-start 2026-06-01 --bar-start 2026-06-09 --end 2026-06-09`
- 账户规模：200,000
- 成本口径：正常成本，`cost_multiplier=1.0`
- 样本过滤：当前官方 AI 池，最新 `eval_date=2026-05-29`
- 策略/归因口径：`official_live_stage372_20w_recovery_sleeve`，即 `stage526_200k_force95_to80_recovery_sleeve_r080_pc25_maxpos4`

## 结果

- 数据更新：`failed_count=0`，`empty_count=0`，`saved_count=19`，`max_saved_date=2026-06-09`
- 期末权益：204,470
- 总收益：2.2350%
- 最大回撤：-16.3027%
- Sharpe：0.3314
- 总滑点：1,580
- 总交易次数：23
- 胜率：45.4545%（非零日收益胜率）
- 其他关键指标：
  - `deployable_pass=1`
  - `max_broker10_margin_to_equity_pct=55.1058%`
  - 日报 `target_signal_count=0`，但该字段不是最终执行结论
  - pending order 审计 `pending_order_count=1`
  - `order_api_called_count=0`

## 信号与候选

- 理论待处理单：
  - `jm2609.DCE`，`Short Close`，`volume=2`，理论价 `1360.0`，原因 `long_prev2day_stop`
- 新开仓候选：
  - 无官方打开候选，`target_opened_candidate_count=0`
- 被拒绝候选：
  - `CF609.CZCE`，`short_case2`，`skip_reason=short_signal_rejected`
  - `lc2609.GFEX`，`short_case2`，`skip_reason=short_signal_rejected`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage659_stage372_2026_ytd_latest_ai_shadow_report_stage659_stage372_2026_ytd_latest_ai_shadow_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage659_stage372_2026_ytd_latest_ai_shadow_decision_stage659_stage372_2026_ytd_latest_ai_shadow_v1.json`
- pending audit summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_shadow_pending_audit_20260609_summary.json`
- orders：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_shadow_pending_audit_20260609_pending_orders.csv`
- daily：无新增单独 daily 文件
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_shadow_pending_audit_20260609_target_entry_candidates.csv`

## 结论

- 本阶段结论：2026-06-09 官方 Stage372/20w 影子盘有一条下一交易时段理论动作：平 `jm2609.DCE` 多头 2 手，价格 1360.0。日报 `signal_plan` 为空是已知 trade_usage 口径遗漏，不能据此判定无信号。
- 是否进入下一步：是，但只进入 broker/SimNow 持仓确认闸门，不进入策略优化或 A/B。
- 下一步：若要执行，必须先刷新券商/SimNow 只读持仓；若账户没有匹配的 `jm2609.DCE` 多头 2 手或快照缺失/过期，则 fail closed，不提交平仓单。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本次只复跑固定官方配置、更新目标日行情并读取引擎末端 pending order，没有新增参数、没有按结果调整规则，也没有选择性挑窗口。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是。
- 原因：本次再次验证了只看 `signal_plan` 会漏掉 2026-06-09 的末端平仓挂单；继续每日影子盘有直接执行安全价值。

## 合入建议

- 是否更新本线 `LINE.md`：否，日常复跑不构成路线状态变更。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：否。
