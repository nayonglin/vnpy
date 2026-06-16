# Stage101：C9/15w 自动化实盘链路独立审查

- 时间：2026-06-16 14:51 CST
- 研究线：`futures_trend_stage819_intraday_rules`
- 当前官方实盘：`official_live_stage847_c9_15w_stage819_05r_stop_retry_once`
- 本阶段性质：执行自动化/代码审查，不改策略参数，不跑回测，不连接 CTP，不调用订单 API。
- 独立 agent：已拉起独立审查 agent `019ecf2e-ec33-7c61-8163-8091aef9112d`，审查对象包括 Stage929/930/931/932、邮件通知、launchd、Phase D gates 与 C9 开仓日止损链路。

## 外部调研与判断

- 调研对象：vn.py `MainEngine.send_order/cancel_order`、CFTC electronic trading risk principles、FIA automated trading risk controls。
- 判断结论：vn.py 的 `send_order/cancel_order` 是直通 gateway 的最后一层动作；自动交易上线前必须有本地预交易控制、重复执行限制、消息节流、kill switch、异常恢复和事后对账。当前审查重点应放在“挡错单、挡重复单、故障自恢复”，而不是策略收益参数。

## 主要发现

1. P1：当前 scheduled `live-real` 仍被配置层 fail-closed 闸门挡住。
   - `qmt_roll_official_live_config.py` 的 `OFFICIAL_LIVE_EXECUTION_POLICY["real_submit_default"]` 仍为 `fail_closed`。
   - Stage902 在 `--mode live-real` 下明确要求该配置不为 `fail_closed`，否则 `ready_for_phase_d_real=0`。
   - 本阶段只读验证显示 Stage902 live-real 当前为 `phase_d_blocked`，阻断项包括 `official_live_config_real_submit_default_fail_closed`、target date/shadow 不匹配、只读快照陈旧、Stage260 缺失。
   - 结论：当前 launchd 虽然传入 `live-real/live-real` 和实盘 env，但还不能称为“会自动真实下单”。

2. P1：开仓日 tick 止损还不能称为全覆盖。
   - Stage904 使用 shadow open trade / entry risk 计算 0.5R 止损，不是直接使用 Stage931 实盘真实成交价、部分成交状态和订单回报状态机。
   - Stage904 文档也写明目前只覆盖初始 0.5R monitor dry-run，retry 仍需要订单/成交状态机。
   - Stage905 对 Stage904 产生的盘中 close intent 仍要求 Stage260 executable gate；这可能导致实盘开仓已成交后，盘中止损 close 被日线/原 pending gate 阻断。

3. P1：ready intent 缺少持久消费/幂等账本。
   - Stage905 每轮从 Stage901 pending 与 Stage904 actions 重建 ready intents。
   - Stage931 提交后只写 submitted/orders/trades，不把 intent 标记为 consumed，也没有按 reference/order_ref 做当日去重账本。
   - Stage906 可阻断活跃委托，但不能覆盖“上一轮委托已撤/被拒/未成交后，下一轮同一 intent 又重新 ready”的重复提交风险。

4. P2：Stage930 是轮询会话守护，不是 tick 级常驻事件引擎。
   - Stage930 每轮执行 tick refresh -> Stage903 -> Stage927 -> Stage931，然后 sleep。
   - 当前 launchd 传入 `--poll-seconds 30`，但单轮执行本身可能超过 30 秒。
   - 结论：当前止损是周期级自动检查，不是连续 tick-on-event 判断；快行情下可能晚于止损价成交。

5. P2：launchd 已安装，但尚无首次定时触发实证，也不是自恢复 supervisor。
   - C9 day/night launchd 当前均为 `live-real/live-real`，且注入真实提交相关 env。
   - `launchctl print` 显示 day/night 当前 `state = not running`、`runs = 0`，属于尚未到触发时间的状态。
   - plist 没有 `RunAtLoad`/`KeepAlive`；Stage930 若出现未捕获异常，launchd 不会在同一交易时段持续拉起。

6. P2：Stage931 真实提交适配器缺少最后一跳的新鲜度/登录态复核。
   - Stage931 检查 ready intent、kill switch、Stage927、env 与确认文本。
   - 进入 live-real 后是 `connect -> sleep -> send_order`，未在发单前确认本次交易登录、结算确认、账户/持仓回调和 Stage927 summary age。
   - 正常 Stage930 路径会先跑 Stage927，但直接调用或旧文件残留时风险仍存在。

7. P3：邮件链路可用且不会阻塞交易，但附件会外发业务敏感证据。
   - 邮箱 local env 文件未明文输出，`*.local.env` 与 `backtest_outputs/` 均被 gitignore 覆盖。
   - 邮件配置输出会 masked，发送异常只记录审计，不阻塞交易。
   - Stage931/932 附件可能包含订单、成交、日志、FrontID/SessionID/OrderRef 等业务敏感信息。

## 当前结论

- 不能说“一切已经完全自动、可无人值守自动实盘开平仓”。
- 更准确的说法是：已经有 scheduled live-real 自动化雏形、邮件通知、只读刷新、Stage927/Stage931 门禁和 fail-closed 链路；但当前真实自动下单仍被配置闸门挡住，且幂等、止损状态机、登录态复核、进程自恢复还不足。

## 后续规划/TODO

1. 增加 live order idempotency ledger：按 `intent_id + vt_symbol + direction + offset + volume + target_date + source_reason/reference` 记录 submitted/accepted/rejected/cancelled/filled/consumed，Stage931 发单前必须查账本。
2. Stage904/905 对盘中止损 close 解耦 Stage260 日线 executable gate；盘中止损应以 broker 持仓、真实成交价、entry risk 和 fresh tick 为核心门槛。
3. Stage931 发单前补本次 CTP 登录态、结算确认、账户/持仓回调、Stage927 summary age 与 ready intent age 检查。
4. Stage930 增加外层异常恢复、cycle watchdog、超时告警与 kill-switch 升级；或引入更明确的 supervisor。
5. 把当前“轮询止损”明确标记为 polling，不宣称 tick-by-tick；若要 tick 级执行，需改为常驻行情订阅 + 事件驱动状态机。
6. 在所有 P1/P2 修复后，再决定是否把 `real_submit_default` 从 `fail_closed` 切到明确的 live-real 配置值。

## 反思

- 过拟合判断：否。本阶段只审查执行工程和自动化安全，没有修改 C9 参数、品种、方向、R 倍数、窗口或样本。
- 继续价值判断：是。当前已经进入实盘自动化边界，发现的问题是下单安全与无人值守可靠性问题，继续修复比继续研究收益参数更有价值。
