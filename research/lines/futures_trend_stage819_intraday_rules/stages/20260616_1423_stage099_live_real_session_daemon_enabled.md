# Stage099 C9/15w session daemon 切换 live-real

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：day
- 记录时间：2026-06-16 14:23 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：官方实盘自动执行部署
- 是否重要突破：是，Stage930/931 session daemon 已从 `dry-run + submit disabled` 切为 scheduled `live-real`
- 是否触发A/B：否，执行部署不改策略版本

## 外部调研与判断

- 参考资料：
  - vn.py/MainEngine/Gateway 架构资料：vn.py 通过 `MainEngine` 和事件引擎向 gateway 路由 `send_order/cancel_order/subscribe`，自动交易需要常驻事件循环处理行情和订单回报。
  - Apple launchd 文档：`launchd.plist` 用 `ProgramArguments`、`EnvironmentVariables`、`StartCalendarInterval` 管理定时用户级任务。
- 我的判断：
  - C9 入场日有实时止损/重试语义，不能只依赖日终 cron；应使用 session daemon 覆盖交易时段 tick、对账和执行。
  - live-real 切换必须落在 launchd plist 的持久参数和环境变量里，不能只靠临时 shell export。
  - 当前不手动 kickstart 长跑日盘守护，避免从 14:20 启动一个跨收盘的 day session；夜盘按 `20:55` 自动触发更符合时段边界。

## 本次变更

- 新增脚本：无。
- 修改脚本：无。
- 删除脚本：无。
- 修改 launchd：
  - `examples/portfolio_backtesting/launchd/local.qmt-roll.official-live.15w.c9-day-session.plist`
  - `examples/portfolio_backtesting/launchd/local.qmt-roll.official-live.15w.c9-night-session.plist`
  - 两个 plist 均从 `--mode dry-run --submit-mode disabled` 改为 `--mode live-real --submit-mode live-real`。
  - 两个 plist 均新增 `--confirm-live-real I_UNDERSTAND_THIS_ENABLES_FULL_AUTO_CTP_LIVE_TRADING`。
  - 两个 plist 均新增环境变量：
    - `OFFICIAL_LIVE_PHASE_D_REAL_SUBMIT_ENABLED=1`
    - `OFFICIAL_LIVE_PHASE_D_REAL_ADAPTER_IMPLEMENTED=1`
    - `OFFICIAL_LIVE_PHASE_D_SESSION_DAEMON_ENABLED=1`
- 新增参数：无策略参数。
- 修改参数：仅执行运行态。
- 删除参数：无。

## 回测/归因参数

- 数据区间：不适用。
- 账户规模：C9/15w 官方 live default。
- 成本口径：不适用，本阶段未成交、未下策略单。
- 样本过滤：不适用。
- 策略/归因口径：`official_live_stage847_c9_15w_stage819_05r_stop_retry_once`。

## 结果

- 期末权益：不适用。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：0，本阶段未成交。
- 总交易次数：0，本阶段未下策略单。
- 胜率：不适用。
- 其他关键指标：
  - `plutil -lint`：day/night 两个 plist 均 `OK`。
  - 手动 live-real/no-intent 单周期：
    - Stage930：`mode=live-real`、`submit_mode=live-real`、`order_api_called_count=0`。
    - Stage927：一次性 arming `real_submit_arming_permitted_ready`，`real_submit_permitted=1`，订单 API `0`。
    - Stage905：`executor_no_intents`，ready `0`。
    - Stage931：`adapter_blocked`，blocker `no_ready_stage905_intents`，`send_order=0/cancel_order=0/order_api=0`。
    - 账户只读：`confirmed_flat`、非零持仓 `0`。
    - Stage906：`reconcile_aligned`。
  - 安装后的 launchd：
    - `local.qmt-roll.official-live.15w.c9-day-session`：`state=not running`，`--mode live-real`，`--submit-mode live-real`，环境变量已注入，触发 `08:55`。
    - `local.qmt-roll.official-live.15w.c9-night-session`：`state=not running`，`--mode live-real`，`--submit-mode live-real`，环境变量已注入，触发 `20:55`。
  - 收尾安全：
    - 手动 Stage927 已恢复为 `real_submit_permitted=0`、`env_real_submit_enabled=0`、blocking `0`、订单 API `0`。
    - 当前没有运行中的 `Stage930/931/932/Stage608` 进程。

## 输出文件

- report：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage930_official_live_c9_session_daemon_report_20260616_142052_stage930_official_live_c9_session_daemon_v1.md`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage931_official_live_ctp_submit_adapter_report_20260616_stage931_official_live_ctp_submit_adapter_v1.md`
- summary：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage930_official_live_c9_session_daemon_summary_20260616_142052_stage930_official_live_c9_session_daemon_v1.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage931_official_live_ctp_submit_adapter_summary_20260616_stage931_official_live_ctp_submit_adapter_v1.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage927_official_live_real_submit_arming_gate_summary_20260616_stage927_official_live_real_submit_arming_gate_v1.json`
- orders：Stage931 orders/trades/submitted CSV 均为空或无提交。
- daily：不适用。
- quality：plist lint、manual live-real/no-intent cycle、launchctl print、进程检查均通过。

## 结论

- 本阶段结论：
  - C9/15w 的 session daemon 已正式切为 scheduled live-real。
  - 当前没有 ready intent，因此本阶段没有真实策略订单发送。
  - 夜盘 `20:55` 会自动启动 live-real session daemon；如果 2026-06-16 日线完成后 shadow 产生 pending/ready intent，Stage930/927/931 会按账户/持仓强对账、kill switch、Stage905 ready intent、Stage927 arming gate 执行。
  - 如果没有 ready intent，Stage931 会像手动验证一样阻断，订单 API 保持 `0`。
- 是否进入下一步：是，进入今晚 20:55 live-real session 运行观察与 21:05/21:10 报告验收。
- 下一步：
  - 20:55 后检查 night session daemon 是否启动、heartbeat/events 是否更新。
  - 21:05/21:10 检查 timed-cycle/latest 报告、Stage930 latest summary、Stage931 是否有 submitted rows。
  - 若有真实订单，立即做 TCA/成交/撤单/账户持仓对账；若无订单，确认 no-intent/no-order 状态。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段只切执行运行态，不改 C9 策略参数、信号逻辑、R 倍数、重试次数、月份、品种或方向；手动 no-intent cycle 是执行安全验证，不反馈策略优化。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是。
- 原因：完全自动化必须把已验收的 smoke/TCA/对账链路落到持久 session daemon；切换后继续价值转为实时观察、对账和 fail-closed 运维，而不是继续优化策略参数。

## 合入建议

- 是否更新本线 `LINE.md`：是，标记 Stage099 live-real session daemon 已部署。
- 是否更新 `research/registry.md`：是，更新当前最新阶段和下一步。
- 是否追加根目录 `memory.md/back_log.md`：是，本次是实盘自动执行部署里程碑。
