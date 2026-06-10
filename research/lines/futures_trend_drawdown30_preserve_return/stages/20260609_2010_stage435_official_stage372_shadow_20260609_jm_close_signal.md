# Stage435 正式Stage372影子盘20260609焦煤平仓纠错

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-09 20:10 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：官方实盘版本日常影子盘纠错；只读信号复核，不做策略优化。
- 是否重要突破：否。
- 是否触发A/B：否。没有新策略候选、没有接正式版、没有与第78基准组合。

## 外部调研与判断

- 参考资料：
  - 仓库 SOP：`skills/futures-live-execution-sop/SKILL.md`
  - 正式配置：`examples/portfolio_backtesting/qmt_roll_official_live_config.py`
  - 官方交易日历核对：中国金融期货交易所 2026 年休市安排显示端午休市为 `2026-06-19` 至 `2026-06-21`，`2026-06-09` 与 `2026-06-10` 不在节假日休市段。
  - GitHub/外部策略代码：本次不是新策略研究或优化，不引入外部策略代码。
- 我的判断：
  - Stage434 用 `signal_plan` 空表判断“无信号”是误判，因为 `signal_plan` 由 `trade_usage` 中已回放成交生成；在回测截止到 `2026-06-09` 时，`2026-06-09` 收盘刚产生、下一交易时段待成交的平仓不会出现在 `trade_usage`。
  - 对最后一日待执行信号，必须读取策略内部 `trade_event_diagnostics` 或等下一交易日成交回放后再看 `trade_usage`。

## 本次变更

- 新增脚本：无。
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：
  - 数据更新：`--mapping-start 2026-06-01 --bar-start 2026-06-09 --end 2026-06-09`
  - 影子盘：`--target-date 2026-06-09`
  - 纠错复核：同一正式配置重跑只读引擎，读取 `strategy.trade_event_diagnostics`
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：`2026-01-01` 至 `2026-06-09`
- 最新完成数据日：`2026-06-09`
- 账户规模：`200,000`
- 成本口径：正常成本。
- 样本过滤：使用当前月度 AI 池；AI 池最新 `eval_date=2026-05-29`。
- AI 池最新品种：`SA.CZCE, si.GFEX, FG.CZCE, MA.CZCE, OI.CZCE, jm.DCE, AP.CZCE, rb.SHFE, fu.SHFE`
- 策略/归因口径：`stage526_200k_force95_to80_recovery_sleeve_r080_pc25_maxpos4`
- 执行性质：只读影子盘，不连接 CTP，不读取账户，不调用下单 API。

## 结果

- 期末权益：`204,470`
- 总收益：`2.235%`
- 最大回撤：`-16.3027%`
- Sharpe：`0.3314`
- 总滑点：`1,580`
- 总交易次数：`23`
- 胜率：`45.4545%`
- 最大 broker10 保证金/权益：`55.1058%`
- `days_over_90pct`：`0`
- `deployable_pass`：`1`
- 风险状态：`normal`；原因 `official_live_profile_normal`
- 当前理论影子持仓：`jm2609.DCE` 多头 `2` 手，`2026-06-09` 收盘价 `1360.0`，精确保证金 `32,640`
- `signal_plan` 行数：`0`，但该表漏掉最后一日待成交事件。
- 策略内部事件账本确认：
  - 日期：`2026-06-09`
  - 合约：`jm2609.DCE`
  - 产品：`jm.DCE`
  - 原持仓方向：`long`
  - 交易方向：`Short`
  - 开平：`Close`
  - 原因：`long_prev2day_stop`
  - 手数：`2`
  - 理论触发价/记录价：`1360.0`
- 开仓候选账本复核：
  - `2026-06-09` 开仓候选数：`2`
  - `CF.CZCE / CF609.CZCE`：`short_case2`，`candidate_status=skipped`，`skip_reason=short_signal_rejected`
  - `lc.GFEX / lc2609.GFEX`：`short_case2`，`candidate_status=skipped`，`skip_reason=short_signal_rejected`
  - `candidate_status=opened` 数量：`0`
- 订单 API 调用次数：`0`
- CTP/SimNow 账户状态：本次未刷新 broker snapshot；若要执行，必须先确认 broker/SimNow 持有匹配的 `jm2609.DCE` 多头 `2` 手，否则不得发送平仓单。

## 输出文件

- data_update_report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage173_forward_main_contract_data_update_report_stage173_forward_main_contract_data_update_v1.md`
- data_update_summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage173_forward_main_contract_data_update_summary_stage173_forward_main_contract_data_update_v1.json`
- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage659_stage372_2026_ytd_latest_ai_shadow_report_stage659_stage372_2026_ytd_latest_ai_shadow_v1.md`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage659_stage372_2026_ytd_latest_ai_shadow_decision_stage659_stage372_2026_ytd_latest_ai_shadow_v1.json`
- signal_plan：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage659_stage372_2026_ytd_latest_ai_shadow_signal_plan_stage659_stage372_2026_ytd_latest_ai_shadow_v1.csv`
- current_positions：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage659_stage372_2026_ytd_latest_ai_shadow_current_positions_stage659_stage372_2026_ytd_latest_ai_shadow_v1.csv`
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage659_stage372_2026_ytd_latest_ai_shadow_daily_stage659_stage372_2026_ytd_latest_ai_shadow_v1.csv`
- trade_usage：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage659_stage372_2026_ytd_latest_ai_shadow_trade_usage_stage659_stage372_2026_ytd_latest_ai_shadow_v1.csv`

## 结论

- 本阶段结论：Stage434 的“无信号”结论被纠正。正式 Stage372/20万在 `2026-06-09` 收盘后生成了 `jm2609.DCE` 多头 `2` 手平仓信号，原因是 `long_prev2day_stop`；同日没有任何新开仓信号，两个空头候选均因 `short_signal_rejected` 被拒绝。
- 是否进入下一步：进入执行前只读 gate，而不是策略研究或A/B。
- 下一步：
  - 若只是人工盘前检查：今晚应关注并准备平 `jm2609.DCE` 多头 `2` 手；不应新开 `CF.CZCE` 或 `lc.GFEX`。
  - 若进入 SimNow/券商测试执行链：先刷新 broker/SimNow 只读快照；只有确认账户确实持有匹配 `jm2609.DCE` 多头 `2` 手，才允许进入 dry-run / pre-submit gate。若账户为空或持仓不匹配，必须 fail closed，不发送平仓单。
  - 后续应修复 Stage659 的最后一日 `signal_plan` 生成口径，使其合并 `trade_event_diagnostics` 中 target-date 当日待执行事件，避免再次漏报。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本次固定官方版本、固定月度 AI 池、只补行情与复跑日报；纠错是执行信号账本口径问题，不涉及调参或选择窗口。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是。
- 原因：日常影子盘直接决定是否需要交易前闸门；本次发现 `signal_plan` 漏报最后一日待成交平仓信号，说明继续做执行链复核有明确价值。

## 合入建议

- 是否更新本线 `LINE.md`：否。无策略状态变化。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：否。日常执行纠错先记录在本线 stage；若后续修复 Stage659 口径，再视为执行工具修复摘要记录。
