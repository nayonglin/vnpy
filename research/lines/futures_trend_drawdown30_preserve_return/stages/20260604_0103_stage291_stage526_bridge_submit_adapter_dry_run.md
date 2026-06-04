# Stage291 Stage526 bridge-aware submit adapter dry-run 审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-04 01:03 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：执行证据链接线审计；不连接 CTP、不调用 `send_order`、不修改策略、不做收益回测。
- 是否重要突破：否，但属于 Stage526/079 真实执行无偏差闭环的关键工程推进。
- 是否触发 A/B：否。本阶段不形成交易策略候选，只是执行 adapter dry-run 接线。

## 外部调研与判断

- 参考资料：
  - vn.py/VeighNa `send_order(req)` 网关合同返回 `vt_orderid`。
  - vn.py/VeighNa 订单和成交生命周期通过 `EVENT_ORDER` 与 `EVENT_TRADE` 回调传播。
  - Stage589 已确认 `OrderRequest.reference` 可以携带 `Stage526TCA:<bridge_signal_id>`，但真实 join 仍必须以 `send_order` 返回的 `vt_orderid` 为准。
- 参考链接：
  - https://gitee.com/vnpy/vnpy/blob/master/vnpy/trader/gateway.py?skip_mobile=true
  - https://github.com/vnpy/vnpy
  - https://www.vnpy.com/forum/post/69782
- 我的判断：
  - 不能靠同日期/同品种日志推断 Stage526 P0 执行质量，必须由 submit adapter 写出 `bridge_signal_id -> vt_orderid`。
  - dry-run 允许构造 `OrderRequest` payload 和 live context checklist，但不能伪造 `vt_orderid`。
  - 历史 P0 合约已经过期，本阶段只能证明 adapter 合同与字段链路，不代表这些历史行可被当前真实提交。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage591_stage526_bridge_submit_adapter_dry_run.py`
- 修改脚本：无正式策略脚本修改。
- 删除脚本：无。
- 新增输出：
  - bridge submit plan
  - live context requirements
  - gates
  - decision
  - report
  - chart
- 新增字段/规则：
  - `OrderRequest.reference = Stage526TCA:<bridge_signal_id>`
  - `vt_orderid_write_policy = persist_exact_return_value_from_main_engine_send_order_only`
  - `synthetic_vt_orderid_generated = 0`
  - `send_order_api_called = 0`
  - `ctp_connection_attempted = 0`
  - live context 必需字段：`fresh_contract_snapshot/fresh_account_snapshot/fresh_position_snapshot/live_limit_price/account_equity_before/broker_margin_before/price_band_checked/margin_available_checked/operator_confirmed`
- 修改参数：无交易参数修改。
- 删除参数：无。

## 审计输入

- Stage589 mapping ledger：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage589_stage526_pre_submit_bridge_mapping_audit_pre_submit_mapping_ledger_stage589_stage526_pre_submit_bridge_mapping_audit_v1.csv`

## 结果

- 决策：`bridge_submit_adapter_dry_run_ready_live_context_missing`
- `promotion_allowed=false`
- `zero_execution_bias_claim_allowed=false`
- submit plan rows：`5`
- P0 rows：`3`
- `OrderRequest` payload rows：`5`
- real `vt_orderid` mappings：`0`
- `send_order_api_called_count=0`
- `ctp_connection_attempted=false`
- gates：`9/10`
- hard gates：`9/10`

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

### Submit plan 摘要

| event_id | vt_symbol | P0 | reference | status | vt_orderid | send_order |
| --- | --- | ---: | --- | --- | --- | ---: |
| `612` | `fu2509.SHFE` | `1` | `Stage526TCA:stage526_event_612_2025-08-21_fu2509.SHFE_close_buy` | `dry_run_order_request_payload_ready` | 空 | `0` |
| `574` | `lc2505.GFEX` | `1` | `Stage526TCA:stage526_event_574_2025-04-21_lc2505.GFEX_close_buy` | `dry_run_order_request_payload_ready` | 空 | `0` |
| `590` | `AP505.CZCE` | `1` | `Stage526TCA:stage526_event_590_2025-04-18_AP505.CZCE_close_sell` | `dry_run_order_request_payload_ready` | 空 | `0` |
| `556` | `SM501.CZCE` | `0` | `Stage526TCA:stage526_event_556_2024-12-05_SM501.CZCE_close_sell` | `dry_run_order_request_payload_ready` | 空 | `0` |
| `565` | `SM505.CZCE` | `0` | `Stage526TCA:stage526_event_565_2024-12-19_SM505.CZCE_open_sell` | `dry_run_order_request_payload_ready` | 空 | `0` |

### Gate 结果

- 通过：
  - Stage589 mapping loaded：`5`
  - P0 rows present：`3`
  - `order_reference_carries_bridge_id`：`5/5`
  - `order_request_payload_built`：`5/5`
  - `no_send_order_called`：`0`
  - `no_ctp_connection_attempted`：`0`
  - `no_synthetic_vt_orderid`：`0`
  - `real_vt_orderid_absent`：`0 in dry-run`
  - `live_context_missing_blocks_real_submit`：`45` 个 live context 缺口仍在
- 失败：
  - `zero_bias_claim_allowed=false`，因为没有 mapped `EVENT_ORDER/EVENT_TRADE` fills。

## 图表视觉复盘

- 左上图：`dry_run_order_request_payload_ready` 为 `5`，说明所有 mapping row 都能构造成带 Stage526TCA reference 的 vn.py `OrderRequest` payload。
- 右上图：三个红色 P0 bucket 与两个灰色 P1 bucket 都保留，没有只做单一 P0。
- 左下图：所有 live context 字段 present rows 都为 `0`，说明本阶段绝不允许真实提交；后续必须补新鲜合约、账户、持仓、限价、保证金与人工确认。
- 右下图：只有 `zero_bias_claim_allowed` 红灯，其余 dry-run 接线和安全项全绿。这个视觉状态是正确的：adapter 接线已推进，但真实无偏差不能关账。

## 输出文件

- script：`examples/portfolio_backtesting/analyze_qmt_roll_stage591_stage526_bridge_submit_adapter_dry_run.py`
- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage591_stage526_bridge_submit_adapter_dry_run_report_stage591_stage526_bridge_submit_adapter_dry_run_v1.md`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage591_stage526_bridge_submit_adapter_dry_run_decision_stage591_stage526_bridge_submit_adapter_dry_run_v1.json`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage591_stage526_bridge_submit_adapter_dry_run_chart_stage591_stage526_bridge_submit_adapter_dry_run_v1.png`
- submit plan：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage591_stage526_bridge_submit_adapter_dry_run_submit_plan_stage591_stage526_bridge_submit_adapter_dry_run_v1.csv`
- live context requirements：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage591_stage526_bridge_submit_adapter_dry_run_live_context_requirements_stage591_stage526_bridge_submit_adapter_dry_run_v1.csv`
- gates：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage591_stage526_bridge_submit_adapter_dry_run_gates_stage591_stage526_bridge_submit_adapter_dry_run_v1.csv`

## 结论

- Stage591 已把 Stage589 mapping contract 落成 bridge-aware submit adapter dry-run：`OrderRequest.reference` 已全量携带 `Stage526TCA:<bridge_signal_id>`。
- 这不是实盘证据，也不是 zero-bias close：真实 `vt_orderid` 仍为 `0`，live context 全缺，`EVENT_ORDER/EVENT_TRADE` mapped fills 仍为 `0`。
- 后续真实/虚拟 submit-capable 路径必须在 `main_engine.send_order(req, gateway_name)` 返回后立即持久化返回的 `vt_orderid`，再交给 Stage587 reducer 归并 order/trade/tick。
- `fu2509/lc2505/AP505` 各 `3` 个有效 mapped fills 或独立全日分钟证据前，Stage526 仍只能是正常成本主候选，不能声明真实交易不存在偏差。

## 过拟合反思

- 运行前判断：不是过拟合。
- 运行后判断：不是过拟合。
- 原因：
  - 本阶段只接执行证据链，不修改策略信号、参数、品种、资金口径或收益回测。
  - 明确不生成 synthetic `vt_orderid`，避免把 dry-run payload 误当真实执行证据。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值。
- 原因：
  - Stage526 真实偏差闭环的核心缺口是 `bridge_signal_id -> vt_orderid -> trade`，Stage591 已完成 reference 接线和 dry-run payload。
  - 下一步价值非常明确：在 fresh pre-submit/live context 下拿到真实或测试环境 `send_order` 返回值，并写入 mapping ledger。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：是，当前线最新阶段刷新为 Stage291。
- 是否追加根目录 `back_log.md`：是，作为真实执行偏差闭环的重要工程进展。
- 是否追加根目录 `memory.md`：否。真实无偏差尚未关账，不是正式突破。
