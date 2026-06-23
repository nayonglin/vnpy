# Stage116：Stage931 连续竞价提交保护

记录时间：2026-06-22 20:38 CST

## 本次结论

本次不是策略优化，不改变 C9/Stage847 的 alpha、入场信号、止损 R 倍数、重试次数、品种池、AI 池或资金风控参数。只修正实盘提交时段保护：Stage930 仍在 20:55/08:55 启动做连接、tick、只读刷新、Stage904/905/927 检查，但 Stage931 live-real 真实提交新增连续竞价时间闸门，避开夜盘集合竞价、日盘集合竞价、10:15 小节休息、午休和 15:00 收盘缓冲。

## 外部调研与判断

已查交易所公开规则口径：有夜盘品种开盘集合竞价在连续交易时段开市前 5 分钟，20:55-20:59 为申报，20:59-21:00 为撮合；rb 属于上期所夜盘品种，连续竞价为 21:00 后。判断：当前 Stage931 默认 `fill_wait_seconds=8`，如果在 20:55-20:59 过早提交并按残单逻辑撤单，存在撮合前被撤掉的执行语义风险。因此应让守护进程提前启动做准备，但真实提交等连续竞价开始后再放行。

## 代码改动

- 修改 `examples/portfolio_backtesting/run_qmt_roll_stage931_official_live_ctp_submit_adapter.py`
- 新增 `_continuous_submit_blockers()`：
  - `20:55-21:00` 阻断：`night_open_auction_2055_2100`
  - `08:55-09:00` 阻断：`day_open_auction_0855_0900`
  - `10:15-10:30` 阻断：`day_mid_break_1015_1030`
  - `11:30-13:30` 阻断：`day_lunch_break_1130_1330`
  - `15:00-15:10` 阻断：`day_close_buffer_1500_1510`
- live-real 模式下把上述 blocker 并入 Stage931 blockers。
- Stage931 summary 新增 `continuous_submit_blockers` 字段，方便邮件/报告/事后复盘。

## 验证

- `.py311/bin/python -m py_compile examples/portfolio_backtesting/run_qmt_roll_stage931_official_live_ctp_submit_adapter.py`：通过。
- 时间窗口函数检查：20:56 阻断、21:00 放开、10:20 阻断、13:30 放开。
- `git diff --check -- examples/portfolio_backtesting/run_qmt_roll_stage931_official_live_ctp_submit_adapter.py`：通过。
- Stage931 dry-run：`adapter_blocked/no_ready_stage905_intents`，`send_order_api_called_count=0`，`cancel_order_api_called_count=0`，`order_api_called_count=0`。

## 过拟合判断

否。本阶段只是在实盘执行适配器增加交易所时段保护，不根据历史收益、品种、方向或当晚 rb 信号调参数。

## 继续价值判断

是。该保护降低 20:55 启动但 21:00 前过早撤单的执行语义风险，更符合“20:55 准备、21:00 后真实连续竞价提交”的无人值守实盘预期。

## TODO

- 20:55 后观察 Stage930 是否启动并在 20:55-21:00 记录 `continuous_submit_blockers`，21:00 后是否自然放开。
- 若 rb 成交，立即核对 Stage931 execution ledger、成交回报、Stage904 止损监控动作和邮件通知。
