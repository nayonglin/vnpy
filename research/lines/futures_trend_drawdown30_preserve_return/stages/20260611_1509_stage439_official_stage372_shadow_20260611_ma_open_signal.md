# Stage439 官方 Stage372/20w 2026-06-11 影子盘

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：2026-06-11 15:09 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：官方实盘 Stage372/20w 日常影子盘与 pending order 审计
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - GitHub `chrism2671/PyTrendFollow`：系统化期货趋势跟随项目，包含合约滚动、历史回测和自动交易框架。
  - arXiv `TrendFolios` 等趋势跟随/动量组合构建材料，作为多资产趋势跟随风险预算背景参考。
- 我的判断：外部资料只说明趋势跟随/CTA 是成熟框架，不能用于今天的执行结论。本次只按本地 `official_live_stage372_20w_recovery_sleeve`、目标日行情闭环和 `active_limit_orders` 审计判断，不引入外部策略代码或参数。

## 本次变更

- 新增脚本：无
- 修改脚本：无
- 删除脚本：无
- 新增参数：无
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：2026-01-01 至 2026-06-11
- 数据更新参数：`--mapping-start 2026-06-01 --bar-start 2026-06-11 --end 2026-06-11`
- 账户规模：200,000
- 成本口径：正常成本，`cost_multiplier=1.0`
- 样本过滤：当前官方 AI 池，最新 `eval_date=2026-05-29`
- 策略/归因口径：`official_live_stage372_20w_recovery_sleeve`，即 `stage526_200k_force95_to80_recovery_sleeve_r080_pc25_maxpos4`

## 结果

- 数据更新：`failed_count=0`，`empty_count=0`，`saved_count=19`，`max_saved_date=2026-06-11`
- 期末权益：205,190
- 总收益：2.5950%
- 最大回撤：-16.3027%
- Sharpe：0.3552
- 总滑点：1,700
- 总交易次数：24
- 胜率：46.6667%（非零日收益胜率）
- 其他关键指标：
  - `deployable_pass=1`
  - `days_over_90pct=0`
  - `days_over_100pct=0`
  - `max_broker10_margin_to_equity_pct=55.1058%`
  - 日报 `target_signal_count=0`，但该字段不是最终执行结论
  - pending order 审计 `pending_order_count=1`
  - `order_api_called_count=0`

## 信号与候选

- 理论待处理单：
  - `MA609.CZCE`，`Long Open`，`volume=10`，理论价 `3026.0`，状态 `Submitting`
- 官方打开候选：
  - `MA.CZCE / MA609.CZCE`，`long_case2`，`candidate_status=opened`
  - AI 池：`allowed=1`，`rank=4`，`score=0.6004425426`，`signal_date=2026-05-29`
  - 计划入场价 `3025.0`，止损价 `2964.5`，止损距离 `60.5`
  - `selected_volume=10`，`projected_total_margin_after=36,300`
- 被拒绝候选：
  - `hc.SHFE / hc2610.SHFE`，`short_case2`，`skip_reason=short_signal_rejected`
- 当前影子持仓：无。目标日末端只有 pending open order，尚未发生下一交易日成交回放。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage659_stage372_2026_ytd_latest_ai_shadow_report_stage659_stage372_2026_ytd_latest_ai_shadow_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage659_stage372_2026_ytd_latest_ai_shadow_decision_stage659_stage372_2026_ytd_latest_ai_shadow_v1.json`
- pending audit summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_shadow_pending_audit_20260611_summary.json`
- orders：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_shadow_pending_audit_20260611_pending_orders.csv`
- daily：无新增单独 daily 文件
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_shadow_pending_audit_20260611_target_entry_candidates.csv`

## 结论

- 本阶段结论：2026-06-11 官方 Stage372/20w 影子盘有一条下一交易时段理论新开动作：开多 `MA609.CZCE` 10 手，理论价 `3026.0`。日报 `signal_plan` 为空是 trade_usage 口径问题，不能据此判定无信号。
- 是否进入下一步：是，但只进入 broker/SimNow 状态闸门和 dry-run 评估；本次未连接 CTP/SimNow，不能直接提交。
- 下一步：若要执行，先刷新券商/SimNow 只读账户与持仓快照，确认风险状态仍 normal、资金与合约信息可用，再跑官方 dry-run gate；任何快照缺失、过期或状态异常都 fail closed。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本次只复跑固定官方配置、更新目标日行情并读取末端 pending order，没有新增参数、没有按结果修改规则，也没有选择性挑窗口。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是。
- 原因：今天再次出现日报 `target_signal_count=0` 但 `active_limit_orders` 有理论动作的情况；继续每日影子盘与 pending 审计有直接执行安全价值。

## 合入建议

- 是否更新本线 `LINE.md`：否，日常复跑不构成路线状态变更。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：否。
