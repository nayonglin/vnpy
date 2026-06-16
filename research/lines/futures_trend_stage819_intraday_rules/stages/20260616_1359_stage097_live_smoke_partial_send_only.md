# Stage097 C9/15w 实盘 smoke 部分通过但未放行 live-real

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：2026-06-16 13:59 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：官方 C9/15w 实盘真实提交闸门、1 手 smoke、fail-closed 放行审计
- 是否重要突破：是。首次在当前 C9/15w 实盘账户上触达真实 `send_order` API。
- 是否触发A/B：否。本阶段只验证执行通道，不改策略参数。

## 外部调研与判断

- 参考资料：
  - vn.py `MainEngine.send_order/cancel_order/subscribe` 接口：<https://github.com/vnpy/vnpy/blob/master/vnpy/trader/engine.py>
  - vn.py CTA 自动交易模块文档：<https://www.vnpy.com/docs/cn/community/app/cta_strategy.html>
- 我的判断：
  - C9/15w 全自动开平仓应继续走 vn.py event/gateway 路径，但真实放行标准不能只看 `send_order`，还必须证明撤单、成交、对账和残余仓位处理闭环。
  - 本次 smoke 证明生产 CTP `send_order` 已可达；但由于订单在脚本主动撤单前已回到 `Cancelled`，没有产生 `cancel_order` API 调用，因此不能宣称“报撤链路完整通过”。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_stage932_official_live_ctp_smoke_order.py`
- 修改脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_stage932_official_live_ctp_smoke_order.py`：将成交统计限定为本次 `vt_orderid`，避免把登录时回放的历史 MA 成交误算成 smoke 成交；将撤单逻辑改成收到 active order 后立即撤。
- 删除脚本：无
- 新增参数：
  - Stage932：`--mode dry-run|submit-cancel`、`--confirm-live-real`、`--confirm-smoke`、`--max-stage927-age-seconds`、`--max-snapshot-age-seconds`、`--passive-ticks-away`、`--manual-price`
  - 新增 env gate：`OFFICIAL_LIVE_PHASE_D_REAL_SMOKE_ENABLED`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：无新增策略回测；执行目标日 `2026-06-16`
- 账户规模：当前官方 live default `150000`
- 成本口径：不适用
- 样本过滤：实盘生产 CTP，合约 `MA609.CZCE`
- 策略/归因口径：C9/15w `official_live_stage847_c9_15w_stage819_05r_stop_retry_once`，真实 smoke 限定 1 手

## 结果

- 期末权益：不适用
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：不适用
- 总交易次数：不适用
- 胜率：不适用
- 其他关键指标：
  - Stage925 ack suite 补跑通过：`account_recovery_ack_suite_passed_fail_closed`、`failed_count=0`、订单 API `0`。
  - Stage927 预检在 env 关闭时为 `real_submit_arming_ready_requires_explicit_enable`，blocking `0`、订单 API `0`。
  - 刷新 Stage930/608/903 后，生产只读 CTP 订阅 `MA609.CZCE`，tick `22` 条，账户 `confirmed_flat`，非零持仓 `0`，Stage904 ready、Stage905 no intents、Stage906 aligned，订单 API `0`。
  - Stage927 在一次性 env `OFFICIAL_LIVE_PHASE_D_REAL_SUBMIT_ENABLED=1` 下为 `real_submit_arming_permitted_ready`、`real_submit_permitted=1`、blocking `0`、订单 API `0`。
  - Stage932 dry-run 通过：拟报 `MA609.CZCE Long Open 1 @2533`，当时 last 约 `2686/2687`，价格理由 `limit_down_buy_open_far_passive`，订单 API `0`。
  - Stage932 submit-cancel 实盘调用：`vt_orderid=CTP.18_-442707628_1`，`send_order_api_called_count=1`、`cancel_order_api_called_count=0`、`order_api_called_count=1`、`trade_volume=0`、`smoke_passed=0`。
  - 订单回报：本次 `MA609.CZCE Long Open 1 @2533` 从 `Submitting` 进入 `Cancelled`，无本次成交。
  - smoke 后 Stage608/930 复核：账户 `confirmed_flat`、非零持仓 `0`，订单 API `0`；只读订单快照同样显示 `CTP.18_-442707628_1` 最终 `Cancelled`，无成交。
  - 结束前已重跑 Stage927 且不带 real-submit env，恢复为 `real_submit_permitted=0`、`real_submit_arming_ready_requires_explicit_enable`。

## 输出文件

- report：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage932_official_live_ctp_smoke_order_report_20260616_135641_stage932_official_live_ctp_smoke_order_v1.md`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage930_official_live_c9_session_daemon_report_20260616_135727_stage930_official_live_c9_session_daemon_v1.md`
- summary：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage932_official_live_ctp_smoke_order_summary_20260616_135641_stage932_official_live_ctp_smoke_order_v1.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage927_official_live_real_submit_arming_gate_summary_20260616_stage927_official_live_real_submit_arming_gate_v1.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage930_official_live_c9_session_daemon_summary_20260616_135727_stage930_official_live_c9_session_daemon_v1.json`
- orders：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage932_official_live_ctp_smoke_order_orders_20260616_135641_stage932_official_live_ctp_smoke_order_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage608_readonly_tick_snapshot_probe_orders_stage608_readonly_tick_snapshot_probe_v1.csv`
- daily：不适用
- quality：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage932_official_live_ctp_smoke_order_logs_20260616_135641_stage932_official_live_ctp_smoke_order_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage932_official_live_ctp_smoke_order_trades_20260616_135641_stage932_official_live_ctp_smoke_order_v1.csv`

## 结论

- 本阶段结论：
  - 生产 CTP 真实 `send_order` 通道已触达，且本次 1 手远价 smoke 无成交、最终订单状态 `Cancelled`、账户复核空仓。
  - 但主动 `cancel_order` API 未被调用，原因是脚本检查时订单已不处于 active 状态；因此本次不能算完整报撤 smoke 通过。
  - 已停止切 live-real，保持 `launchd` 为 `dry-run + submit disabled`，并把 Stage927 summary 恢复成 `real_submit_permitted=0`。
- 是否进入下一步：暂不自动进入 live-real。
- 下一步：
  - 若继续，应在用户再次明确允许第二次 1 手 smoke retry 后，用已修正的 Stage932 立即撤单逻辑重新验证 `cancel_order_api_called_count=1`。
  - 只有第二次 smoke 明确出现 `send_order=1/cancel_order=1/trade_volume=0/账户复核空仓` 后，才建议把 Stage930/931 切到 live-real。

## 过拟合反思

- 运行前判断：否。本阶段只做执行通道验收，不调 C9 参数。
- 运行后判断：否。真实 smoke 结果不反馈进策略收益、止损、重试或品种逻辑。
- 原因：它验证的是 broker API 行为和 fail-closed 纪律，不是历史样本收益。

## 继续价值反思

- 运行前判断：是。用户已授权实盘自动开平仓，必须先有真实最小 API 证据。
- 运行后判断：是，但不能跳步。`send_order` 已证明，`cancel_order` 仍需补验。
- 原因：无人值守策略遇到未成交挂单时必须能主动撤单；只证明下单不能满足自动执行安全边界。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 live-real 未放行原因。
- 是否更新 `research/registry.md`：是，当前 live-real 下一步改为二次 smoke retry，而不是直接切换。
- 是否追加根目录 `memory.md/back_log.md`：是，本阶段已真实触达实盘订单 API。
