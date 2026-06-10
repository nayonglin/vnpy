# Stage436 正式 Stage372 20万影子盘 2026-06-09 JM 平仓信号复跑

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：2026-06-09 20:22 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：正式实盘候选日常影子盘/执行信号检查
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：本次是正式执行链路复跑，不做新 alpha 研究；调研对象为本地 `work-type.txt`、`research/registry.md`、`qmt_roll_official_live_config.py`、本线 `LINE.md`、`skills/futures-live-execution-sop/SKILL.md` 与 `$futures-official-shadow` skill。
- 我的判断：当前正式默认仍是 `official_live_stage372_20w_recovery_sleeve`，20万口径；不能使用 Stage78、Stage653 原版、30万或50万历史入口代替。

## 本次变更

- 新增脚本：无
- 修改脚本：无
- 删除脚本：无
- 新增参数：无
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：`2026-01-01` 至 `2026-06-09`
- 数据更新：Stage173 `mapping_start=2026-06-01`、`bar_start=2026-06-09`、`end=2026-06-09`
- 数据闭环：`saved_count=19`、`failed_count=0`、`empty_count=0`、`max_saved_date=2026-06-09`
- 账户规模：`200000`
- 成本口径：1x 正常成本
- 样本过滤：当前月 AI pool，最新 eval date `2026-05-29`
- 策略/归因口径：`official_live_stage372_20w_recovery_sleeve`，正式 Stage659 + `$futures-official-shadow` pending-order audit

## 结果

- 期末权益：`204,470`
- 总收益：`2.235%`
- 最大回撤：`-16.3027%`
- Sharpe：`0.3314`
- 总滑点：`1,580`
- 总交易次数：`23`
- 胜率：Stage659 当前输出未给总胜率字段；非零日胜率 `45.4545%`
- 其他关键指标：
  - `deployable_pass=1`
  - `days_over_90pct=0`
  - `days_over_100pct=0`
  - `max_broker10_margin_to_equity_pct=55.1058%`
  - Stage659 `target_signal_count=0`
  - pending-order audit `pending_order_count=1`
  - `order_api_called_count=0`

## 今日/今晚信号

- 正式可行动理论单：
  - `jm2609.DCE`
  - 方向：`Short`
  - 开平：`Close`
  - 数量：`2`
  - 理论价：`1360.0`
  - 原因：`long_prev2day_stop`
  - 状态：`Submitting`（回测引擎 pending order）
- 今日开仓候选：
  - 无正式打开的开仓候选，`target_opened_candidate_count=0`
- 被拒绝开仓候选：
  - `CF.CZCE / CF609.CZCE`：`short_case2`，`short_signal_rejected`
  - `lc.GFEX / lc2609.GFEX`：`short_case2`，`short_signal_rejected`
- 解释：`short_case2` 是策略检测到的短侧候选，但当前正式版新开空仓白名单只允许 `short_case1a`；因此这两个不是交易所拒单，也不是 CTP 拒单，而是策略本地规则拒绝。

## 输出文件

- Stage173 summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage173_forward_main_contract_data_update_summary_stage173_forward_main_contract_data_update_v1.json`
- Stage659 summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage659_stage372_2026_ytd_latest_ai_shadow_decision_stage659_stage372_2026_ytd_latest_ai_shadow_v1.json`
- Stage659 report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage659_stage372_2026_ytd_latest_ai_shadow_report_stage659_stage372_2026_ytd_latest_ai_shadow_v1.md`
- Stage659 signal_plan：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage659_stage372_2026_ytd_latest_ai_shadow_signal_plan_stage659_stage372_2026_ytd_latest_ai_shadow_v1.csv`
- pending audit summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_shadow_pending_audit_20260609_summary.json`
- pending orders：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_shadow_pending_audit_20260609_pending_orders.csv`
- target events：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_shadow_pending_audit_20260609_target_events.csv`
- target entry candidates：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_shadow_pending_audit_20260609_target_entry_candidates.csv`

## 结论

- 本阶段结论：2026-06-09 正式 Stage372 20万影子盘，今晚/明早只有 `jm2609.DCE` 的 2 手多头平仓理论信号；无正式开仓信号。
- 执行纪律：这是只读影子盘，没有连接 CTP，没有调用下单接口。若进入 SimNow/实盘执行，必须先读券商/SimNow 持仓；若账户为空仓或没有匹配 JM 多头，必须 fail closed，不能发送平仓单。
- 是否进入下一步：是，若要实际虚拟盘执行，需要继续跑 7x24/SimNow read-only broker snapshot 与 daily execution gate。
- 下一步：仅在用户明确要求执行闸门时，刷新 broker snapshot 并运行 dry-run gate；否则只记录影子盘。

## 过拟合反思

- 运行前判断：否
- 运行后判断：否
- 原因：本次没有修改策略参数、没有选择历史窗口救参，只是用固定正式配置和固定证据优先级检查目标日交易信号。

## 继续价值反思

- 运行前判断：是
- 运行后判断：是
- 原因：本次再次证明单看 Stage659 `signal_plan` 会漏掉目标日最后一根 bar 后的 pending order；继续使用 pending-order audit 有明确执行安全价值。

## 合入建议

- 是否更新本线 `LINE.md`：否，日常影子盘记录即可
- 是否更新 `research/registry.md`：否
- 是否追加根目录 `memory.md/back_log.md`：否
