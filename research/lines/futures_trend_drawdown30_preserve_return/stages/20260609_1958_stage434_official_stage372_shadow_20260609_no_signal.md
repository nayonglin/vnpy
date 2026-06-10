# Stage434 正式Stage372影子盘20260609无信号

> 更正：本记录依据 `signal_plan` 空表得出“无信号”，后续 Stage435 直接读取策略内部 `trade_event_diagnostics` 后确认这是误判。`2026-06-09` 正式版存在 `jm2609.DCE` 多头 `2` 手的 `long_prev2day_stop` 平仓事件，详见 `20260609_2010_stage435_official_stage372_shadow_20260609_jm_close_signal.md`。本文件保留为误判来源记录，不作为今晚执行结论。

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-09 19:58 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：官方实盘版本日常影子盘检查；只读信号复核，不做策略优化。
- 是否重要突破：否。
- 是否触发A/B：否。没有新策略候选、没有接正式版、没有与第78基准组合。

## 外部调研与判断

- 参考资料：
  - 仓库 SOP：`skills/futures-live-execution-sop/SKILL.md`
  - 正式配置：`examples/portfolio_backtesting/qmt_roll_official_live_config.py`
  - 官方交易日历核对：中国金融期货交易所 2026 年休市安排显示端午休市为 `2026-06-19` 至 `2026-06-21`，`2026-06-09` 与 `2026-06-10` 不在节假日休市段。
  - GitHub/外部策略代码：本次不是新策略研究或优化，不引入外部策略代码。
- 我的判断：
  - 当前时间为 `2026-06-09 19:56 CST`，`2026-06-09` 日线已由 TQ 数据源补齐，适合生成给 `2026-06-09` 夜盘与 `2026-06-10` 日盘早段参考的影子盘信号。
  - 本次必须固定使用当前正式版本 `official_live_stage372_20w_recovery_sleeve`，不能回退 Stage653 原版、Stage372 30万研究口径或旧 Stage78-1 50万口径。

## 本次变更

- 新增脚本：无。
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：
  - 数据更新：`--mapping-start 2026-06-01 --bar-start 2026-06-09 --end 2026-06-09`
  - 影子盘：`--target-date 2026-06-09`
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：`2026-01-01` 至 `2026-06-09`
- 最新完成数据日：`2026-06-09`
- 账户规模：`200,000`
- 成本口径：正常成本；同时输出 2x/3x 成本压力。
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
- 当前理论影子持仓：`jm2609.DCE` 多头 `2` 手，收盘价 `1360.0`，精确保证金 `32,640`
- 目标信号数：`0`
- `2026-06-09` 夜盘交易信号：无新增开仓、无平仓、无反手。
- `2026-06-10` 日盘早段交易信号：无新增开仓、无平仓、无反手。
- 订单 API 调用次数：`0`
- CTP/SimNow 账户状态：本次未刷新 broker snapshot；因理论信号计划为空，不推进到 fresh read-only / daily execution gate。

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

- 本阶段结论：`2026-06-09` 官方 Stage372/20万影子盘没有生成可用于 `2026-06-09` 夜盘或 `2026-06-10` 日盘早段的新增交易信号。
- 是否进入下一步：只做日常跟踪，不进入策略研究或A/B。
- 下一步：
  - 若只是人工盘前检查：今晚和明早不需要按影子盘信号发起新订单。
  - 若要进入 SimNow/券商测试执行链：因为理论信号为空，默认不需要刷新 fresh broker gate；若用户仍要求对账，可单独跑只读账户快照。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本次固定官方版本、固定月度 AI 池、只补行情与复跑日报，不调参数、不选择窗口、不根据结果改规则。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是。
- 原因：日常影子盘能防止错过或误发交易信号；本次结论为空信号，同样有执行价值，因为它明确禁止推进新增订单。

## 合入建议

- 是否更新本线 `LINE.md`：否。无重要突破或路线状态变化。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：否。日常影子盘无重大结论，不追加历史总账。
