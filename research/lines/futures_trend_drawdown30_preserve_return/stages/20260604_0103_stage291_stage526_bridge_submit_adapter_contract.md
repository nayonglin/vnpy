# Stage291 Stage526 bridge-aware submit adapter 合同审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-04 01:03 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：执行证据链工程前置；不连接 CTP、不调用 `send_order`、不修改策略、不做收益回测。
- 是否重要突破：否，但属于 Stage526 真实执行偏差闭环的重要工程推进。
- 是否触发 A/B：否。本阶段没有形成交易候选，只把 Stage589 mapping 合同落成 adapter-facing `OrderRequest` payload 与 `vt_orderid` 写入策略。

## 外部调研与判断

- 参考资料：
  - vn.py 官方 Gitee `vnpy/trader/gateway.py`：gateway `send_order(req)` 的合同是创建委托、推送 `on_order`，并返回 `vt_orderid`。
  - DeepWiki 对 vn.py gateway 的源码索引：`send_order()` 返回 `{gateway_name}.{orderid}` 格式的 `vt_orderid`；`on_trade()` 推送 `EVENT_TRADE`，`on_order()` 推送 `EVENT_ORDER`。
  - VeighNa 社区示例：上层常见写法为 `vt_orderid = main_engine.send_order(req, contract.gateway_name)`，随后用该 id 更新订单请求/转换器状态。
- 我的判断：
  - Stage526 真实交易无偏差不能靠同日期同品种日志推断；必须在 submit adapter 层把 `bridge_signal_id` 和实际 `vt_orderid` 绑定。
  - `OrderRequest.reference = Stage526TCA:<bridge_signal_id>` 是人类/日志辅助 join key；权威 join key 仍是 `main_engine.send_order(req, gateway_name)` 返回的 `vt_orderid`。
  - 本阶段只能实现 fail-closed 合同，不能伪造 `vt_orderid`；任何 synthetic id 都会污染后续 TCA。

参考链接：

- https://gitee.com/vnpy/vnpy/blob/master/vnpy/trader/gateway.py?skip_mobile=true
- https://deepwiki.com/vnpy/vnpy/7.2-creating-custom-gateways
- https://www.vnpy.com/forum/post/55380

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage591_stage526_bridge_submit_adapter_contract.py`
- 修改脚本：
  - 无正式策略脚本修改。
  - 无 Stage78 Phase B 旧 adapter 修改，避免污染正式执行入口。
- 删除脚本：无。
- 新增输出：
  - submit plan
  - mapping writer contract
  - gates
  - decision
  - report
  - chart
- 新增合同字段/策略：
  - `OrderRequest.reference = Stage526TCA:<bridge_signal_id>`
  - `vt_orderid = main_engine.send_order(req, gateway_name)`
  - `write_timing = immediately_after_send_order_returns_before_waiting_for_events`
  - `vt_orderid_write_policy = write_actual_return_only_never_synthetic`
  - `event_sources_after_submit = EVENT_ORDER,EVENT_TRADE,EVENT_TICK`
  - `required_next_metrics = filled_volume,unfilled_volume,cancelled_volume,avg_fill_price,VWAP,implementation_shortfall,participation`
- 修改参数：无交易参数修改。
- 删除参数：无。

## 审计输入

- Stage589 mapping ledger：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage589_stage526_pre_submit_bridge_mapping_audit_pre_submit_mapping_ledger_stage589_stage526_pre_submit_bridge_mapping_audit_v1.csv`

## 运行口径

- 命令：
  - `MPLCONFIGDIR=/private/tmp/mpl-cache .py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_stage591_stage526_bridge_submit_adapter_contract.py --mode dry-run`
- 执行口径：
  - dry-run only
  - `send_order_api_called_count=0`
  - `real_submit_allowed_count=0`
  - 不注入 `MainEngine`
  - 不连接 CTP
  - 不生成 synthetic `vt_orderid`

## 结果

- 决策：`bridge_submit_adapter_contract_ready_real_submit_blocked`
- `promotion_allowed=false`
- `zero_execution_bias_claim_allowed=false`
- submit rows：`5`
- P0 submit rows：`3`
- `order_request_payload_ready=5`
- `send_order_api_called_count=0`
- real `vt_orderid` mappings：`0`
- `real_submit_allowed_count=0`
- gates：`8/10`
- hard gates：`8/10`

### Submit plan 摘要

| event_id | vt_symbol | watch_priority | order_reference | status | volume | price | vt_orderid |
| --- | --- | --- | --- | --- | ---: | ---: | --- |
| `612` | `fu2509.SHFE` | `P0_hard_daily_and_close_window_gap` | `Stage526TCA:stage526_event_612_2025-08-21_fu2509.SHFE_close_buy` | `request_ready_dry_run` | `500` | `2698` | 空 |
| `574` | `lc2505.GFEX` | `P0_roll_old_contract_close_window_gap` | `Stage526TCA:stage526_event_574_2025-04-21_lc2505.GFEX_close_buy` | `request_ready_dry_run` | `347` | `69060` | 空 |
| `590` | `AP505.CZCE` | `P0_close_window_gap` | `Stage526TCA:stage526_event_590_2025-04-18_AP505.CZCE_close_sell` | `request_ready_dry_run` | `279` | `7930` | 空 |
| `556` | `SM501.CZCE` | `P1_high_window_participation_reference` | `Stage526TCA:stage526_event_556_2024-12-05_SM501.CZCE_close_sell` | `request_ready_dry_run` | `447` | `6248` | 空 |
| `565` | `SM505.CZCE` | `P1_closed_hard_event_reference` | `Stage526TCA:stage526_event_565_2024-12-19_SM505.CZCE_open_sell` | `request_ready_dry_run` | `500` | `6226` | 空 |

### Gate 摘要

- 通过：
  - Stage589 mapping loaded：`5` rows
  - OrderRequest payload ready：`5/5`
  - Stage526 reference prefix：全部 `Stage526TCA:`
  - bridge_signal_id unique：通过
  - P0 payload slots ready：`3`
  - dry-run send_order zero：`0`
  - mapping writer contract ready：`5`
  - real submit allowed：`false for this audit`
- 失败：
  - real `vt_orderid` present：`0`
  - zero execution-bias claim allowed：`false`

## 图表视觉复盘

- 左上 submit adapter status：`5` 行全部为 `request_ready_dry_run`，说明 adapter-facing payload 已构造完成，但仍处于 dry-run 状态。
- 右上 field readiness：`bridge_id/reference/payload` 三列全绿，`vt_orderid/real_allowed` 两列全红。这个图最关键：它证明桥接字段已接上，但真实订单回报没有被伪造。
- 左下 P0 planned volume slots：`fu2509 500手`、`lc2505 347手`、`AP505 279手` 三个 P0 都进入 payload slot；不是只覆盖某一个缺口。
- 右下 contract gates：绿灯集中在 mapping/payload/reference/writer/dry-run 安全项；红灯只剩真实 `vt_orderid` 缺失和 zero-bias claim 不允许，符合 fail-closed 预期。

## 输出文件

- script：`examples/portfolio_backtesting/analyze_qmt_roll_stage591_stage526_bridge_submit_adapter_contract.py`
- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage591_stage526_bridge_submit_adapter_contract_report_stage591_stage526_bridge_submit_adapter_contract_v1.md`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage591_stage526_bridge_submit_adapter_contract_decision_stage591_stage526_bridge_submit_adapter_contract_v1.json`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage591_stage526_bridge_submit_adapter_contract_chart_stage591_stage526_bridge_submit_adapter_contract_v1.png`
- submit plan：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage591_stage526_bridge_submit_adapter_contract_submit_plan_stage591_stage526_bridge_submit_adapter_contract_v1.csv`
- mapping writer contract：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage591_stage526_bridge_submit_adapter_contract_mapping_writer_contract_stage591_stage526_bridge_submit_adapter_contract_v1.csv`
- gates：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage591_stage526_bridge_submit_adapter_contract_gates_stage591_stage526_bridge_submit_adapter_contract_v1.csv`

## 结论

- Stage591 已把 Stage589 的 mapping 合同推进到 adapter-facing payload 和 writer contract。
- 本阶段仍不能声明 Stage526 真实交易无偏差，因为真实 `vt_orderid` 仍为 `0`，真实 fills 为 `0`。
- 下一步必须不是继续 dry-run，而是在测试环境/SimNow/券商测试路径满足 SOP 后，接入真实 `main_engine` 或等价 broker adapter：
  - fresh broker snapshot
  - 合约快照校验
  - 1手/小量 smoke 或策略目标订单前置闸门
  - `send_order` 返回后立即持久化 `vt_orderid`
  - 再把 `EVENT_ORDER/EVENT_TRADE/EVENT_TICK` 回灌 Stage587 reducer
- `fu2509/lc2505/AP505` 各 `3` 个有效样本前，Stage526 仍只能称为正常成本候选，不能说“真实交易不存在偏差”。

## 过拟合反思

- 运行前判断：不是过拟合。
- 运行后判断：不是过拟合。
- 原因：
  - 本阶段只做执行工程合同，不修改策略、不调参数、不做收益回测。
  - 主动保持真实 submit blocked，并明确不伪造 `vt_orderid`。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值。
- 原因：
  - Stage589 只有字段合同，Stage591 已让合同可被 adapter 消费。
  - 但总目标还未完成；真正价值下一步在真实 mapped fills，而不是继续增加 dry-run 报告。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：是，当前线最新阶段刷新为 Stage291。
- 是否追加根目录 `back_log.md`：是，作为执行偏差闭环的重要工程前置。
- 是否追加根目录 `memory.md`：否。本阶段未产生真实成交证据或正式候选。
