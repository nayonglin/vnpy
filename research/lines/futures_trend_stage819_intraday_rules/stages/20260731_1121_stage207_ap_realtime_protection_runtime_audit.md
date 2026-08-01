# Stage207 AP 实时保护运行状态核验

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：官方实盘只读运行状态核验；未连接新 CTP 会话、未发单、未撤单、未重启或修改生产状态
- 记录时间：2026-07-31 11:21 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`；当前工作区
- 阶段性质：实时执行保护与手工仓位安全审计
- 是否重要突破：否；延续 Stage206 根因并确认当前保护链仍未恢复
- 是否触发A/B：否；不修改策略或生产配置

## 外部调研与判断

- 参考资料：
  - 郑州商品交易所《鲜苹果期货业务细则》：AP 上午交易时段为 09:00—11:30，当前核验时间仍在正常日盘内。
  - vn.py GitHub Releases：未发现可将本次状态归因于上游自动止盈/止损行为的证据；实际阻断来自本地 Stage608/941/927 证据链。
- 我的判断：
  - “进程存在”不等于实时保护有效。当前行情、检测、执行进程均存活，但检测器 fail-closed，平仓权限为 0。
  - 正式 C9 实时模块实现的是入场日 `0.5R` 保护止损与一次重试；`+0.5R` 顺向进展只进入 `watch_progress_hit_no_initial_stop`，不会形成固定实时止盈单。RSI95 半仓止盈属于日级策略逻辑，不是当前 Stage904 的独立实时止盈进程。

## 本次变更

- 新增脚本：无
- 修改脚本：无
- 删除脚本：无
- 新增参数：无
- 修改参数：无
- 删除参数：无
- 新增记录：本 Stage207 中文状态核验

## 回测/归因参数

- 数据区间：2026-07-31 11:18—11:21 CST
- 账户规模：150,000 元，`c9-15w`
- 成本口径：不适用；未运行回测
- 样本过滤：AP610.CZCE、当前 Stage608/941/927/930/931、intent spool、execution ledger 与券商只读仓位
- 策略/归因口径：`official_live_stage847_c9_15w_stage819_05r_stop_retry_once`

## 结果

- 期末权益：不适用；未运行回测
- 总收益：不适用；未运行回测
- 最大回撤：不适用；未运行回测
- Sharpe：不适用；未运行回测
- 总滑点：不适用；未运行回测
- 总交易次数：本次核验自动订单 0
- 胜率：不适用
- 其他关键指标：
  - Stage930、Stage608、Stage941、Stage931 相关进程均存活。
  - 11:18:35：AP610 tick 年龄约 0.836 秒，`all_symbols_fresh=1`；但 Stage608 仍为 `stream_ready=0`、`ever_stream_ready=false`，保留 `prior_session_unclean`。
  - Stage941：`detector_running_unready`、`detector_feed_unready`，blocker 为 `tick_heartbeat_stream_ready_not_true`，`tick_count=0`、`intent_count=0`、`ready_count=0`；游标仍停在 2026-07-30 feed sequence 1。
  - intent spool：`intents=0`。
  - Stage931 warm executor 自身心跳为 `ready`，但没有输入 intent。
  - Stage927：`real_submit_permitted=0`、`reduce_close_submit_permitted=0`，平仓保护也不能提交。
  - 券商只读仓位：AP610 多仓 4 手；手工订单 7738 全部成交。
  - execution ledger：手工订单/成交仍为 `broker_*_callback_unbound`，没有自动 intent 绑定。
  - 自动订单 API：send/cancel/order 均为 0。

## 输出文件

- report：`research/lines/futures_trend_stage819_intraday_rules/stages/20260731_1121_stage207_ap_realtime_protection_runtime_audit.md`
- summary：`~/Library/Application Support/qmt-roll-stage179/production-live/official-live/qmt_roll_stage930_official_live_c9_session_daemon_summary_20260731_110330_stage930_official_live_c9_session_daemon_v1.json`
- orders：`~/Library/Application Support/qmt-roll-stage179/production-live/official-live/qmt_roll_stage174_ctp_vnpy_readonly_probe_orders_stage174_ctp_vnpy_readonly_probe_v1.csv`
- daily：不适用
- quality：Stage941 heartbeat、intent spool 只读计数、Stage927 capability、execution ledger、券商只读订单/成交/仓位交叉验证

## 结论

- 本阶段结论：当前实时止盈/止损保护没有正常生效。进程虽然存活，但检测器不消费 tick、没有 intent，且 `reduce_close_submit_permitted=0`；AP610 手工多仓应按“未被自动保护”管理。
- 是否进入下一步：是
- 下一步：
  1. 在修复与验收前，不把 AP 手工仓位交给当前自动保护链。
  2. 先显式对账并吸收手工 4 手仓位，清除重复开仓风险。
  3. 修复 Stage608 历史 gap 恢复、Stage260 时区快照解析和 Stage927 证据闭环后，使用隔离回放验证“新 tick → Stage941 close intent → Stage927 reduce-close authorization”；不得直接用真实仓位试错。

## 过拟合反思

- 运行前判断：否
- 运行后判断：否
- 原因：只核验实时状态与执行权限，没有修改参数或根据单笔盈亏调整策略。

## 继续价值反思

- 运行前判断：是
- 运行后判断：是
- 原因：AP610 当前有真实手工仓位，错误地把存活进程当作有效止盈/止损会产生直接风险。

## 合入建议

- 是否更新本线 `LINE.md`：暂不更新；待执行链修复并独立复核后统一整理
- 是否更新 `research/registry.md`：否
- 是否追加根目录 `memory.md/back_log.md`：暂不追加；修复闭环后再合入事故摘要
