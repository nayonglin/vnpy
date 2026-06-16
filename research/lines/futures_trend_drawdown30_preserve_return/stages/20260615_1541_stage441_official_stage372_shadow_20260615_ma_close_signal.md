# Stage441 官方 Stage372 影子盘 2026-06-15 MA 平仓信号

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-15 15:41 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：每日官方实盘影子盘 + pending order 审计 + CTP 只读持仓对账
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - 本仓库 `AGENTS.md`
  - `skills/futures-live-execution-sop/SKILL.md`
  - `/Users/bytedance/.codex/skills/futures-official-shadow/SKILL.md`
  - 天勤数据更新脚本输出
- 我的判断：
  - 本次不是新策略研究，不需要外部 GitHub 策略调研；按已冻结官方 Stage372/20w 执行日报 SOP 即可。
  - 不能只看 Stage659 `target_signal_count=0` 或 `signal_plan`，必须按 skill 检查 target-date 后的 `active_limit_orders`。

## 本次变更

- 新增脚本：无
- 修改脚本：无
- 删除脚本：无
- 新增参数：无
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：`2026-01-01` 至 `2026-06-15`
- 账户规模：`200000`
- 成本口径：`1x` 成本为主，同时 Stage659 输出 2x/3x 成本压力
- 样本过滤：当前官方 live profile 固定 AI 池，最新 AI pool `eval_date=2026-05-29`
- 策略/归因口径：`official_live_stage372_20w_recovery_sleeve` / `stage526_200k_force95_to80_recovery_sleeve_r080_pc25_maxpos4`

## 结果

- 期末权益：`182,090`
- 总收益：`-8.955%`
- 最大回撤：`-22.6334%`
- Sharpe：`-0.4430`
- 总滑点：`1,800`
- 总交易次数：`25`
- 胜率：`45.6522%`（非零日胜率）
- 其他关键指标：
  - 数据更新：`saved_count=19`，`failed_count=0`，`empty_count=0`，`max_saved_date=2026-06-15`
  - Stage659 `target_signal_count=0`，但 pending audit 发现 `pending_order_count=1`
  - Pending order：`MA609.CZCE Short Close 10 @ 2770.0`
  - 平仓原因：`long_base_stop`
  - 理论当前持仓：Stage659 报告显示官方 Stage372 当前 `MA609.CZCE long 10`
  - CTP 只读对账：`front/auth/login/settlement/account/position` 全部成功
  - 券商持仓：`MA609` 方向 `2`，总持仓 `10`，今仓 `0`，昨仓 `10`
  - 券商账户：`Balance=149285.67`，`Available=94871.67`，`CurrMargin=54414.0`，`PositionProfit=-25300.0`
  - 订单 API：`send_order_api_called_count=0`，`cancel_order_api_called_count=0`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage659_stage372_2026_ytd_latest_ai_shadow_report_stage659_stage372_2026_ytd_latest_ai_shadow_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage659_stage372_2026_ytd_latest_ai_shadow_decision_stage659_stage372_2026_ytd_latest_ai_shadow_v1.json`
- orders：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_shadow_pending_audit_20260615_pending_orders.csv`
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage659_stage372_2026_ytd_latest_ai_shadow_daily_stage659_stage372_2026_ytd_latest_ai_shadow_v1.csv`
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_shadow_pending_audit_20260615_summary.json`
- CTP account：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage655_readonly_account_margin_probe_accounts_stage655_readonly_account_margin_probe_v1.csv`
- CTP positions：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage655_readonly_account_margin_probe_positions_stage655_readonly_account_margin_probe_v1.csv`

## 结论

- 本阶段结论：
  - 以 `2026-06-15` 完成日线为 target date，明天 `2026-06-16` 对应的下一交易时段有官方理论平仓信号。
  - 信号为 `MA609.CZCE` 多头卖平 `10` 手，理论限价/触发价记录为 `2770.0`，原因 `long_base_stop`。
  - 券商只读持仓与理论平仓方向匹配：当前确有 `MA609` 多头 `10` 手。
  - 本次只是影子盘与只读对账，没有提交任何真实订单。
- 是否进入下一步：可以进入执行前 dry-run / fresh gate；真实平仓必须由用户另行明确授权。
- 下一步：
  - 若用户决定跟随官方信号，下一步应在交易时段前重新拉 fresh CTP 只读快照，再跑平仓 dry-run。
  - 真实提交前必须确认 `ctp_live.local.env` 与 `DYLD_FRAMEWORK_PATH` 使用正式 framework 优先，且再次确认 broker 持仓仍为 `MA609` 多头 `10` 手。

## 过拟合反思

- 运行前判断：否
- 运行后判断：否
- 原因：本阶段只按固定官方 Stage372/20w profile 做每日影子盘和执行对账，不改 alpha、参数、AI 池或风控阈值。

## 继续价值反思

- 运行前判断：是
- 运行后判断：是
- 原因：pending audit 发现了 Stage659 `target_signal_count=0` 单独无法暴露的最终日 active order；继续每日跑有助于避免漏掉明天应处理的平仓。

## 合入建议

- 是否更新本线 `LINE.md`：暂不更新，日常执行记录即可。
- 是否更新 `research/registry.md`：否
- 是否追加根目录 `memory.md/back_log.md`：否，除非后续真实平仓成交或执行失败。
