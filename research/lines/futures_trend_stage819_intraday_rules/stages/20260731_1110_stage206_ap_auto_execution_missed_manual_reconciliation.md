# Stage206 AP 自动成交缺失与手工成交对账归因

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：官方实盘只读事故归因；未连接 CTP、未发单、未撤单、未修改生产状态
- 记录时间：2026-07-31 11:10 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`；当前工作区
- 阶段性质：执行链路事故归因与手工成交对账
- 是否重要突破：是；首次把 2026-07-31 早盘 AP 自动未成交追溯到前一晚磁盘耗尽造成的行情流永久 fail-close，并确认手工成交未绑定策略意图
- 是否触发A/B：否；不改变策略 alpha，也不接入新策略版本

## 外部调研与判断

- 参考资料：
  - 郑州商品交易所《鲜苹果期货业务细则》：AP 日盘为 09:00—11:30、13:30—15:00，夜盘以交易所另行公告为准。
  - vn.py GitHub Releases：上游持续维护 CTP 报单、撤单和行情字段行为，但本次 `Stage608/Stage941/Stage260/Stage927` 阻断均来自本仓库自定义执行证据链，不能归因于交易所或 vn.py 上游拒单。
- 我的判断：
  - AP610 确有 `Stage901` 待执行多开 4 手信号，理论价 7741；早盘 09:01 后 AP 行情持续新鲜，因此不是“没有信号”或“AP 没行情”。
  - 券商侧 `send_order/cancel_order/order_api_called_count` 均为 0；自动链从未向交易所提交这笔单，所以不是交易所拒单、价格未成交或柜台拒绝。

## 本次变更

- 新增脚本：无
- 修改脚本：无
- 删除脚本：无
- 新增参数：无
- 修改参数：无
- 删除参数：无
- 新增记录：本 Stage206 中文归因记录

## 回测/归因参数

- 数据区间：2026-07-30 20:55—2026-07-31 11:07 CST
- 账户规模：150,000 元，`c9-15w`
- 成本口径：不适用；未运行回测
- 样本过滤：仅 AP610.CZCE、Stage901 待执行单、Stage930 早盘守护进程、Stage608/941/260/905/927/931 证据、券商只读订单/成交/持仓
- 策略/归因口径：`official_live_stage847_c9_15w_stage819_05r_stop_retry_once`

## 结果

- 期末权益：不适用；未运行回测
- 总收益：不适用；未运行回测
- 最大回撤：不适用；未运行回测
- Sharpe：不适用；未运行回测
- 总滑点：不适用；未运行回测
- 总交易次数：自动 0；用户手工订单 1 笔、成交回报 4 笔，共 4 手
- 胜率：不适用
- 其他关键指标：
  - `Stage901`：AP610 多开 4 手，理论价 7741，待执行。
  - 2026-07-30 21:22:20：Stage608 记录 `OSError(28, 'No space left on device')`，终态为 `fault_stopped`、`clean_shutdown=false`。
  - 2026-07-31 09:01：AP610 tick 年龄约 1.6 秒，累计 durable tick 150 条、无缺失品种，但恢复证据携带 `prior_session_unclean` gap；`stream_ready=0`、`ever_stream_ready=false`。
  - Stage941：`tick_heartbeat_stream_ready_not_true`，检测器从 2026-07-30 旧游标停住，`intent_count=0`。
  - Stage260：只读快照 `generated_at` 为带时区 ISO 字符串，当前 `_parse_generated_at` 仅接受无时区格式，导致 `snapshot_age_seconds=null`、`readonly_gate_not_passed`。
  - Stage927：`real_submit_permitted=0`、`initial_open_submit_permitted=0`，另有 acceptance、reconcile、health、scheduler、静态边界和证据完整性阻断。
  - Stage931/Stage930：自动订单 API 调用均为 0。
  - 用户手工成交：2026-07-31 09:03:44，AP610 多开 4 手，价格 7738，全部成交；券商只读快照 11:07 确认多仓 4 手。
  - 执行账本把手工订单与 4 笔成交记为 `broker_*_callback_unbound`，即已观察但未绑定自动 intent。
  - Stage260 的开仓 pending-order 分支不比较已有 broker 同向持仓，当前仍保留原 4 手待开仓；若直接解除闸门，存在重复开仓风险。

## 输出文件

- report：`research/lines/futures_trend_stage819_intraday_rules/stages/20260731_1110_stage206_ap_auto_execution_missed_manual_reconciliation.md`
- summary：`~/Library/Application Support/qmt-roll-stage179/production-live/official-live/qmt_roll_stage930_official_live_c9_session_daemon_summary_20260731_085520_stage930_official_live_c9_session_daemon_v1.json`
- orders：`~/Library/Application Support/qmt-roll-stage179/production-live/official-live/qmt_roll_stage174_ctp_vnpy_readonly_probe_orders_stage174_ctp_vnpy_readonly_probe_v1.csv`
- daily：不适用
- quality：Stage930 events、Stage608 heartbeat、Stage260/927 summaries、execution ledger 与 11:07 券商只读快照交叉验证

## 结论

- 本阶段结论：
  - 首要底层原因是 7 月 30 日晚磁盘耗尽使 Stage608 行情流以不干净终态退出；7 月 31 日早盘恢复逻辑将其转换成永久 `prior_session_unclean` gap。即使 AP 新 tick 已经持续落盘，行情流仍不能宣告 ready，Stage941 因而不能生成 intent。
  - 即使修复上述行情流问题，Stage260 时间格式解析缺陷和 Stage927 多项未闭合证据仍会阻止真实提交，所以当前自动实盘链并未达到可提交状态。
  - 用户手工仓位未被策略接管，不能假定自动止损/平仓有效。
- 是否进入下一步：是，但必须作为执行安全修复，不是策略优化。
- 下一步：
  1. 在任何重新放行前，把 AP610 手工多仓 4 手与 Stage901 pending order 做显式吸收/对账，消除重复开仓风险。
  2. 修复 Stage608 对已披露历史 gap 的会话级 readiness 语义，补“前一会话磁盘满、次日新行情恢复”的回归测试；仍需保留不可恢复数据缺口的 fail-close。
  3. 修复 Stage260 带时区 ISO `generated_at` 解析，并让 pending-order open 比较 broker 同向持仓。
  4. 单独补齐 Stage927 acceptance/reconcile/health/scheduler/static-boundary/evidence 闭环，未完成前不得声明自动实盘可用。

## 过拟合反思

- 运行前判断：否
- 运行后判断：否
- 原因：本次只分析执行状态机、行情流水位和券商成交，不修改参数，也不利用成交结果反向拟合策略。

## 继续价值反思

- 运行前判断：是
- 运行后判断：是
- 原因：这是实盘自动执行可靠性与重复开仓风险，不解决会持续造成“有信号但不下单”或手工补单后重复开仓。

## 合入建议

- 是否更新本线 `LINE.md`：暂不更新；先完成修复与独立复核，再由合入者整理
- 是否更新 `research/registry.md`：否
- 是否追加根目录 `memory.md/back_log.md`：暂不追加；待修复验证闭环后作为重要实盘执行事故摘要合入
