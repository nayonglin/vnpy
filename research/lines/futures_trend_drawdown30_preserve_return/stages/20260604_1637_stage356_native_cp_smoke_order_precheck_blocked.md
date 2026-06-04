# Stage356：native CP 1手 smoke order 提交前闸门阻断

- 时间：2026-06-04 16:37 CST
- 研究线：`futures_trend_drawdown30_preserve_return`
- 决策：`native_cp_smoke_order_precheck_blocked_front_unreachable`
- 是否重要突破版本：否
- 是否连接 CTP：是，只读尝试
- 是否调用报单 API：否，`send_order_api_called_count=0`
- 是否调用撤单 API：否，`cancel_order_api_called_count=0`

## 本阶段目的

用户明确确认“测试环境 + 允许发 1 手测试单”后，按 Stage78/CTP smoke order SOP 执行提交前闸门：

1. 先刷新 300 秒内 read-only 账户/持仓/保证金快照。
2. read-only 成功后才允许进入 smoke order dry-run。
3. dry-run 成功后才允许使用显式 token 发 `1` 手 submit-cancel 测试单。

本阶段在第 1 步即失败，因此没有进入 dry-run，也没有进入 submit-cancel。

## 外部资料与判断

- CTP `ReqOrderInsert` 是报单录入请求；录入错误通过 `OnRspOrderInsert` / `OnErrRtnOrderInsert` 返回，正确录入后通过 `OnRtnOrder` / `OnRtnTrade` 回报。
- CTP `ReqOrderAction` 是撤单/报单操作请求。
- 因此本次 1 手测试单的正确工程目标不是追求成交，而是验证：`ReqOrderInsert` 可达、回报可捕获、必要时可撤单、最终不留残余仓位。

## 新增参数

无。

## 修改参数

无。

## 删除参数

无。

## 执行命令与证据

只读快照命令：

```bash
bash examples/portfolio_backtesting/run_ctp_stage656_native_cp_account_margin_probe.sh
```

结构化输出：

- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage656_native_cp_account_margin_probe_summary_stage656_native_cp_account_margin_probe_v1.json`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage656_native_cp_account_margin_probe_report_stage656_native_cp_account_margin_probe_v1.md`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage656_native_cp_account_margin_probe_raw_stage656_native_cp_account_margin_probe_v1.log`

只读快照结果：

- `generated_at=2026-06-04 16:36:32`
- `native_exit_code=0`
- `front_connected=false`
- `auth_ok=false`
- `login_ok=false`
- `settlement_ok=false`
- `account_rows=0`
- `position_rows=0`
- `explicit_margin_rows=0`
- `status=readonly_native_cp_no_account_margin_received`
- `system_info_source=collector_api:_Z28CTP_GetSystemInfoUnAesEncodePcRi`
- `system_info_len=264`
- `send_order_api_called_count=0`
- `cancel_order_api_called_count=0`

TCP 探测：

```text
182.140.218.46:41407 timeout
182.140.218.46:41415 timeout
182.140.218.46:41207 timeout
182.140.218.46:41215 timeout
```

## 回测结果

本阶段无策略回测、无收益曲线变更、无持仓变更。

- 期末权益：不适用
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：不适用
- 总交易次数：不适用
- 胜率：不适用

参考候选仍沿用 Stage353 `force95_to80_largest_margin`：

- 期末权益：`10,415,070`
- 总收益：`5107.5350%`
- 年化收益率：`86.8222%`
- 最大回撤：`-38.8730%`
- Sharpe：`1.6384`
- 总滑点：`597,710`
- 总交易次数：`655`
- 胜率：`52.3156%`
- broker10 峰值：`83.3212%`
- 强制减仓：`6` 次 / `317` 手

## 结论

本阶段不能发 1 手测试单。原因不是用户未授权，而是 fresh read-only snapshot 没有通过：`front_connected=false` 且 TCP 层对 `41407/41415/41207/41215` 均超时。

按 SOP 必须 fail closed：没有 300 秒内 read-only 账户快照，就不能 dry-run，更不能 submit-cancel。

## 反过拟合反思

否。本阶段是执行链路闸门验证，不改 alpha、不扫参数、不根据结果优化策略。

## 继续价值反思

有价值，但当前不能继续发单。下一步只应在券商前置 TCP 可达后重跑 Stage656；只有 `front/auth/login/settlement/account/position` 全部恢复，并且 dry-run 显示 request ready，才允许继续 1 手 submit-cancel。

## TODO

1. 在券商确认前置开放、网络可达或切换网络/VPN 后，重跑 Stage656 read-only。
2. read-only 成功后运行 Stage281 dry-run，验证 `send_order_api_called_count=0` 且 `dry-run ready`。
3. dry-run 通过后，再用显式 `CTP_NATIVE_SMOKE_ORDER_ENABLED=1` 和确认 token 发 `submit-cancel`。
4. 若 submit 成功，记录 `OrderRef / FrontID / SessionID / OrderSysID / OnRtnOrder / OnRtnTrade / cancel`，并补入 live TCA bridge；不要把本次阻断误记为执行成功。
