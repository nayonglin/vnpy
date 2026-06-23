# Stage120 Stage931止损平仓发送前最终重定价

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：2026-06-22 23:48 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：实盘执行鲁棒性修复 / 不改策略信号 / 不改止损触发线
- 是否重要突破：否，但属于全自动止损成交可靠性的必要加固。
- 是否触发A/B：否。

## 外部调研与判断

- 参考资料：
  - vn.py GitHub `vnpy/trader/object.py`：`OrderRequest` 是带 `type`、`price`、`volume`、`offset` 的下单请求结构，当前 CTP 通路继续用 `OrderType.LIMIT` 与保护性限价是合理的工程约束。
  - URL：https://github.com/vnpy/vnpy/blob/master/vnpy/trader/object.py
- 我的判断：
  - 用户提出的风险成立：Stage904 看到止损触发价时，Stage905 生成的保护性限价到 Stage931 真正 `send_order` 前可能已经落后于盘口。
  - 不应把这个问题通过扩大策略止损、放宽风控或改回测参数解决；正确位置是执行层，在最终发送前基于最新可用 tick 重新计算同一套保护性限价。

## 本次变更

- 新增脚本：无。
- 修改脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_stage931_official_live_ctp_submit_adapter.py`
- 删除脚本：无。
- 新增参数：
  - `--final-reprice-tick-wait-seconds`，默认 `2` 秒。只用于 Stage931 止损平仓发送前等待最新 tick，不改变 Stage930 轮询频率。
- 修改参数：
  - 无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：不涉及。
- 账户规模：15万实盘口径。
- 成本口径：不涉及。
- 样本过滤：不涉及。
- 策略/归因口径：C9/15w 实盘 Stage904 止损触发、Stage905 dry-run 生成指令、Stage931 真实提交适配器；只改 Stage931 发送前价格。

## 结果

- 期末权益：不涉及。
- 总收益：不涉及。
- 最大回撤：不涉及。
- Sharpe：不涉及。
- 总滑点：不涉及。
- 总交易次数：不涉及。
- 胜率：不涉及。
- 其他关键指标：
  - Stage931 现在在 `reserve_execution_ledger_intent` 成功后、`final_pre_send_gate` 与 `send_order` 前执行最终重定价。
  - 仅对 `source=stage904_c9_intraday_close` 且 `offset=close` 的止损平仓启用。
  - 优先订阅 CTP 实时 tick；若 2 秒内没有新 tick，则读取 Stage608 tick 文件；两者都必须满足 `max_tick_age_seconds=10`，否则保留 Stage905 原价并写审计原因。
  - 空单止损买平按最新卖一价加 `max_slippage_ticks=5` 个 tick；多单止损卖平按最新买一价减 `5` 个 tick；仍按涨跌停价裁剪并按 tick 对齐。
  - 新增 `final_close_reprice_before_send` ledger 事件，`submitted_csv` 增加 `final_reprice_*` 字段，Stage931 输出增加 `ticks_csv` 与 `tick_row_count`。
  - 纯内存 helper 验证通过：rb 空单止损买平，Stage905 旧价 `3133`，最新卖一 `3150`，最终报单价重定价为 `3155`。
  - Stage931 dry-run 验证通过：`ready_intent_count=0`、`order_api_called_count=0`、`adapter_status=adapter_blocked`、阻断原因为 `no_ready_stage905_intents`。
  - `py_compile` 通过。
  - `git diff --check` 通过。

## 输出文件

- report：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage931_official_live_ctp_submit_adapter_report_20260622_stage931_official_live_ctp_submit_adapter_v1.md`
- summary：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage931_official_live_ctp_submit_adapter_summary_20260622_stage931_official_live_ctp_submit_adapter_v1.json`
- orders：
  - 真实下单 API 为 `0`。
- daily：不涉及。
- quality：
  - `.py311/bin/python -m py_compile examples/portfolio_backtesting/run_qmt_roll_stage931_official_live_ctp_submit_adapter.py`
  - `git diff --check -- examples/portfolio_backtesting/run_qmt_roll_stage931_official_live_ctp_submit_adapter.py`

## 结论

- 本阶段结论：
  - 已修复“止损触发后，真正挂单时盘口已经变了”的主要执行风险。现在止损价仍只是触发价，最终平仓委托在 Stage931 发送前会尽量用最新盘口重新生成保护性限价。
  - 这不保证极端跳价中一定成交，因为仍然是 CTP 限价单，不是无条件市价单；但第一笔止损单追不上盘口的概率下降。
- 是否进入下一步：是。
- 下一步：
  - 继续观察夜盘/明早实盘守护。如果触发止损，重点检查 ledger 的 `final_close_reprice_before_send`、最终委托价、成交价、撤单/重试状态和邮件说明。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：
  - 本阶段没有用历史收益结果调整策略参数，没有改止损线、R 倍数、品种、方向、手数或重试规则；只是在真实发送前用最新盘口更新限价。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是。
- 原因：
  - 全自动实盘的左尾风险不只来自策略信号，也来自执行延迟和挂单追不上。最终重定价能降低止损单首单漏成交概率，属于真实交易系统必须补的工程能力。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage120 执行修复状态。
- 是否更新 `research/registry.md`：否，当前 live profile 未变化。
- 是否追加根目录 `memory.md/back_log.md`：否，本次不是策略正式候选或跨线里程碑。
