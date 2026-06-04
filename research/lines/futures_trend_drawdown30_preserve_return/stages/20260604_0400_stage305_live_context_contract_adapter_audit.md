# Stage305 Live Context Contract Adapter 审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-04 04:00 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读执行合同审计；不重放策略、不修改策略、不连接 CTP、不调用 `send_order`。
- 是否重要突破：否。执行链路缺口被工程化收敛，但尚未形成可部署候选。
- 是否触发A/B：否。没有新策略版本，没有收益改善候选，也没有真实执行/TCA样本。

## 外部调研与判断

- 参考资料：
  - VeighNa 订单/成交回报讨论：https://www.vnpy.com/forum/post/69782
  - vn.py event-driven architecture reference：https://deepwiki.com/vnpy/vnpy/2.1-main-engine-and-event-system
  - vn.py MainEngine reference：https://deepwiki.com/vnpy/vnpy/2.2-main-engine
  - vn.py custom gateway order contract reference：https://deepwiki.com/vnpy/vnpy/7.2-creating-custom-gateways
- 本地源码证据：
  - `vnpy/trader/engine.py`：`MainEngine.send_order` 委托 gateway 并返回 `gateway.send_order(req)`；OMS 缓存 `EVENT_TICK/EVENT_ORDER/EVENT_TRADE/EVENT_POSITION/EVENT_ACCOUNT/EVENT_CONTRACT`。
  - `vnpy/trader/object.py`：`OrderRequest.reference` 可携带 `Stage526TCA:<bridge_signal_id>`；`OrderData/TradeData` 生成 `vt_orderid`。
  - `vnpy/trader/gateway.py`：`on_order/on_trade/on_tick` 推送事件；`BaseGateway.send_order` 合同要求返回 `vt_orderid`。
- 我的判断：
  - vn.py 框架能力不是当前瓶颈；`reference -> vt_orderid -> order/trade/tick event` 这条原始合同存在。
  - 当前瓶颈是项目 adapter 没有把 fresh live context、真实 `vt_orderid`、`EVENT_ORDER/EVENT_TRADE/EVENT_TICK` 归并为 TCA 账本。
  - 因此 Stage079/Stage526 类版本现在仍不能声明“真实交易不存在偏差”；最多只能说 dry-run 合同已具备。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage605_live_context_contract_adapter_audit.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `EXPECTED_P0_LIVE_SAMPLES_PER_SIGNAL = 3`
  - `ORDER_REFERENCE_PREFIX = Stage526TCA`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：只读 Stage591 submit plan/live context requirements、Stage587 live TCA ledger、vn.py 本地源码。
- 策略版本：无新增策略版本；Stage526/Stage591 执行桥接合同审计。
- 账户规模：不适用；本阶段不做收益回放。
- 成本口径：不适用；本阶段不计算滑点，只检查真实 TCA 所需字段。
- 安全约束：
  - `send_order_api_called_count = 0`
  - `ctp_connection_attempted = false`
  - 不生成 synthetic `vt_orderid`
  - 不允许 real submit

## 结果

- 新增交易回测：无
- 决策：`live_context_contract_ready_adapter_implementation_missing_no_submit`
- promotion allowed：`false`
- zero execution bias claim allowed：`false`
- 期末权益：无新增；Stage526 参考 `23,369,505`
- 总收益：无新增；Stage526 参考 `3699.9195%`
- 最大回撤：无新增；Stage526 参考 `-36.2670%`
- Sharpe：无新增；Stage526 参考 `1.6385`
- 总滑点：无新增；Stage526 参考 `1,342,190`
- 总交易次数：无新增；Stage526 参考 `905`
- 胜率：无新增；Stage526 非零日胜率参考 `53.6330%`
- 其他关键指标：
  - submit plan rows：`5`
  - P0 rows：`3`
  - dry-run payload ready rows：`5/5`
  - live context：`0/45`
  - real `vt_orderid` mappings：`0/5`
  - P0 required live TCA samples：`9`
  - P0 valid live TCA samples：`0/9`
  - hard gates：`6/10`
  - failed hard gates：`fresh_live_context_ready`、`real_vt_orderid_mapping_ready`、`order_trade_tick_join_ready`、`p0_valid_live_tca_samples_ready`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage605_live_context_contract_adapter_audit_report_stage605_live_context_contract_adapter_audit_v1.md`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage605_live_context_contract_adapter_audit_decision_stage605_live_context_contract_adapter_audit_v1.json`
- contract schema：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage605_live_context_contract_adapter_audit_contract_schema_stage605_live_context_contract_adapter_audit_v1.csv`
- implementation gap：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage605_live_context_contract_adapter_audit_implementation_gap_stage605_live_context_contract_adapter_audit_v1.csv`
- signal contract：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage605_live_context_contract_adapter_audit_signal_contract_stage605_live_context_contract_adapter_audit_v1.csv`
- chain progress：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage605_live_context_contract_adapter_audit_chain_progress_stage605_live_context_contract_adapter_audit_v1.csv`
- gates：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage605_live_context_contract_adapter_audit_gates_stage605_live_context_contract_adapter_audit_v1.csv`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage605_live_context_contract_adapter_audit_chart_stage605_live_context_contract_adapter_audit_v1.png`

## 图表视觉复盘

- 左上图显示 source、safety、adapter dry-run 层为绿；missing adapter、missing join、missing evidence 为红，说明问题不是 vn.py 框架能力，而是项目执行账本没有落地。
- 右上图显示 9 个 live context 字段全部为 `0/5`，即每个 submit plan 行都缺 contract/account/position/tick/limit/margin/operator context。
- 左下图显示 5 个信号全部只走到 `intent` 与 `payload`，从 `fresh_live_context` 开始全部为红。这比单一指标更清楚地说明断点统一发生在真实执行前。
- 右下图显示 hard gates 前 6 个通过，后 4 个失败；dry-run 安全性没问题，但真实无偏差仍不能宣称。

## 结论

- 本阶段结论：
  - Stage591 dry-run submit plan 已经具备 `OrderRequest.reference = Stage526TCA:<bridge_signal_id>` 合同。
  - vn.py 本地源码支持返回真实 `vt_orderid` 并通过事件系统捕获订单、成交、tick。
  - 当前缺的是 fresh live context adapter、真实 `vt_orderid` writer、order/trade/tick join reducer 和 P0 有效 TCA 样本。
  - 因此 Stage079/Stage526 类结构仍不能声明“真实交易不存在偏差”，也不能进入 A/B 或交易白名单。
- 是否进入下一步：进入工程实现下一步，不进入收益回测或选品白名单。
- 下一步：
  1. 实现只读/预提交 fresh live context collector：合约、账户、持仓、tick、涨跌停/price band、保证金、operator confirmation。
  2. 在真实测试环境 submit 后，立即持久化 `main_engine.send_order(req, gateway_name)` 返回的精确 `vt_orderid`；禁止 synthetic id。
  3. 将 `EVENT_ORDER/EVENT_TRADE/EVENT_TICK` 归并到 `bridge_signal_id + vt_orderid`，计算 avg fill、filled/unfilled/cancelled、VWAP、shortfall、participation。
  4. 对 `fu2509.SHFE/lc2505.GFEX/AP505.CZCE` 三个 P0 bucket 各补 `3` 个有效真实/独立分钟 TCA 样本。

## 过拟合反思

- 运行前判断：否。因为本阶段只做执行合同审计，不改策略参数、品种池、信号、仓位或历史成交口径。
- 运行后判断：否。输出是缺口和闸门，不是收益提升；没有使用历史赢家或窗口结果来生成新规则。
- 原因：本阶段只回答“回测能否被真实执行证据支持”，不回答“哪个参数更赚钱”。

## 继续价值反思

- 运行前判断：有价值。真实无偏差是当前目标的硬要求，继续扩池或选品前必须先闭合执行链。
- 运行后判断：有价值且优先级最高。图表显示所有信号在同一执行断点停止，说明下一步可以非常明确地做 adapter，而不是继续发散研究。
- 原因：只要 `0/45 live context`、`0/5 vt_orderid`、`0/9 P0 TCA` 不变，任何收益/回撤候选都不能成为真实可成交结构。

## 合入建议

- 是否更新本线 `LINE.md`：是，更新当前状态和下一步。
- 是否更新 `research/registry.md`：是，更新本线最新阶段摘要。
- 是否追加根目录 `memory.md/back_log.md`：否。没有正式候选或重要突破。
