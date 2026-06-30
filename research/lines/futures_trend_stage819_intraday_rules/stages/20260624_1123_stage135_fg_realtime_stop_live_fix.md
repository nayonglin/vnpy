# Stage135：FG 实时止损未触发的实盘修复

记录时间：2026-06-24 11:23 CST

所属研究线：futures_trend_stage819_intraday_rules

## 背景

用户反馈 FG 已超过止损价但没有实时止损。复核当时实盘状态，FG609.CZCE 空单 15 手，策略接管价 967，初始止损 979，C9 0.5R 实时止损价 973；Stage904 最新监控显示 live_price 980/981，已经高于空单止损价，理论上应触发买平。

## 根因

1. Stage904 tick 时间列选择有 bug：Stage608 tick 文件存在 localtime 列但值为空，Stage904 优先选择 localtime 后直接得到全 NaT，没有 fallback 到 datetime/snapshot_at，导致 fresh_tick_batch_count=0，adverse_extreme_price=0，最终没有触发 adverse_hit。
2. Stage931 解析 Stage905 order_request_json 时直接 Direction(str(value))，在 live CTP/vn.py 运行态下遇到 Long 枚举值异常，报 ValueError("'Long' is not a valid Direction")，真实 send_order_api_called_count=0。
3. 第一次修复后，FG 被正确止损买平 15 手，但 Stage905 又把原始 Stage901 pending open 重新放行为开仓，导致 11:12:53 再次空开 15 手，成交 979；这绕过了 C9 “止损后必须由 Stage904 retry 条件触发才可重试”的语义。
4. 订单快照按交易所 datetime 排序判断最新状态，遇到同一订单“提交中”的 datetime 晚于“全部成交”时，把已成交订单误判为 active_order_count=1。

## 修改内容

新增参数：无。

修改参数：无。

删除参数：无。

代码修改：

- Stage904 `_tick_dt_series` 改为跳过全空时间列，继续 fallback 到 datetime/snapshot_at/generated_at。
- Stage904 增加“Stage901 pending open 在 Stage904 止损平仓后又重开”的强制平仓识别，不再因为 risk_price=0 阻断减风险平仓。
- Stage904 retry 候选排除这种止损后错误重开的 pending open，避免平仓后继续显示 retry_block。
- Stage905 读取 execution ledger，若同品种同方向已有 Stage904 止损平仓成交，则原始 Stage901 pending open 标记为 skipped，必须等待 Stage904 retry_open 才能重试。
- Stage905/Stage931 订单最新状态判断改为按同一订单在文件/事件流中的最后出现行，而不是按交易所 datetime。
- Stage931 增加 Direction/Offset/OrderType 显式解析，兼容 long/short/open/close、中文枚举值和 vn.py enum name/value。
- execution ledger 公共函数归一化 多/空/开/平 与 long/short/open/close，修复 weighted_open_fill 和 duplicate 识别。

## 实盘执行结果

- 11:07:43 修复 Stage904 后，FG close dry-run 生成：FG609.CZCE short 15 手，止损价 973，live/adverse 981，adverse_hit=1。
- 11:10:13 Stage931 自动买平 FG609.CZCE 15 手，报单价 985，11:10:14 全部成交，成交价 980，残量 0。
- 11:12:53 由于原始 pending open 漏洞，系统错误再次空开 FG609.CZCE 15 手，成交价 979。
- 11:19:01 修复 pending open/枚举/订单状态后，Stage931 再次买平 FG609.CZCE 15 手，报单价 984，成交价 979，残量 0。
- 11:19:43、11:19:48、11:19:52 只读持仓快照确认 FG609.CZCE 空单 volume=0。
- 11:22:05 手动刷新后 Stage904 `intraday_monitor_ready`、close_dry_run_count=0、blocked_count=0。
- 11:22:07 Stage905 `executor_no_ready_intents`、ready_count=0、blocked_count=0；原始 Stage901 pending open 被 `stage901_pending_open_suppressed_after_stage904_stop_close_wait_for_retry` 跳过。

## 验证

- `py_compile` 通过：Stage904、Stage905、Stage931、execution ledger。
- `git diff --check` 通过。
- Stage904/905 手动复跑确认无 ready 指令。
- CTP 只读持仓确认 FG flat。

## 回测结果

本阶段是实盘执行链路修复，不是策略 alpha 或回测版本变更；没有新增、修改或删除回测结果。

## 反过拟合判断

否。本次没有调整 C9 参数、止损线、手数、AI 池或品种选择，只修实盘执行语义与本地状态机一致性。

## 继续价值判断

是。该问题直接影响实盘“价格越过止损后是否自动减风险”，且已经用真实订单和只读持仓闭环验证。

## 后续 TODO

1. 等下一轮 Stage930 守护进程自然循环确认 Stage904/905 继续保持 no-ready，不再重复报单。
2. 后续邮件中应把本次止损执行链路的关键事件用普通文本说明清楚，避免只显示 adapter duplicate/blocker。
3. 对 Stage930/Stage931 latest 输出被后续 duplicate-check 覆盖为空 CSV 的问题做审计优化，避免事后查证依赖 ledger tail。
