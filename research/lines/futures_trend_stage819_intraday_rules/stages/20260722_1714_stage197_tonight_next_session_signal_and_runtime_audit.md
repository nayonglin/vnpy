# Stage197 今晚/明早信号与 production runtime 只读复核

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：C9/15万 production-live 只读运行复核
- 记录时间：2026-07-22 17:14 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy_stage179_production_live` / `codex/stage179-production-live`
- 阶段性质：每日数据、信号、launchd、CTP 只读 gate 复核
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：仓库 `futures-live-execution-sop` 与 `futures-official-shadow`；本阶段未做新的外部策略调研。
- 我的判断：判断今晚/明早是否下单必须以 7 月 22 日最新 Stage901 `pending_orders` 和 fresh broker gate 为准，不能只看 signal plan，也不能沿用 7 月 21 日回执。

## 本次变更

- 新增/修改/删除脚本：无。
- 新增/修改/删除参数：无。
- 运行操作：补齐 2026-07-22 的 19 个主力合约日线；通过 production launchd 重跑 postclose-precompute；重跑 health；尝试正式 CTP 只读刷新。

## 结果

- 数据：Stage173 `saved=19, failed=0, empty=0, max_saved_date=2026-07-22`。
- launchd：production surface `verified_exact`，disk/domain/loaded=`7/7/7`，unknown=`0`。
- production daily receipt：target cutoff date=`2026-07-22`。
- Stage901：profile=`c9-15w`，capital=`150000`，risk=`normal`，target signal count=`1`，pending order count=`0`，order API=`0/0`。
- 目标日信号：`si2609.GFEX` 空开 `6` 手，影子成交价 `8250`；影子当前持仓为 SI 空 `6` 手。
- broker：16:23 资格采集的最近合格快照为 `confirmed_flat`；17:11 新只读刷新在正式 framework 路径下发生 native `SIGSEGV`，栈顶为 `TdApi::getTradingDay()`，未形成新 generation；send/cancel/order API 仍为 `0/0/0`。
- postclose report：16:55 已触发，但当时 daily receipt 尚停在 7 月 21 日，因 `production_support_daily_data_receipt_invalid` 退出 `2`；17:10 receipt 已补到 7 月 22 日，本阶段未重发可能包含邮件副作用的 report。
- health：清理可重建缓存、恢复磁盘余量后，17:14 为 `healthy_production_live_scheduled`、blockers=`[]`、order API=`0/0/0`。

## 结论

- 今晚/明早 canonical actionable pending order：无。
- 7 月 22 日确有 SI 空开 6 手的影子信号，但影子已经把它计为成交持仓，实盘最近合格快照为空仓；不允许在今晚追单或把 signal plan 当 pending order。
- fresh CTP gate 当前失败，因此即使后续出现动作也必须保持 fail-closed，直到交易时段生成新的完整 broker 快照。
- 下一步：20:55 观察 night session 的 fresh CTP/行情/账户 gate；若仍在 `TdApi::getTradingDay()` 崩溃，则不提交任何订单并单独修复 runtime 生命周期问题。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：只补真实数据、读取固定正式信号和运行闸门，没有调参或改变 alpha。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是，但只限交易时段运行复核，不继续扩策略研究。
- 原因：当前已确认无 pending order，但 fresh CTP snapshot 未通过，必须由 20:55 的真实时段证据决定执行链是否可用。

## 合入建议

- 是否更新本线 `LINE.md`：否。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：否。
