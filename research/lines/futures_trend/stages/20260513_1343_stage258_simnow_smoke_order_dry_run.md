# Stage258 SimNow-only 1手委托链路Dry-run

- line_id：futures_trend
- 当前模式：day
- 记录时间：2026-05-13 13:43
- 阶段性质：SimNow-only 最小委托链路脚本 / dry-run验证
- 是否重要突破：是
- 是否触发A/B：否，本阶段不修改策略、不跑收益比较、不引入新alpha

## 外部调研与判断

- 本阶段参考 vn.py/VeighNa 的 `MainEngine.send_order`、`OrderRequest`、`CancelRequest` 与 CTP Gateway 委托/撤单接口结构。
- 判断：最小链路测试应独立于回测和影子盘脚本，不能把 `send_order` 塞进 Stage78-1 日报或回测入口。
- 判断：第一步只做 `dry-run`，实际 SimNow 虚拟委托必须重新刷 300 秒内新鲜只读快照，并由用户确认具体合约、方向、价格和1手数量。

## 本次变更

- 新增 `examples/portfolio_backtesting/run_ctp_stage258_simnow_smoke_order.py`
- 新增 `examples/portfolio_backtesting/run_ctp_stage258_simnow_smoke_order.sh`
- 修复脚本内 dataclass 转行时丢失 `vt_symbol` 的问题，使 tick 过滤按真实 `vt_symbol` 生效。

## 新增参数

- `--mode dry-run|submit-cancel`
- `--vt-symbol`
- `--direction`
- `--volume`
- `--passive-ticks-away`
- `--manual-price`
- `--connect-wait-seconds`
- `--tick-wait-seconds`
- `--cancel-after-seconds`
- `--post-cancel-wait-seconds`
- `--max-snapshot-age-seconds`
- `--confirm-submit`

## 修改参数

- 无策略参数修改。

## 删除参数

- 无。

## 本次运行

### 网络探针

- 命令：`.py311/bin/python examples/portfolio_backtesting/run_ctp_stage179_simnow_network_probe.py`
- 时间：2026-05-13 13:35
- 可达前置：`trading`, `trading2`, `trading_mobile`
- 当前不可达：`7x24_182`, `7x24_180`, `first_180_group1`, `first_180_group2`
- 判断：继续使用 `SIMNOW_FRONT=trading`

### 只读探针

- 60秒版本：拿到账户但持仓查询未完成，状态 `position_query_not_completed`，按规则 fail-closed。
- 120秒版本：状态 `readonly_snapshots_received`
- 持仓语义：`confirmed_flat`
- 账户持仓：空仓
- `order_api_called`：`false`

### Stage258 Dry-run

- 命令：`env SIMNOW_FRONT=trading bash examples/portfolio_backtesting/run_ctp_stage258_simnow_smoke_order.sh --mode dry-run --vt-symbol rb2610.SHFE --direction long --volume 1 --connect-wait-seconds 20 --tick-wait-seconds 40`
- 状态：`dry_run_request_ready`
- 合约：`rb2610.SHFE`
- 方向：买开
- 手数：`1`
- 最新tick：`last=3249`, `bid1=3249`, `ask1=3250`
- 被动测试限价：`3229`
- 逻辑：买一价下方20个tick，目标是提交后挂单并撤单，不追求成交。
- `send_order_api_called_count`：`0`
- `cancel_order_api_called_count`：`0`
- 注意：本次 dry-run 读取的只读快照年龄为 `367.470` 秒，超过300秒阈值；实际 submit-cancel 前必须重新刷只读快照。

## 输出文件

- Stage179报告：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage179_simnow_network_probe_report_stage179_simnow_network_probe_v1.md`
- Stage174 summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage174_ctp_vnpy_readonly_probe_summary_stage174_ctp_vnpy_readonly_probe_v1.json`
- Stage258 summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage258_simnow_smoke_order_summary_20260513_134307_stage258_simnow_smoke_order_v1.json`
- Stage258 report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage258_simnow_smoke_order_report_20260513_134307_stage258_simnow_smoke_order_v1.md`

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

- SimNow 第一套 `trading` 仍可达。
- 只读链路可以拿到 `confirmed_flat`，但需要足够等待时间，60秒不稳，120秒本次通过。
- Stage258 dry-run 已能拿到实时tick并构造1手被动测试委托。
- 本阶段没有发单，真实/虚拟委托API调用次数为0。
- 下一步若执行 submit-cancel，应先刷新 300 秒内只读快照，再用 `SIMNOW_SMOKE_ORDER_ENABLED=1` 和确认文本运行 submit-cancel。

## 过拟合反思

- 运行前判断：否。委托链路测试只验证执行通道，不修改策略参数。
- 运行后判断：否。dry-run 不改变策略、不影响回测收益、不产生实盘/虚拟盘持仓。

## 继续价值反思

- 运行前判断：有价值。SimNow通路恢复后，必须验证最小报单/撤单链路。
- 运行后判断：有价值。dry-run已通过，下一步可以在用户明确确认后做1手submit-cancel。

## TODO

- 用户明确确认后，重新运行120秒只读探针并在300秒内执行 `submit-cancel`。
- submit-cancel后检查订单、撤单、成交、持仓、账户快照，确认最终仍为空仓或记录异常。
- 若 submit-cancel 出现意外成交，先暂停正常策略手数，单独处理持仓回正。
