# Stage259 SimNow 1手Submit-Cancel链路实测

- line_id：futures_trend
- 当前模式：day
- 记录时间：2026-05-13 13:56
- 阶段性质：SimNow-only 1手虚拟委托/撤单链路实测
- 是否重要突破：是
- 是否触发A/B：否，本阶段不修改策略、不比较收益、不引入新alpha

## 外部调研与判断

- 本阶段没有新增外部调研，沿用Stage258对 vn.py/VeighNa `OrderRequest`、`send_order`、`CancelRequest`、`cancel_order` 的本地源码审计结论。
- 判断：本次只验证SimNow虚拟盘执行链路，不代表Stage78-1策略可以直接按正常手数自动运行。

## 本次变更

- 修改 `examples/portfolio_backtesting/run_ctp_stage174_readonly_probe.py`
  - 写出 `vt_symbol`、`vt_orderid`、`vt_accountid` 等运行时字段。
  - 当CTP返回持仓明细但全部 `volume=0/frozen=0` 时，识别为 `confirmed_flat`。
  - 新增 `nonzero_position_rows` 输出。
- 修改 `examples/portfolio_backtesting/run_qmt_roll_stage245_phaseb_duplicate_and_target_checks.py`
  - 重复委托检查改用同一 `orderid/vt_orderid` 的最新状态。
  - 补充 `Not Traded`、中文状态等活跃委托状态归一。
  - `vt_symbol` 缺失时用 `symbol.exchange` 回填。

## 新增参数

- 无策略参数新增。

## 修改参数

- 无策略参数修改。

## 删除参数

- 无。

## 本次运行

### 提交前只读快照

- 命令：`env SIMNOW_FRONT=trading bash examples/portfolio_backtesting/run_ctp_stage177_simnow_readonly_probe.sh --connect --wait-seconds 120`
- 时间：2026-05-13 13:46
- 状态：`readonly_snapshots_received`
- 持仓语义：`confirmed_flat`
- 持仓行：`0`
- 持仓查询回调：`21`
- `order_api_called`：`false`

### Submit-Cancel

- 命令：`env SIMNOW_FRONT=trading SIMNOW_SMOKE_ORDER_ENABLED=1 bash examples/portfolio_backtesting/run_ctp_stage258_simnow_smoke_order.sh --mode submit-cancel --vt-symbol rb2610.SHFE --direction long --volume 1 --connect-wait-seconds 20 --tick-wait-seconds 40 --cancel-after-seconds 8 --post-cancel-wait-seconds 20 --confirm-submit I_UNDERSTAND_THIS_SENDS_SIMNOW_VIRTUAL_ORDERS`
- 时间：2026-05-13 13:48
- 合约：`rb2610.SHFE`
- 方向：买开
- 手数：`1`
- 最新tick：`last=3255`, `bid1=3254`, `ask1=3255`
- 委托价格：`3234`
- 委托编号：`CTP.1_281656631_1`
- `send_order_api_called_count`：`1`
- `cancel_order_api_called_count`：`1`
- 脚本状态：`submit_cancel_attempted`
- 成交行数：`0`

### 提交后复核

- 命令：`env SIMNOW_FRONT=trading bash examples/portfolio_backtesting/run_ctp_stage177_simnow_readonly_probe.sh --connect --wait-seconds 120`
- 时间：2026-05-13 13:54
- 状态：`readonly_snapshots_received`
- 持仓语义：`confirmed_flat`
- 持仓行：`14`
- 非零持仓行：`0`
- 订单最终状态：`Cancelled`
- 成交行数：`0`
- 结论：委托已撤，未成交，账户实际仍为空仓。

## 输出文件

- Submit-cancel summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage258_simnow_smoke_order_summary_20260513_134849_stage258_simnow_smoke_order_v1.json`
- Submit-cancel report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage258_simnow_smoke_order_report_20260513_134849_stage258_simnow_smoke_order_v1.md`
- 提交后只读 summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage174_ctp_vnpy_readonly_probe_summary_stage174_ctp_vnpy_readonly_probe_v1.json`
- 提交后只读 orders：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage174_ctp_vnpy_readonly_probe_orders_stage174_ctp_vnpy_readonly_probe_v1.csv`
- 提交后只读 positions：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage174_ctp_vnpy_readonly_probe_positions_stage174_ctp_vnpy_readonly_probe_v1.csv`

## 新增回测结果

- 无。本阶段没有运行回测。

## 修改回测结果

- 无。

## 删除回测结果

- 无。

## 固定指标占位

- 期末权益：无，本阶段无回测。
- 总收益：无，本阶段无回测。
- 最大回撤：无，本阶段无回测。
- Sharpe：无，本阶段无回测。
- 总滑点：无，本阶段无回测。
- 总交易次数：无，本阶段无回测。
- 胜率：无，本阶段无回测。

## 结论

- SimNow 1手虚拟委托/撤单链路已实测打通。
- `rb2610.SHFE` 买开1手被动限价单成功送出，并成功撤销。
- 没有成交，没有非零持仓残留。
- 发现并修复了只读探针零持仓行语义和重复委托最新状态判断问题。
- 仍不建议直接进入正常策略手数；下一步应做“虚拟盘日常执行SOP的单日委托草案 -> SimNow执行 -> 对账”闭环。

## 过拟合反思

- 运行前判断：否。本阶段只验证执行通道，不修改策略参数。
- 运行后判断：否。本阶段不影响回测收益和策略选择，只提升执行安全性。

## 继续价值反思

- 运行前判断：有价值。连通性恢复后必须验证真实报单/撤单生命周期。
- 运行后判断：有价值。最小链路已经闭环，下一步可以开始做SimNow虚拟盘日常SOP，而不是继续停留在只读。

## TODO

- 将下一次真实策略信号转成Phase B委托草案，但仍只在SimNow虚拟盘执行。
- 每次执行后必须跑提交后只读复核，确认订单最终态、成交、持仓、账户状态。
- 只有连续若干次虚拟盘执行/对账稳定后，才讨论正常策略手数或更接近实盘的执行流程。
