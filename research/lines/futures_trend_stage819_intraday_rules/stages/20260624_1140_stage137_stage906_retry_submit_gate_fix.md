# Stage137 Stage906重进场提交闸门修复

- line_id：futures_trend_stage819_intraday_rules
- 当前模式：day
- 记录时间：2026-06-24 11:40 CST
- 工作区/分支：/Users/bytedance/Desktop/person/vnpy / master
- 阶段性质：实盘执行层提交闸门修复
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：本阶段只处理当前仓库实盘执行链路，不做外部策略调研；遵循 `skills/futures-live-execution-sop/SKILL.md` 的 fail-closed、只读证据和订单 API 审计要求。
- 我的判断：这不是策略 alpha 优化，而是修复 Stage906 对 broker 订单状态和 suppressed pending order 的解释，避免下午 FG 触发重进场后被错误挡在提交闸门外。

## 本次变更

- 新增脚本：无。
- 修改脚本：`examples/portfolio_backtesting/run_qmt_roll_stage906_official_live_reconciliation_worker.py`。
- 删除脚本：无。
- 新增参数：无。
- 修改参数：无。
- 删除参数：无。
- 主要改动：
  - Stage906 `_active_orders()` 不再按交易所 `datetime` 选择每张订单最新状态，改为按 broker 回调行序 `_row_seq` 选择最后状态。
  - Stage906 pending order visibility 检查新增对 `stage904_stop_close_wait_for_retry` suppressed pending open 的解释：这类原始 Stage901 pending 已被 Stage904 止损后接管，不能继续要求其在 broker 或 ready intents 中可见。

## 回测/归因参数

- 数据区间：当前实盘 target_date `2026-06-23`。
- 账户规模：当前 official live 15万口径。
- 成本口径：不适用。
- 样本过滤：`FG609.CZCE` 当前实盘事件链路。
- 策略/归因口径：`official_live_stage847_c9_15w_stage819_05r_stop_retry_once`，执行层 Stage906/Stage927 提交闸门。

## 结果

- 期末权益：不适用。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：不适用。
- 胜率：不适用。
- 其他关键指标：
  - `py_compile` 通过。
  - 修复前，Stage906 在宽松快照年龄模拟下仍为 `reconcile_divergent_fail_closed`，原因是 `stage901_pending_orders_broker_visibility` 未解释 suppressed FG pending open。
  - 修复后，Stage906 宽松快照年龄模拟为 `reconcile_aligned`、`active_broker_order_count=0`、`blocking_failure_count=0`、订单 API `0`。
  - 午休真实 300 秒快照口径仍会因 snapshot stale fail-closed；这是预期行为，下午 `day_pm` fresh refresh 后才应恢复提交闸门判断。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage906_official_live_reconciliation_worker_report_20260623_stage906_official_live_reconciliation_worker_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage906_official_live_reconciliation_worker_summary_20260623_stage906_official_live_reconciliation_worker_v1.json`
- orders：不适用，订单 API `0`
- daily：不适用
- quality：`py_compile` 通过

## 结论

- 本阶段结论：修复后，下午 13:25/13:30 进入 day_pm、broker/tick fresh refresh 正常时，Stage906 不应再因为旧订单状态或已 suppress 的原始 FG pending open 阻断 C9 retry open。
- 是否进入下一步：是。
- 下一步：下午开盘后观察 Stage904/905/906/927/931 链路；若 FG fresh tick 触发 `<=967`，应进入 `retry_open_dry_run`，再由 Stage905/927/931 提交一次 retry open。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本次只修 broker 订单回调顺序和 pending 解释，不改变策略信号、AI 池、手数、R 倍数、止损价或回测样本。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是。
- 原因：若不修复，FG 即使下午价格满足重进场条件，也可能被 Stage906/Stage927 错误挡住，继续造成实盘与回测执行语义不一致。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：否，本次是执行层缺口修复记录，不是正式候选或研究突破。
