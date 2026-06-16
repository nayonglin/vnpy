# Stage098 C9/15w 实盘 1 手 smoke 完整报撤通过

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：day
- 记录时间：2026-06-16 14:13 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：官方实盘执行链路 smoke/TCA/对账验收
- 是否重要突破：是，首次在生产实盘 CTP 上完成 `send_order=1/cancel_order=1/trade_volume=0/账户空仓`
- 是否触发A/B：否，执行验收不改 C9 策略版本

## 外部调研与判断

- 参考资料：
  - CTP API 文档 `ReqOrderInsert`：报单录入错误会对应 `OnRspOrderInsert`、`OnErrRtnOrderInsert`，正确报单会对应 `OnRtnOrder`、`OnRtnTrade`。
  - CTP API 文档 `OnErrRtnOrderInsert`：字段错误或 CTP 拒单通过错误回报返回。
  - 本地 `vnpy_ctp/gateway/ctp_gateway.py`：实际实现中 `onRspOrderInsert(data,error,reqid,last)` 会写 `交易委托失败`，`onRtnOrder(data)` 原始字段含 `StatusMsg`，但 vn.py `OrderData` 不保留 `StatusMsg`。
- 我的判断：
  - 用户 App 里看到的 `委托数量不符合最小开仓数量限制` 不应只依赖人工观察；脚本必须捕获原始 CTP 回调与订单 `StatusMsg`。
  - Stage097 旧 smoke 没有捕获原文，是执行观测缺口，不是策略问题。
  - 本次只补执行证据，不反馈 C9 参数，因此不构成策略过拟合。

## 本次变更

- 新增脚本：无。
- 修改脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_stage932_official_live_ctp_smoke_order.py`
    - 新增 `onRspOrderInsert/onErrRtnOrderInsert/onRspOrderAction/onErrRtnOrderAction/onRtnOrder` 原始回调捕获。
    - 新增 `raw_orders_csv/order_insert_errors_csv/order_action_errors_csv/callback_capture_errors_csv` 输出。
    - 新增当前订单 `vt_orderid` 过滤，区分当前 smoke 订单状态消息与账户历史订单状态消息。
- 删除脚本：无。
- 新增参数：无策略参数；新增 smoke 运行时输出字段 `current_order_raw_status_messages/all_raw_order_status_messages/observed_error_message_count`。
- 修改参数：smoke 品种从 `MA609.CZCE` 改为 `rb2610.SHFE`，原因是 MA 被柜台限制 1 手开仓。
- 删除参数：无。

## 回测/归因参数

- 数据区间：不适用，本阶段为实盘执行 smoke。
- 账户规模：C9/15w 官方 live default，实盘账户只读快照约 `150000.45`。
- 成本口径：不适用；本次成交 `0`。
- 样本过滤：只允许 1 手、生产 live env、Stage927 permitted、只读账户空仓且快照新鲜。
- 策略/归因口径：`official_live_stage847_c9_15w_stage819_05r_stop_retry_once`，但 smoke 订单不来自策略信号，只验证 CTP 报撤通道。

## 结果

- 期末权益：不适用。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：0，本次无成交。
- 总交易次数：0，本次无成交。
- 胜率：不适用。
- 其他关键指标：
  - Stage930 前置 dry-run：`order_api_called_count=0`，`rb2610.SHFE` 与 `MA609.CZCE` 收到 tick，账户 `confirmed_flat`、非零持仓 `0`。
  - Stage932 `rb2610.SHFE` dry-run：`Long Open 1 @3025`，当时 last `3175` 左右，价格理由 `limit_down_buy_open_far_passive`。
  - Stage927 一次性 arming：`real_submit_arming_permitted_ready`，`real_submit_permitted=1`，blocking `0`，订单 API `0`。
  - Stage932 submit-cancel：`vt_orderid=CTP.17_-390942763_1`，`send_order_api_called_count=1`，`cancel_order_api_called_count=1`，`order_api_called_count=2`，`trade_volume=0.0`，`status=submit_cancel_attempted`，`smoke_passed=1`。
  - 当前 rb 订单状态链：`报单已提交 -> 未成交 -> 已撤单`。
  - 捕获到 Stage097 MA 旧拒单原文：`700:已撤单报单被拒绝CZCE:出错: 委托数量不符合最小开仓数量限制`，该消息来自历史/当日订单查询，不属于本次 rb 订单。
  - Post-smoke Stage930 对账：账户 `confirmed_flat`、非零持仓 `0`、Stage906 `reconcile_aligned`、Stage930 订单 API `0`。
  - Stage927 已恢复 fail-closed：`real_submit_permitted=0`、`env_real_submit_enabled=0`、blocking `0`、订单 API `0`。
  - 两个 session daemon launchd 仍为 `dry-run + submit disabled`，当前未运行。

## 输出文件

- report：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage932_official_live_ctp_smoke_order_report_20260616_140951_stage932_official_live_ctp_smoke_order_v1.md`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage930_official_live_c9_session_daemon_report_20260616_141135_stage930_official_live_c9_session_daemon_v1.md`
- summary：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage932_official_live_ctp_smoke_order_summary_20260616_140951_stage932_official_live_ctp_smoke_order_v1.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage930_official_live_c9_session_daemon_summary_20260616_141135_stage930_official_live_c9_session_daemon_v1.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage927_official_live_real_submit_arming_gate_summary_20260616_stage927_official_live_real_submit_arming_gate_v1.json`
- orders：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage932_official_live_ctp_smoke_order_orders_20260616_140951_stage932_official_live_ctp_smoke_order_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage932_official_live_ctp_smoke_order_raw_orders_20260616_140951_stage932_official_live_ctp_smoke_order_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage932_official_live_ctp_smoke_order_order_insert_errors_20260616_140951_stage932_official_live_ctp_smoke_order_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage932_official_live_ctp_smoke_order_order_action_errors_20260616_140951_stage932_official_live_ctp_smoke_order_v1.csv`
- daily：不适用。
- quality：`py_compile` 通过；post-smoke 只读对账通过。

## 结论

- 本阶段结论：
  - 回答用户问题：旧脚本没有捕获到 MA 拒单原文；本次已补上 raw CTP 回调与 `StatusMsg` 捕获，并在 raw orders 中看到原文。
  - 第二次 smoke 换 `rb2610.SHFE` 后完整报撤通过，证明生产 CTP 的真实 `send_order/cancel_order` 链路可达。
  - 本次无成交、无残留持仓，账户对账 aligned。
  - 但 Stage930/931 尚未切为自动 `live-real`，仍保持 dry-run/disabled；这是有意 fail-closed。
- 是否进入下一步：可以进入“切 Stage930/931 live-real 运行配置”的最后部署步骤，但必须在用户明确确认后操作。
- 下一步：
  - 若用户确认，更新 launchd session daemon 参数到 `--mode live-real --submit-mode live-real`，并确保环境注入 `OFFICIAL_LIVE_PHASE_D_REAL_SUBMIT_ENABLED=1`。
  - 切换后立即跑一次 no-intent/live-real dry-run-equivalent cycle，确认无 ready intents 时订单 API 仍为 `0`。
  - 夜盘/日盘真实信号出现时，依赖 Stage927、Stage931、账户/持仓强对账、kill switch 和 TCA 报告。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段只改执行观测与报撤验收，不改策略参数、品种池、方向、R 倍数、重试次数或回测窗口；更换 smoke 品种是为绕开柜台最小开仓限制，不是策略调参。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是。
- 原因：完全自动化真实开平仓必须证明真实报撤链路、拒单文本捕获和 post-trade 对账；现在这些关键执行证据已补齐，继续价值从 smoke 转向 live-real 守护部署与日内风险控制。

## 合入建议

- 是否更新本线 `LINE.md`：是，标记 Stage098 报撤 smoke 通过。
- 是否更新 `research/registry.md`：是，更新当前最新阶段和下一步。
- 是否追加根目录 `memory.md/back_log.md`：是，本次是实盘执行里程碑。
