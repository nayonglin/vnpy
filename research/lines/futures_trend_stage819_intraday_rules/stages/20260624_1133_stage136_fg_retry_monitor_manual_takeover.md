# Stage136 FG止损后重进场接管手动补仓修复

- line_id：futures_trend_stage819_intraday_rules
- 当前模式：day
- 记录时间：2026-06-24 11:33 CST
- 工作区/分支：/Users/bytedance/Desktop/person/vnpy / master
- 阶段性质：实盘执行层缺口修复与验证
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：本阶段只处理当前仓库实盘执行链路，不做外部策略调研；遵循 `skills/futures-live-execution-sop/SKILL.md` 的 fail-closed、只读证据和订单 API 审计要求。
- 我的判断：这是执行接管语义修复，不是 alpha 参数优化。修复目标是让“符合策略但因自动化 bug 由用户手动补开的仓位”在被 Stage904 实时止损平仓后，仍能进入 C9 一次重进场监控。

## 本次变更

- 新增脚本：无。
- 修改脚本：`examples/portfolio_backtesting/run_qmt_roll_stage904_official_live_c9_intraday_monitor.py`。
- 删除脚本：无。
- 新增参数：无。
- 修改参数：无。
- 删除参数：无。
- 主要改动：
  - 新增 `_opposite_direction()`，统一多空反向计算。
  - 新增 `_broker_original_open_trade_before_stage904_close()`，从只读 broker 成交流中反查第一笔 Stage904 止损平仓之前的原始开仓成交。
  - `_retry_actions()` 不再只依赖 execution ledger 的 open fill；看到 Stage904 止损平仓成交后，也会把原始方向加入重进场候选。
  - 若 ledger open fill 缺失，或 ledger open 是止损后错误的 `STAGE905-PENDING` 重开，则改用止损平仓之前的 broker 原始开仓作为 retry 基础。
  - 保持原始 Stage901 pending open 的 suppress 逻辑，不允许用它绕过 Stage904 retry 状态机。

## 回测/归因参数

- 数据区间：当前实盘 target_date `2026-06-23`。
- 账户规模：当前 official live 15万口径。
- 成本口径：无新增回测成本；只做执行层 dry-run。
- 样本过滤：`FG609.CZCE` 当前实盘事件链路。
- 策略/归因口径：`official_live_stage847_c9_15w_stage819_05r_stop_retry_once`，C9 0.5R 止损后重回原开仓价允许一次重进场。

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
  - 手动 Stage904 dry-run：`monitor_status=intraday_monitor_ready`、`action_count=2`、`retry_candidate_rows=1`、`retry_watch_count=1`、`retry_open_dry_run_count=0`、`close_dry_run_count=0`、`order_api_called_count=0`。
  - Stage930 守护进程随后以 `max_tick_age_seconds=45` 自动覆盖文件；午休 tick 过期后，FG retry 行变为 `retry_block/retry_fresh_tick_missing_or_stale`，符合 fail-closed。
  - Stage905 dry-run：`executor_no_ready_intents`、`ready_count=0`、`skipped_count=1`、订单 API `0`；原始 `stage901_pending_order` 仍被 `suppressed_after_stage904_stop_close_wait_for_stage904_retry`。
  - FG 原始策略空开成交价识别为 `967.0`，初始止损价 `979.0`，0.5R 止损价 `973.0`，重进场触发价 `967.0`。
  - 当前最近 tick 为 2026-06-24 11:30:00，FG last `978.0`、买一 `977.0`、卖一 `978.0`；午休后对 45 秒阈值已经 stale，不触发重进场。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage904_official_live_c9_intraday_monitor_report_20260623_stage904_official_live_c9_intraday_monitor_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage904_official_live_c9_intraday_monitor_summary_20260623_stage904_official_live_c9_intraday_monitor_v1.json`
- orders：不适用，订单 API `0`
- daily：不适用
- quality：`py_compile` 通过；Stage905 当前无 ready intent

## 结论

- 本阶段结论：重进场逻辑正在由 Stage930/904 守护链路运行；FG 在修复后能进入 retry 候选，但当前午休 tick stale 且价格仍在 `977/978` 附近，未达到空头重进场触发价 `967`，所以不会下单。
- 是否进入下一步：是，继续观察下午开盘 fresh tick 恢复后，FG 是否按 `<=967` 触发 `retry_open_dry_run`。
- 下一步：下午开盘后若 fresh tick 的 progress extreme 对 FG 空头达到 `<=967`，Stage904 应生成 `retry_open_dry_run`，Stage905/931 再按当前执行闸门生成并提交一次空开；若未达到，则保持 `retry_watch`。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本次没有改变信号、手数、止损 R 倍数、AI 池或回测参数，只补齐实盘接管状态来源，避免手动补仓导致 retry 状态机丢失。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是。
- 原因：如果不修复，手动补开的策略仓即使被实时止损平掉，也无法按回测语义进入一次重进场；这会造成实盘和回测执行路径不一致。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：否，本次是执行层缺口修复记录，不是正式候选或研究突破。
