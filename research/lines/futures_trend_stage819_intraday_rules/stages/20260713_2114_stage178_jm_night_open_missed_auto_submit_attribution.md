# Stage178 JM 夜盘未自动开空执行归因

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：`2026-07-13 21:14 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：官方实盘执行事故只读法证
- 是否重要突破：否；这是执行可靠性缺陷归因，不是策略突破
- 是否触发A/B：否；未形成新策略候选，不修改 alpha

## 外部调研与判断

- 参考资料：
  - VeighNa 官方 `vnpy_ctp` 实现：<https://github.com/vnpy/vnpy_ctp/blob/main/vnpy_ctp/gateway/ctp_gateway.py>。官方代码同样通过 `EVENT_TIMER` 交替查询账户和持仓，结算确认后先请求全量合约；这解释了短生命周期新连接不能把“登录成功”等同于“账户/持仓状态已完整到达”。
  - 大连商品交易所夜盘资料：<https://www.dce.com.cn/dalianshangpin/resource/cms/2019/04/2019042612023697006.pdf>。焦煤属于夜盘品种，连续夜盘从 `21:00` 开始。
- 我的判断：JM 策略信号没有被 AI 池、方向白名单、风险层、手数、保证金、合约或 kill switch 拦截。未自动成交由两层执行问题共同造成：当前 Stage930 是重型串行审计循环，连续竞价后的首次 Stage931 直到 `21:02:01` 才启动；随后 Stage931 在固定 `8` 秒连接等待内没有收到账户回调和持仓查询结束回调，按 fail-close 规则拒绝调用 `send_order`。安全原则正确，但“多次重连 + 固定睡眠 + 全链路串行”的实现不具备 `21:00` 准点提交能力。

## 本次变更

- 新增脚本：无。
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：无。
- 修改参数：无。
- 删除参数：无。
- 仅新增本阶段只读法证记录；未连接新的 CTP 会话，未调用报单或撤单 API。

## 回测/归因参数

- 数据区间：`2026-07-13 16:45:50–21:14 CST`。
- 账户规模：当前官方实盘 `150,000` 口径。
- 成本口径：不适用；本阶段不跑回测。
- 样本过滤：当晚 `jm2609.DCE` 空头开仓信号、Stage930 从 `20:55` 到 `21:09` 的前六个关键循环、Stage931 最终适配器、CTP 券商只读快照和执行 ledger；daemon 后续循环仍会继续追加。
- 策略/归因口径：`official_live_stage847_c9_15w_stage819_05r_stop_retry_once` / `Stage847-C9-15w`。

## 结果

- 期末权益：不适用。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：不适用；自动下单 API 调用 `0`。
- 胜率：不适用。
- 其他关键指标：
  - `16:45:50` Stage901 已生成 `jm2609.DCE short/open 2手 @1238.5` pending order；不是 `target_signal_count=0` 就无订单，必须读取 pending orders。
  - `20:55:05` launchd 准时触发；Stage930 本次运行产物时间为 `20:55:20`，首个 tick 刷新从 `20:55:24` 开始。
  - 第一轮 Stage905 `ready=1/blocked=0`、Stage927 `real_submit_permitted=1`；`20:57:43` Stage931 被预期的 `night_open_auction_2055_2100` 连续竞价保护拦截，订单 API `0`。
  - 开盘后的首轮从 `21:00:09` 才开始：外层 tick 刷新 `18.947s`，Stage903 controller `88.685s`，Stage927 arming `4.306s`；Stage931 到 `21:02:01` 才启动。
  - Stage931 `21:02:04` 建连，`21:02:07` 完成交易认证、登录与结算确认；固定 `8s` 等待结束时 `account_rows=0`、`position_query_last_seen=false`，触发 `ctp_account_callback_missing` 和 `ctp_position_query_last_missing`，`send_order/cancel_order=0/0`。
  - 用户手工单的本地委托回报时间为 `21:02:08`：`jm2609.DCE` 空开 `2` 手、成交均价 `1245.5`，两笔各 `1` 手全部成交。CTP 成交行中的 `2026-07-14` 是交易日语义，本地委托时间明确为自然日 `2026-07-13 21:02:08`。
  - 执行 ledger 对 `target_date=2026-07-13` 的事件数为 `0`，Stage931 submitted/orders/trades 均为空；结合用户自述，可高置信认定该成交不是 Stage931 自动单。券商快照不含客户端名称，无法从本地证据确认具体手工终端。
  - `21:04` 后系统识别 broker 已有同向空仓 `2` 手，Stage905 标记 `skipped_existing_broker_position`，Stage906 以 pending allowance 对齐，避免重复开仓。
  - `21:11:06` Stage904 已接管当日 C9 实时止损：broker 成交价 `1245.5`、初始止损 `1258`、`0.5R` 止损 `1251.75`、进展价 `1239.25`、最新监控价 `1246.0`，动作 `watch`，订单 API `0`。
  - 反事实边界：用户手工成交后没有留下“broker 仍为空仓”的下一轮自动重试样本，不能断言不手动下单就一定会自动成功；下一轮仍可能再次缺账户/持仓回调。手工操作与 Stage931 等待窗口重叠，但没有证据证明手工操作导致回调缺失。

## 输出文件

- report：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage929_official_live_15w_timed_cycle_report_evening-report_20260713_20260713_210508_stage929_official_live_15w_timed_cycle_v1.md`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage931_official_live_ctp_submit_adapter_report_20260713_stage931_official_live_ctp_submit_adapter_v1.md`
- summary：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage930_official_live_c9_session_daemon_summary_20260713_205520_stage930_official_live_c9_session_daemon_v1.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage931_official_live_ctp_submit_adapter_summary_20260713_stage931_official_live_ctp_submit_adapter_v1.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage904_official_live_c9_intraday_monitor_summary_20260713_stage904_official_live_c9_intraday_monitor_v1.json`
- orders：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow_pending_orders_stage901_stage847_c9_2026_ytd_live_shadow_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage174_ctp_vnpy_readonly_probe_orders_stage174_ctp_vnpy_readonly_probe_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage174_ctp_vnpy_readonly_probe_trades_stage174_ctp_vnpy_readonly_probe_v1.csv`
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage930_official_live_c9_session_daemon_events_20260713_205520_stage930_official_live_c9_session_daemon_v1.ndjson`。
- quality：launchd 状态、Stage930 前六轮关键事件、Stage931 连接日志、broker 委托/成交/持仓、ledger 空事件和 Stage904 接管状态已交叉核对；三个独立只读 agent 分别复核日志、闸门代码和券商证据，结论一致。未运行回测。

## 结论

- 本阶段结论：今晚不是“JM 没信号”，也不是“自动单发出但未成交”。信号在日盘收盘后已存在，launchd 也准时启动；`21:00` 不准时首先来自 Stage930 的串行重型循环，真正让自动单没有发出的直接原因是 Stage931 本次连接在固定 `8s` 内未拿到账户和持仓完成回调，fail-close 明确拦截。用户手工成交后，系统正确避免重复开仓并接管当日 C9 实时止损。
- 是否进入下一步：是；执行可靠性修复有高价值，但不得通过调整 JM 信号、AI 分数或策略参数解决。
- 下一步：
  1. 先设计“`20:55` 预热、`21:00` 轻量最终闸门”的持久 CTP 会话，减少同一轮 Stage608/Stage907/Stage931 多次建连。
  2. Stage931 从固定 `sleep(8)` 改为有上限的状态驱动等待：登录/结算、合约完成、账户回调和 position last 均到达后才放行，并显式触发/重试账户与持仓查询；在 SimNow/broker-test 做跨多会话验证后才允许部署。
  3. 修复 fresh 快照下 `readonly_refresh_plan_only` 被 Stage903 标成 blocked 的 ready/block 振荡。
  4. 增加“人工接管/暂停自动提交”原子开关和 ready intent 超时告警，消除手工单与正在连接的自动单竞态。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段只还原固定官方策略的执行时间线，没有根据 JM 当晚价格结果修改 alpha、品种、方向、AI 池、手数或止损参数。后续修复也应以跨品种、跨会话连接状态机测试为准，不能只把今晚的 `8s` 补成某个恰好通过的秒数。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是，而且优先级高。
- 原因：该缺陷直接使“有信号且所有上游闸门通过”仍无法落地；修复持久连接、状态驱动等待和人工接管竞态，能提升所有品种和所有交易时段的执行确定性，不依赖单笔收益结果。

## 合入建议

- 是否更新本线 `LINE.md`：暂不更新；当前并行工作只写唯一 Stage178 文件，修复实现和回归验收后再统一收口。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：暂不追加；若持久会话/状态驱动闸门完成正式验收，再作为重要执行链路修复摘要合入。
