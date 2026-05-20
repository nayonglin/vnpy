# Stage268 券商CTP测试柜台1手报撤链路实测

- 时间：2026-05-19 13:50
- 所属研究线：futures_trend
- 工作模式：day
- 阶段性质：执行工程 / CTP测试柜台 smoke order
- 是否重要突破版本：否，不改变Stage78-1策略；但属于实盘前执行链路关键里程碑

## 本次目标

在用户明确确认当前为测试环境后，验证 Mac + vn.py + 券商CTP测试柜台是否可以完成：

1. 连接行情/交易前置
2. 登录行情/交易
3. 通过交易授权
4. 确认结算
5. 订阅实时tick
6. 发送1手测试委托
7. 收到委托回报
8. 撤销该委托
9. 确认最终未成交或记录成交

## 本次代码/SOP变更

- 新增 `examples/portfolio_backtesting/run_ctp_stage268_broker_test_smoke_order.sh`
  - 读取 `ctp_broker_test.local.env`
  - 复用 Stage258 smoke-order 核心逻辑
  - 设置 `SIMNOW_FRONT=broker-test` 作为输出里的环境标签
- 更新 `examples/portfolio_backtesting/run_ctp_stage258_simnow_smoke_order.py`
  - 文案从 SimNow-only 调整为更中性的 CTP test smoke order
  - 新增 `CTP_SMOKE_ORDER_ENABLED=1`
  - 新增确认文本 `I_UNDERSTAND_THIS_SENDS_CTP_TEST_ORDERS`
  - 继续兼容旧 `SIMNOW_SMOKE_ORDER_ENABLED` 和旧确认文本，便于历史SimNow结果复现
- 更新 `skills/stage78-simnow-shadow-sop/SKILL.md`
  - 新增 Broker-Test CTP Workflow
  - 固化 fresh readonly -> dry-run -> 1手 submit-cancel -> 订单/成交/持仓复核
- 更新 `AGENTS.md`、`skills/stage78-simnow-shadow-sop/agents/openai.yaml`、`research/lines/futures_trend/LINE.md`、`research/registry.md`

## 执行命令

只读快照刷新：

```bash
bash examples/portfolio_backtesting/run_ctp_stage267_broker_test_readonly_probe.sh --connect --wait-seconds 20
```

dry-run，不调用下单API：

```bash
bash examples/portfolio_backtesting/run_ctp_stage268_broker_test_smoke_order.sh --mode dry-run --vt-symbol MA609.CZCE --direction long --volume 1 --connect-wait-seconds 8 --tick-wait-seconds 20
```

1手测试报撤：

```bash
CTP_SMOKE_ORDER_ENABLED=1 bash examples/portfolio_backtesting/run_ctp_stage268_broker_test_smoke_order.sh --mode submit-cancel --vt-symbol MA609.CZCE --direction long --volume 1 --connect-wait-seconds 8 --tick-wait-seconds 20 --cancel-after-seconds 8 --post-cancel-wait-seconds 15 --confirm-submit I_UNDERSTAND_THIS_SENDS_CTP_TEST_ORDERS
```

## 结果

- CTP只读快照：`readonly_snapshots_received`
- 行情服务器连接：成功
- 交易服务器连接：成功
- 行情服务器登录：成功
- 交易服务器授权验证：成功
- 交易服务器登录：成功
- 结算信息确认：成功
- 合约信息查询：成功
- fresh readonly age：约 `41.775` 秒，通过
- dry-run：`dry_run_request_ready`

测试委托：

- 合约：`MA609.CZCE`
- 方向：`Long / Open`
- 手数：`1`
- 委托价：`2944.0`
- 委托编号：`CTP.5_-140689176_1`
- `send_order_api_called_count`：`1`
- `cancel_order_api_called_count`：`1`
- 订单状态流：`Submitting -> Not Traded -> Cancelled`
- 最终状态：`Cancelled`
- 成交行数：`0`
- 成交数量：`0`

## 输出文件

- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage258_simnow_smoke_order_summary_20260519_133941_stage258_simnow_smoke_order_v1.json`
- orders：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage258_simnow_smoke_order_orders_20260519_133941_stage258_simnow_smoke_order_v1.csv`
- trades：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage258_simnow_smoke_order_trades_20260519_133941_stage258_simnow_smoke_order_v1.csv`
- readonly summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage174_ctp_vnpy_readonly_probe_summary_stage174_ctp_vnpy_readonly_probe_v1.json`

## 结论

券商CTP测试柜台的最小执行链路已经打通：连接、行情订阅、报单、委托回报、撤单、撤单回报均可用。

这不代表可以直接用Stage78-1正常手数交易。下一步应进入策略执行闭环：

1. 每日先生成Stage78-1 50万口径目标信号。
2. 刷新券商CTP只读账户/持仓/挂单快照。
3. 比较策略目标仓位与CTP实际持仓。
4. 只允许通过风险闸门、持仓闸门、重复委托闸门的委托进入草案。
5. 先用小手数或人工审批方式执行，再做订单/成交/撤单/持仓对账。

## 过拟合判断

否。本阶段只验证测试柜台执行通道，不修改策略参数、AI品种池、信号逻辑、资金管理或回测结果。

## 继续价值判断

有价值。此前链路只到只读账户/持仓/合约快照；现在已验证测试环境报单和撤单闭环，Stage78-1 可以进入“策略目标仓位 vs CTP账户状态”的真实对账层。

## TODO

1. 将 Stage260/Phase B 的默认只读刷新参数改为可选 `broker-test`。
2. 生成一份“策略目标仓位 vs CTP实际持仓 vs 活跃委托”的日报。
3. 对可执行策略信号继续使用人工审批和 fail-closed 闸门，不直接进入正常策略手数。
