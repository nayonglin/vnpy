# Stage096 C9/15w 会话级自动化执行骨架

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：2026-06-16 13:44 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：官方实盘 C9/15w 执行自动化、会话守护进程、真实提交适配器硬闸门
- 是否重要突破：是。自动化从 timed report 推进到交易时段 tick 监控 + 执行意图 + 受控提交适配器。
- 是否触发A/B：否。本阶段不改 C9 alpha、不改参数、不产生新策略版本。

## 外部调研与判断

- 参考资料：
  - vn.py `MainEngine.send_order/cancel_order/subscribe` 源码接口：<https://github.com/vnpy/vnpy/blob/master/vnpy/trader/engine.py>
  - vn.py CTA 自动交易模块文档：<https://www.vnpy.com/docs/cn/community/app/cta_strategy.html>
  - `vnpy_ctastrategy` 说明：<https://pypi.org/project/vnpy_ctastrategy/>
- 我的判断：
  - C9 的 entry-day 实时止损不是日终 cron 能完整覆盖的事情；只要开仓当天有持仓，就必须在交易时段内持续接收 tick 或至少高频刷新 tick 快照，计算 Stage904 的触发条件，再由 Stage905 生成执行意图。
  - vn.py 的实盘执行边界很清楚：行情订阅、订单提交、撤单都应通过 gateway/MainEngine 的事件回调闭环。因此架构上应该是会话守护进程，而不是只靠 21:05 报告。
  - 真实自动开平仓必须和影子盘/只读/干跑分层隔离。当前先把真实提交代码准备好，但默认保持 `dry-run + submit disabled`，用 Stage927、env、confirm text、kill switch 和账户/持仓强对账作为硬闸门。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_stage930_official_live_c9_session_daemon.py`
  - `examples/portfolio_backtesting/run_qmt_roll_stage931_official_live_ctp_submit_adapter.py`
- 修改脚本：
  - `examples/portfolio_backtesting/qmt_roll_official_live_phase_d_config.py`
- 新增部署文件：
  - `examples/portfolio_backtesting/launchd/local.qmt-roll.official-live.15w.c9-night-session.plist`
  - `examples/portfolio_backtesting/launchd/local.qmt-roll.official-live.15w.c9-day-session.plist`
- 删除脚本：无
- 新增参数：
  - Stage930：`--mode dry-run|live-real`、`--submit-mode disabled|live-real`、`--tick-refresh-mode skip|plan-only|refresh`、`--readonly-refresh-mode plan-only|refresh|auto`、`--shadow-refresh-mode plan-only|run|auto`、`--duration-seconds`、`--poll-seconds`、`--confirm-live-real`
  - Stage931：`--mode dry-run|live-real`、`--confirm-live-real`、`--max-orders`、`--connect-wait-seconds`、`--fill-wait-seconds`、`--post-cancel-wait-seconds`
- 修改参数：
  - `READONLY_TICKS_PATH` 改为 Stage608 只读 tick snapshot 输出：`qmt_roll_stage608_readonly_tick_snapshot_probe_ticks_stage608_readonly_tick_snapshot_probe_v1.csv`
- 删除参数：无

## 回测/归因参数

- 数据区间：无新增策略回测；执行自检目标日 `2026-06-16`
- 账户规模：当前官方 live default `150000`
- 成本口径：无新增成本压力回测
- 样本过滤：当前交易会话 `day_pm`，watchlist 来自 pending/signal/current positions，实测为 `MA609.CZCE`
- 策略/归因口径：C9/15w `official_live_stage847_c9_15w_stage819_05r_stop_retry_once`，执行层 `dry-run + submit disabled`

## 结果

- 期末权益：不适用，本阶段不是策略回测
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：不适用
- 总交易次数：不适用
- 胜率：不适用
- 其他关键指标：
  - Stage930 编译通过；Stage931 编译通过。
  - Stage930 plan-only 单轮自检通过：`daemon_status=daemon_completed_max_cycles`、`watched_symbols=["MA609.CZCE"]`、Stage903 `phase_d_controller_dry_run_blocked`、Stage904 `intraday_monitor_ready`、Stage905 `executor_no_intents`、订单 API `0`。
  - Stage930 生产只读 tick 单轮自检通过：2026-06-16 13:41 CST 连接生产 CTP，只读订阅 `MA609.CZCE`，`tick_rows=25`，`subscribe_api_called_count=1`，TD/MD 连接、认证、登录成功。
  - Stage608 broker snapshot：`position_snapshot_state=confirmed_flat`、`nonzero_position_rows=0`、`send_order_api_called_count=0`、`cancel_order_api_called_count=0`。
  - Stage903：`stage907_refresh_status=readonly_refresh_completed_snapshot_ready`、Stage904 `intraday_monitor_ready`、Stage905 `executor_no_intents`、Stage906 `reconcile_aligned`、Stage908 `live_submit_permitted=0`、订单 API `0`。
  - Stage931 dry-run 自检：`adapter_status=adapter_blocked`、`ready_intent_count=0`、blocker `no_ready_stage905_intents`、`order_api_called_count=0`。
  - `launchd` 已加载两个会话任务：夜盘 `20:55`、日盘 `08:55`，均为 `dry-run + submit disabled`。

## 输出文件

- report：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_live_c9_session_daemon_latest_report.md`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage931_official_live_ctp_submit_adapter_report_20260616_stage931_official_live_ctp_submit_adapter_v1.md`
- summary：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_live_c9_session_daemon_latest_summary.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage931_official_live_ctp_submit_adapter_summary_20260616_stage931_official_live_ctp_submit_adapter_v1.json`
- orders：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage931_official_live_ctp_submit_adapter_orders_20260616_stage931_official_live_ctp_submit_adapter_v1.csv`
- daily：不适用
- quality：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_live_c9_session_daemon_heartbeat.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_live_c9_session_daemon_events.ndjson`

## 结论

- 本阶段结论：
  - 自动化已经从“定时跑报告”推进到“交易时段会话守护”：会自动发现关注合约、刷新只读 tick、刷新账户/持仓、运行 Stage904 日内监控、生成 Stage905 执行意图，并在需要时可接 Stage927/Stage931。
  - 当前不是已经打开真实自动开平仓。已部署的 `launchd` 会话任务仍是 `dry-run + submit disabled`，真实下单路径只有代码和闸门，未武装。
  - 若要真的自动开平仓，必须额外通过 Stage927 `real_submit_permitted=1`、设置 `OFFICIAL_LIVE_PHASE_D_REAL_SUBMIT_ENABLED=1`、精确确认 `I_UNDERSTAND_THIS_ENABLES_FULL_AUTO_CTP_LIVE_TRADING`、kill switch 未激活、账户/持仓/意图对账一致，并把 Stage930/Stage931 切到 `live-real`。
- 是否进入下一步：是，但下一步是受控真实开关评审，不是继续调策略。
- 下一步：
  - 等今晚会话自动 dry-run 运行后检查 tick/intent/reconcile/heartbeat。
  - 若用户明确要求打开真实自动开平仓，应先跑 Stage927 arming gate，再做一轮最小单元真实提交/撤单或小额 smoke 风险评审，最后再改 launchd 为 live-real。
  - 中期应把 Stage930 从“每轮重连刷新 tick 快照”升级为真正长连接事件循环，降低频繁重连成本。

## 过拟合反思

- 运行前判断：否。本阶段是执行自动化和风控闸门，不调整 C9 入场、止损、重试、品种、方向或资金参数。
- 运行后判断：否。实测只产生执行状态和只读 tick 证据，没有把结果反馈进 alpha。
- 原因：所有输出都是 fail-closed 的执行证据；真实提交默认禁用，不能因为某一日行情或某一笔交易调整策略逻辑。

## 继续价值反思

- 运行前判断：是。用户目标是完全自动化执行，entry-day 实时止损必须有交易时段守护进程。
- 运行后判断：是。Stage930/931 已把自动计算、tick 监控、意图生成和受控提交路径打通；剩余价值集中在真实开关验收、低频重连改长连接、TCA/对账闭环。
- 原因：C9 的执行风险主要在“开仓当天必须按 tick 判断”和“真实账户状态必须与策略意图一致”，这不是日终报告能解决的。

## 合入建议

- 是否更新本线 `LINE.md`：是，当前状态应从 timed report 自动化升级为会话级 dry-run 自动化已部署。
- 是否更新 `research/registry.md`：是，这是官方实盘执行链路重要里程碑。
- 是否追加根目录 `memory.md/back_log.md`：是，属于官方实盘自动化重要里程碑。
