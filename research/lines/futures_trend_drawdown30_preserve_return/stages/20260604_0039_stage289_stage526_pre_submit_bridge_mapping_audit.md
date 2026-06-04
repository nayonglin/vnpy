# Stage289 Stage526 pre-submit bridge mapping 审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-04 00:39 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：执行证据链合同审计；不连接 CTP、不调用 `send_order`、不修改策略、不做收益回测。
- 是否重要突破：否，但属于 Stage526 执行偏差闭环的重要工程前置。
- 是否触发 A/B：否。本阶段没有形成新策略候选，只是 submit/TCA mapping 合同。

## 外部调研与判断

- 参考资料：
  - vn.py 官方 Gitee 源码 `vnpy/trader/gateway.py`：网关 `send_order(req)` 应返回 `vt_orderid`，`on_order/on_trade` 推送 `EVENT_ORDER/EVENT_TRADE`。
  - VeighNa 社区与 DeepWiki 源码索引：`OrderData/TradeData` 通过 `vt_orderid` 串起委托状态与成交回报。
- 我的判断：
  - Stage526 的执行偏差不能靠同品种/同日期日志推断；必须由 submit adapter 写出 `bridge_signal_id -> vt_orderid`。
  - `OrderRequest.reference` 应携带 `Stage526TCA:<bridge_signal_id>`，但真正 join 仍以 `send_order` 返回的 `vt_orderid` 为准。
  - dry-run 阶段不能伪造 `vt_orderid`，否则会污染后续 TCA 证据。

参考链接：

- https://gitee.com/vnpy/vnpy/blob/master/vnpy/trader/gateway.py?skip_mobile=true
- https://deepwiki.com/vnpy/vnpy/7.2-creating-custom-gateways
- https://www.vnpy.com/forum/post/69782

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage589_stage526_pre_submit_bridge_mapping_audit.py`
- 修改脚本：无正式策略脚本修改；无真实 submit adapter 修改。
- 删除脚本：无。
- 新增输出：
  - pre-submit mapping ledger
  - adapter capability matrix
  - field contract
  - gates
  - decision
  - report
  - chart
- 新增字段合同：
  - `bridge_signal_id`
  - `adapter_intent_id`
  - `order_reference`
  - `vt_orderid`
  - `vt_orderid_source`
  - `order_submit_at`
  - `order_submit_price`
  - `order_type`
  - `limit_price`
  - `account_equity_before`
  - `broker_margin_before`
  - `send_order_api_called`
  - `ctp_connection_attempted`
  - `real_submit_allowed`
- 修改参数：无交易参数修改。
- 删除参数：无。

## 回测/归因参数

- 数据区间：不适用；本阶段不做收益回测。
- 账户规模：不适用；Stage526 参考口径仍为 `50万` 约束下的正常成本候选。
- 成本口径：不适用。
- 样本过滤：读取 Stage587 intent ledger 的 `5` 行，其中 P0 为 `fu2509.SHFE/lc2505.GFEX/AP505.CZCE`。
- 执行口径：dry-run only；`send_order_api_called_count=0`，`ctp_connection_attempted=false`。

## 结果

- 决策：`pre_submit_bridge_mapping_contract_ready_real_vt_orderid_absent`
- `promotion_allowed=false`
- `zero_execution_bias_claim_allowed=false`
- mapping rows：`5`
- P0 mapping slots：`3`
- real `vt_orderid` mappings：`0`
- gates：`7/11`
- hard gates：`7/9`
- `send_order_api_called_count=0`
- `ctp_connection_attempted=false`

### Stage526 参考口径

| 指标 | 数值 |
| --- | ---: |
| 期末权益 | `23,369,505` |
| 总收益 | `3699.9195%` |
| 最大回撤 | `-36.2670%` |
| Sharpe | `1.6385` |
| Ulcer | `14.4691` |
| 总滑点 | `1,342,190` |
| 总交易次数 | `905` |
| 胜率 | `53.6330%` |

### Mapping ledger 摘要

| event_id | vt_symbol | watch_priority | order_reference | mapping_status | vt_orderid |
| --- | --- | --- | --- | --- | --- |
| `612` | `fu2509.SHFE` | `P0_hard_daily_and_close_window_gap` | `Stage526TCA:stage526_event_612_2025-08-21_fu2509.SHFE_close_buy` | `awaiting_live_send_order_return` | 空 |
| `574` | `lc2505.GFEX` | `P0_roll_old_contract_close_window_gap` | `Stage526TCA:stage526_event_574_2025-04-21_lc2505.GFEX_close_buy` | `awaiting_live_send_order_return` | 空 |
| `590` | `AP505.CZCE` | `P0_close_window_gap` | `Stage526TCA:stage526_event_590_2025-04-18_AP505.CZCE_close_sell` | `awaiting_live_send_order_return` | 空 |
| `556` | `SM501.CZCE` | `P1_high_window_participation_reference` | `Stage526TCA:stage526_event_556_2024-12-05_SM501.CZCE_close_sell` | `awaiting_live_send_order_return` | 空 |
| `565` | `SM505.CZCE` | `P1_closed_hard_event_reference` | `Stage526TCA:stage526_event_565_2024-12-19_SM505.CZCE_open_sell` | `awaiting_live_send_order_return` | 空 |

### Adapter capability

- Stage249 legacy submit adapter：
  - dry-run 安全层存在。
  - 但没有 `bridge_signal_id`、没有 `vt_orderid` slot、`reference` 不携带 `Stage526TCA`。
- Stage250 legacy OrderRequest builder：
  - 能构造 vn.py `OrderRequest`，且 `order_api_called=0`。
  - 但 `reference` 仍为 `Stage250PhaseB:{intent_id}`，不是 Stage526 TCA join id。
- Stage587 reducer：
  - 已要求 `bridge_signal_id + vt_orderid`。
  - 但没有 submit mapping writer。
- Stage589 新合同：
  - 已有 `bridge_signal_id`、`vt_orderid` slot、`Stage526TCA:<bridge_signal_id>` reference 合同，且真实 submit blocked。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage589_stage526_pre_submit_bridge_mapping_audit_report_stage589_stage526_pre_submit_bridge_mapping_audit_v1.md`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage589_stage526_pre_submit_bridge_mapping_audit_decision_stage589_stage526_pre_submit_bridge_mapping_audit_v1.json`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage589_stage526_pre_submit_bridge_mapping_audit_chart_stage589_stage526_pre_submit_bridge_mapping_audit_v1.png`
- mapping ledger：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage589_stage526_pre_submit_bridge_mapping_audit_pre_submit_mapping_ledger_stage589_stage526_pre_submit_bridge_mapping_audit_v1.csv`
- adapter capability：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage589_stage526_pre_submit_bridge_mapping_audit_adapter_capability_matrix_stage589_stage526_pre_submit_bridge_mapping_audit_v1.csv`
- field contract：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage589_stage526_pre_submit_bridge_mapping_audit_field_contract_stage589_stage526_pre_submit_bridge_mapping_audit_v1.csv`
- gates：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage589_stage526_pre_submit_bridge_mapping_audit_gates_stage589_stage526_pre_submit_bridge_mapping_audit_v1.csv`

## 图表视觉复盘

- 左上图：所有 mapping row 都停在 `awaiting_live_send_order_return`，说明合同已生成，但没有伪造 `vt_orderid`。
- 右上图：新 Stage589 合同具备 `bridge_signal_id`、`vt_orderid_slot`、`reference_carries_bridge_id` 和 submit block；旧 Stage249/250 在前三项为红，说明老 adapter 不能直接支撑 Stage526 TCA。
- 左下图：P0/P1 五个 intent 都有 mapping slot，不是只覆盖某一个 P0。
- 右下图：绿灯集中在 dry-run、intent loaded、bridge id unique、P0 slot created 和新合同 ready；红灯仍是旧 adapter 未接、真实 `vt_orderid=0`、zero-bias claim 不允许。

## 结论

- 本阶段结论：Stage526 pre-submit mapping 合同 ready，但真实 `vt_orderid` absent。
- 是否进入下一步：进入执行 adapter 接线或真实 mapped fill 采集；不进入收益回测，也不允许声明真实交易无偏差。
- 下一步：
  - 未来 submit-capable adapter 必须构造 `OrderRequest.reference = Stage526TCA:<bridge_signal_id>`。
  - `main_engine.send_order(req, gateway_name)` 返回后，必须立即把 `vt_orderid` 写入 mapping ledger。
  - 之后再把 `EVENT_ORDER/EVENT_TRADE/EVENT_TICK` 归并回 Stage587 reducer，计算 avg fill、unfilled/cancelled、VWAP、shortfall、participation。
  - `fu2509/lc2505/AP505` 各 `3` 个有效样本前，Stage526 仍只能称为正常成本候选。

## 过拟合反思

- 运行前判断：不是过拟合。
- 运行后判断：不是过拟合。
- 原因：
  - 本阶段只做执行证据链字段合同，不修改交易规则、不调收益参数、不做样本选择。
  - 明确拒绝 synthetic `vt_orderid`，避免把 dry-run 合同误当实盘证据。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值。
- 原因：
  - Stage526 的目标是“真实交易不存在偏差”，没有 `bridge_signal_id -> vt_orderid` 就无法证明。
  - 现在 mapping slot 已落地，下一步可以把未来真实 submit adapter 的返回值直接接到 Stage587 reducer。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：是，当前线最新阶段需要刷新。
- 是否追加根目录 `memory.md/back_log.md`：追加 `back_log.md` 简短边界；不追加 `memory.md`，因为仍未关账真实执行偏差。
