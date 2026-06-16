# Stage094 C9/15w 官方实盘资金口径切换与账户只读核验

- 时间：2026-06-16 12:57 CST
- line_id：`futures_trend_stage819_intraday_rules`
- 是否重要突破：是。官方 live default 从 C9/30w 资金口径切换为 C9/15w，且影子盘冷启动日固化为 `2026-06-16`。
- 外部调研判断：vn.py / vnpy_ctp 的生产 CTP 连接依赖正确底层接口和动态库加载顺序；结合本仓 SOP，本次只做生产只读 runtime 与账户快照核验，不绕过 `vnpy_ctp/api/libs` 正式 framework 优先级，也不调用任何订单 API。

## 本次改动

- 新增参数：`OFFICIAL_LIVE_SHADOW_ANALYSIS_START_DATE="2026-06-16"`。
- 修改参数：
  - `OFFICIAL_LIVE_ALIAS`：`Stage847-C9-30w` -> `Stage847-C9-15w`
  - `OFFICIAL_LIVE_VERSION`：`official_live_stage847_c9_30w_stage819_05r_stop_retry_once` -> `official_live_stage847_c9_15w_stage819_05r_stop_retry_once`
  - `OFFICIAL_LIVE_PROFILE_NAME`：`stage847_c9_30w_stage819_05r_stop_retry_live` -> `stage847_c9_15w_stage819_05r_stop_retry_live`
  - `OFFICIAL_LIVE_CAPITAL/c3_capital/account_capital`：`300000` -> `150000`
  - `OFFICIAL_LIVE_PREVIOUS_VERSION`：改为 C9/30w，Stage372/20w 降为 legacy previous live default。
- 修改执行闸门：
  - Stage659 shadow 入口改为按 `OFFICIAL_LIVE_FAMILY_VERSION=stage819_c9_intraday_stop_retry` 委托 Stage901，不再硬编码 C9/30w。
  - Stage902/913/914/927 的 C9 校验从版本字符串改为 family 校验；Stage927 仍要求 controller 证据的 `official_live_version` 精确等于当前 15w 版本。
  - Stage901/909/903 默认 shadow 起点改为官方配置常量 `2026-06-16`。
  - Stage922 增加冷启动保护：若最新完成交易日早于 `2026-06-16`，返回 `target_date_before_live_shadow_start_waiting_fail_closed`。
  - Stage902/913 增加 `analysis_start==2026-06-16` 校验，防止旧 YTD shadow 被误判为可执行。
- 删除参数：无。

## 只读核验结果

- Stage914 生产 CTP runtime preflight：`production_readonly_preflight_passed`，`blocking_failure_count=0`，使用 `ctp_live.local.env`，正式 `vnpy_ctp/api/libs` 在 `DYLD_FRAMEWORK_PATH` 前置，订单 API 计数 `0`。
- Stage907 生产只读账户刷新：`readonly_refresh_completed_snapshot_ready`，`readonly_status_after=readonly_snapshots_received`，`position_snapshot_state_after=confirmed_flat`，订单 API 计数 `0`。
- Stage174 账户快照：`balance=150000.449813`，`available=150000.449813`；账户字段已脱敏。
- Stage174 持仓快照：`MA609.CZCE Long volume=0`，实际等价空仓。

## Shadow 与可执行性

- 2026-06-16 12:56 CST 的 Stage922 解析结果：最新完成交易日仍为 `2026-06-15`，但官方 shadow 冷启动日为 `2026-06-16`，因此状态为 `target_date_before_live_shadow_start_waiting_fail_closed`，`auto_submit_permitted=0`。
- Stage909 plan-only for `2026-06-16` 已确认晚间/日终刷新命令将使用：
  - `--mapping-start 2026-06-01 --bar-start 2026-06-16 --end 2026-06-16`
  - `--analysis-start 2026-06-16 --target-date 2026-06-16`
- Stage902 readiness gate for `2026-06-15` 被正确拦截，核心 blocker 为 `target_date_matches_shadow`：实际旧 summary `start=2026-01-01;end=2026-06-15`，要求 `start=2026-06-16;end=2026-06-15`。
- 兼容验证用 Stage901 YTD 15w shadow `2026-01-01 -> 2026-06-15` 结果：
  - 期末权益：`133,320`
  - 总收益：`-11.12%`
  - 最大回撤：`-14.0647%`
  - Sharpe：`-1.2461`
  - 总滑点：`1,700`
  - 总交易次数：`26`
  - 胜率：非零日胜率 `45.0%`
  - 风险层级：`normal`
  - `pending_order_count=0`
  - `order_api_called=false`
  - 注意：该 YTD shadow 只用于验证 15w 配置兼容，不作为从 2026-06-16 冷启动实盘账户的执行依据。

## 结论

- 官方正式版本现在是 C9/15w：`official_live_stage847_c9_15w_stage819_05r_stop_retry_once`。
- 实盘账户已只读确认补齐到约 `150000.45`，且当前空仓。
- 从今天开始的正式影子盘应以 `2026-06-16` 冷启动。当前时间尚未到 2026-06-16 日线数据完成点，所以现在不能计算今晚的真实 6/16 信号。
- 理论上，若 `2026-06-16` 日盘数据在 16:30 后更新成功，且 C9/15w 冷启动 shadow 产生 pending open order，那么最早的执行窗口是今晚夜盘窗口，系统窗口从 `20:55` 开始，实际交易通常按 `21:00` 夜盘开市处理。是否有第一笔交易取决于今晚刷新后的 pending order，不保证一定出现。

## 反思

- 运行前过拟合判断：否。本阶段只改部署资金口径和 shadow 冷启动日期，不改 C9 alpha、R 倍数、重试次数、品种、方向或阈值。
- 运行后过拟合判断：否。只读账户结果和 fail-closed 闸门不会反馈到策略参数。
- 运行前继续价值判断：是。实盘账户资金、影子盘资金口径、冷启动日期必须一致，否则手数和执行闸门会偏。
- 运行后继续价值判断：是。下一步价值在 2026-06-16 数据完成后跑 Stage909 run、复核 pending orders、刷新只读账户、再跑 readiness/dry-run；仍不应继续扫 C9 参数。

## TODO

- 2026-06-16 16:30 之后运行 Stage909 `--mode run --target-date 2026-06-16`，确认 `max_saved_date=2026-06-16` 且 cold-start shadow 成功。
- 若 `pending_orders` 非空，夜盘前刷新 Stage907 只读账户快照，再跑 Stage902/260/905 dry-run；空仓账户只能执行新开仓信号，不能执行历史 shadow 的平仓回放。
- 若 `pending_orders` 为空，记录无交易，继续保持 fail-closed。
