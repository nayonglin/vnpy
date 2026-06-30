# Stage139 FG signal_plan 已入 shadow 持仓防重复与邮件澄清

- line_id：futures_trend_stage819_intraday_rules
- 当前模式：day
- 记录时间：2026-06-24 16:48 CST
- 工作区/分支：/Users/bytedance/Desktop/person/vnpy / master
- 阶段性质：官方实盘执行链路防重复与邮件可读性修复
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：本次是本地 Stage901/260/905/906/929 执行链路排障，未引用外部策略资料或 GitHub 策略代码。
- 我的判断：问题不在 C9 alpha，也不是 FG 又出现一条真正可提交的新开仓；核心是 Stage901 `signal_plan` 的理论影子交易已计入 shadow 当前持仓，但 Stage929 邮件主题仍把它写成 `FG609.CZCE short/open 15手`，Stage260 在 fresh 快照情景下也缺少一层“signal_plan open 已在 shadow 当前持仓中”的防重复阻断。

## 本次变更

- 新增脚本：无
- 修改脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_stage260_stage78_1_simnow_daily_execution_gate.py`
  - `examples/portfolio_backtesting/run_qmt_roll_stage929_official_live_15w_timed_cycle.py`
- 删除脚本：无
- 新增参数：无
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：2026-06-24 官方实盘 shadow/执行报告
- 账户规模：C9/15w 官方实盘口径
- 成本口径：不适用
- 样本过滤：2026-06-24 Stage901 signal_plan/current_positions、Stage260、Stage905、Stage906、Stage929 post-close
- 策略/归因口径：只改执行闸门和邮件展示，不改信号、AI池、手数、止损、重进场或真实提交策略

## 结果

- 期末权益：不适用
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：不适用
- 总交易次数：不适用
- 胜率：不适用
- 其他关键指标：
  - Stage901 2026-06-24 `signal_plan` 有 `FG609.CZCE short/open 15`，理论价 `967`；`current_positions` 同时已包含 `FG609.CZCE short -15` 和 `rb2610.SHFE short -11`。
  - Broker 只读持仓实际只有 `rb2610.SHFE short 11`，FG broker 为 `0`，Stage906 因 `FG shadow=15 / broker=0` 为 `reconcile_divergent_fail_closed`。
  - Stage905 为 `executor_no_intents`，ready `0`，订单 API `0`。
  - 修复后 Stage260 对 `stage901_signal_plan` open 增加 `shadow_position_already_contains_signal_open:15.0000` 阻断，`executable_count=0`。
  - 修复后 Stage929 signal_details 增加 `执行含义=理论shadow已持仓，不是新的自动开仓` 和 `Shadow已持仓=15`；邮件 subject 后缀只在 Stage905 ready 时显示合约，当前 FG blocked 理论项不会再出现在 subject。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage929_official_live_15w_timed_cycle_report_post-close_20260624_20260624_164712_stage929_official_live_15w_timed_cycle_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage929_official_live_15w_timed_cycle_summary_post-close_20260624_20260624_164712_stage929_official_live_15w_timed_cycle_v1.json`
- orders：不适用
- daily：不适用
- quality：Stage260 decision、Stage905 summary、Stage906 position_diff

## 结论

- 本阶段结论：用户看到的 FG609 不是新的自动开仓许可，而是 Stage901 理论影子账在 2026-06-24 生成并已计入 shadow 当前持仓的一笔 open；broker 实际已无 FG，因此执行链路 fail-closed。邮件原展示不符合手机阅读预期，已修复为明确标注“理论shadow已持仓，不是新的自动开仓”，并避免 subject 误报。
- 是否进入下一步：进入观察
- 下一步：20:55 live-real session 继续看 Stage906 是否仍因 FG shadow/broker 差异 fail-closed；如需要恢复日线级 broker/shadow 一致性，必须单独做“FG 手动止损/实盘 flat 是否应写入策略 ledger/shadow 调整”的审计，不能静默把 shadow 改平。

## 过拟合反思

- 运行前判断：否
- 运行后判断：否
- 原因：本次不改变交易信号或参数，只是防止执行层把已进入 shadow 当前持仓的理论 signal_plan open 重复解释为新开仓，并改善报告可读性。

## 继续价值反思

- 运行前判断：有价值
- 运行后判断：有价值
- 原因：这类邮件歧义会直接诱导人工误操作；执行层增加防重复阻断和邮件解释字段，能降低今晚和后续类似日终报告的误解风险。

## 合入建议

- 是否更新本线 `LINE.md`：是
- 是否更新 `research/registry.md`：否
- 是否追加根目录 `memory.md/back_log.md`：否
