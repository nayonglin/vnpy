# Stage315 event TCA reducer 合同审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-04 05:24 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：执行无偏差证据链的 TCA reducer 合同审计；用合成 order/trade/tick 事件验证 reducer 数学与字段闭合。
- 对应脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage615_event_tca_reducer_contract_audit.py`
- 输出报告：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage615_event_tca_reducer_contract_audit_report_stage615_event_tca_reducer_contract_audit_v1.md`
- 输出图表：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage615_event_tca_reducer_contract_audit_chart_stage615_event_tca_reducer_contract_audit_v1.png`
- 决策：`event_tca_reducer_contract_ready_synthetic_only_live_evidence_absent`
- 是否重要突破：否。它证明 reducer 合同和数学路径可工作，但合成样本不能替代真实成交证据。
- 是否触发 A/B：否。没有策略候选、没有收益回放、没有交易白名单。
- 是否新增回测：否。
- 是否修改策略：否。
- 是否连接 CTP/SimNow：否，`ctp_connection_attempted=false`。
- 是否调用 `send_order`：否，`send_order_api_called_count=0`。

## 开始前反思

- 是否过拟合：否。本阶段不调整收益、品种、参数或窗口，只验证 `vt_orderid + order/trade/tick` 事件归并合同。
- 是否有价值继续：有。Stage314 已经把 live evidence 画红，本阶段把下一步真实 TCA reducer 的接口、字段和计算边界先压实，避免后续 submit 测试时临时补字段。

## 外部调研与判断

- vn.py/VeighNa 网关合同显示 `send_order(req)` 应返回 `vt_orderid`，这是订单、成交和后续 TCA 归并的关键主键。
- vn.py/EventEngine 路径提供 `EVENT_ORDER`、`EVENT_TRADE`、`EVENT_TICK`，本线后续应只接受这些事件进入真实 TCA reducer。
- `tcapy` 一类 TCA 工程实践强调，真实执行评估必须把订单/成交与市场 tick 或窗口 VWAP 合并，而不是只看回测信号价。
- implementation shortfall 资料说明，真实执行偏差至少要拆成信号价到成交价、窗口 VWAP 偏差、显性成本、参与率和未成交量。
- 本阶段判断：正确边界是 exact `vt_orderid` 持久化 + 事件驱动 reducer。合成样本可以验证 reducer 代码和字段闭合，但不能计入 live TCA 样本，不能用于声明真实交易无偏差。

参考：

- vn.py gateway/send_order：`https://deepwiki.com/vnpy/vnpy/7.2-creating-custom-gateways`
- vn.py MainEngine/EventEngine：`https://deepwiki.com/vnpy/vnpy/2.1-main-engine-and-event-system`
- tcapy：`https://github.com/cuemacro/tcapy`
- QuestDB implementation shortfall cookbook：`https://questdb.com/docs/cookbook/sql/finance/implementation-shortfall/`

## 本阶段做了什么

- 读取 Stage589 pre-submit mapping ledger，确认 `bridge_signal_id`、`order_reference`、`vt_orderid` 等 writer 合同字段。
- 用 Stage589 第一个 P0 信号构造一个合成 `vt_orderid=SIMTCA.000001` 样本。
- 构造合成 order/trade/tick 事件，验证 reducer 能计算：
  - `avg_fill_price`
  - `filled_volume`
  - `unfilled_volume`
  - `commission_cash`
  - `actual_implementation_shortfall_bps`
  - `actual_vs_window_vwap_bps`
  - `actual_participation_pct`
- 同时保留真实 live evidence gap，使真实 live context、真实 `vt_orderid`、P0 live TCA 样本继续为红。
- 不连接 CTP，不订阅行情，不提交订单，不重放策略收益。

## 新增/修改/删除

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage615_event_tca_reducer_contract_audit.py`
- 修改脚本：无既有策略脚本修改。
- 删除脚本：无。
- 新增参数：
  - `MAX_VWAP_COST_BPS = 50.0`
  - `MAX_IMPLEMENTATION_SHORTFALL_BPS = 75.0`
  - `MAX_PARTICIPATION_PCT = 25.0`
  - `P0_REQUIRED_LIVE_TCA_SAMPLES = 9`
- 修改参数：无策略参数修改。
- 删除参数：无。

## 回测结果

本阶段没有新增交易回测，因此以下字段不适用：

- 期末权益：不适用。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：不适用。
- 胜率：不适用。

## 核心结果

- synthetic samples：`1`
- synthetic valid TCA samples：`1`
- live context present：`0/45`
- real `vt_orderid` mappings：`0/5`
- P0 valid live TCA samples：`0/9`
- hard gates：`5/9`
- failed hard gates：`4`
- zero execution bias claim allowed：`false`
- `ctp_connection_attempted`：`false`
- `send_order_api_called_count`：`0`

合成 TCA 样本：

| 字段 | 结果 |
| --- | --- |
| `bridge_signal_id` | `stage526_event_612_2025-08-21_fu2509.SHFE_close_buy` |
| `vt_orderid` | `SIMTCA.000001` |
| `vt_symbol` | `fu2509.SHFE` |
| `signal_price` | `2698.0` |
| `avg_fill_price` | `2698.16` |
| `filled_volume` | `500` |
| `unfilled_volume` | `0` |
| `commission_cash` | `13.4908` |
| `actual_implementation_shortfall_bps` | `0.5930` |
| `actual_vs_window_vwap_bps` | `0.5374` |
| `actual_participation_pct` | `2.5%` |
| `valid_tca_sample` | `1` |
| `sample_source` | `synthetic_contract_fixture_not_live` |

## 关账闸门

| 闸门 | 状态 | 结果 |
| --- | --- | --- |
| no_strategy_or_return_change | 通过 | 不重放收益、不改策略。 |
| order_api_not_called | 通过 | `send_order_api_called_count=0`。 |
| writer_contract_fields_present | 通过 | Stage589 mapping 合同字段大部分已在账本中存在。 |
| synthetic_order_trade_tick_join_ready | 通过 | 合成样本 `1/1` 能 join。 |
| synthetic_tca_math_ready | 通过 | VWAP、IS、参与率、成交量字段可计算。 |
| live_context_ready | 失败 | `0/45`，没有 fresh contract/tick/account/position。 |
| live_vt_orderid_ready | 失败 | `0/5`，没有真实 submit 返回值。 |
| live_tca_samples_ready | 失败 | `0/9`，合成样本不得计入 live TCA。 |
| zero_bias_claim_allowed | 失败 | 当前仍不能声明真实交易无偏差。 |

## 图表视觉复盘

- 左上图显示 writer contract 大多数槽位为绿，但 `signal_price` 与 `operator_confirm_text` 仍是 live-only 待补字段。
- 右上图显示合成 reducer 的 implementation shortfall、VWAP 偏差和 participation 都低于灰色阈值，数学路径可工作。
- 左下图显示真实 live evidence 仍全部为红：live context、真实 `vt_orderid`、P0 order/trade/tick join、P0 valid live TCA 都为 `0`。
- 右下图显示 synthetic gates 为绿，live gates 为红；图表没有把合成样本误画成真实执行证据。
- 视觉结论：Stage315 可以证明 reducer 合同可运行，但真实证据断点仍清楚停在 live context 与真实 `vt_orderid` 之前。

## 结论

- TCA reducer 合同已具备进入真实 submit 测试后的承接能力。
- 合成样本证明 `bridge_signal_id -> vt_orderid -> order/trade/tick -> avg_fill/VWAP/IS/participation` 的数学和字段路径可以闭合。
- 但这不是 live evidence。当前仍不能说 Stage079/Stage526 真实交易不存在偏差，也不能把合成 `SIMTCA.000001` 计入 P0 live TCA 样本。
- 下一步不应继续收益回测或扩池白名单，而应先刷新 read-only live snapshot；之后只有在用户明确确认测试环境和 submit 动作后，才做 exact `vt_orderid` writer 与真实 `EVENT_ORDER/EVENT_TRADE/EVENT_TICK` reducer。

## 结束后反思

- 是否过拟合：否。脚本只验证事件归并合同和 TCA 计算，没有根据收益、回撤、品种强弱或历史窗口做选择。
- 是否有价值继续：有。它把“后续真实成交 TCA 要怎么验”从口头标准变成了可运行 reducer 合同；但价值边界也明确，下一步必须拿真实 live context 和真实事件样本，不应继续在合成数据上美化结论。

## 验证

- `.py311/bin/python -m py_compile examples/portfolio_backtesting/analyze_qmt_roll_stage615_event_tca_reducer_contract_audit.py`：通过。
- `.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_stage615_event_tca_reducer_contract_audit.py`：通过。
- `rg -n "send_order\\(" examples/portfolio_backtesting/analyze_qmt_roll_stage615_event_tca_reducer_contract_audit.py`：无命中。
- 图表视觉检查：通过。
- 输出文件存在：通过。

## 输出文件

- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage615_event_tca_reducer_contract_audit_decision_stage615_event_tca_reducer_contract_audit_v1.json`
- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage615_event_tca_reducer_contract_audit_report_stage615_event_tca_reducer_contract_audit_v1.md`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage615_event_tca_reducer_contract_audit_chart_stage615_event_tca_reducer_contract_audit_v1.png`
- gates：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage615_event_tca_reducer_contract_audit_gates_stage615_event_tca_reducer_contract_audit_v1.csv`
- live gap：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage615_event_tca_reducer_contract_audit_live_gap_stage615_event_tca_reducer_contract_audit_v1.csv`
- synthetic TCA samples：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage615_event_tca_reducer_contract_audit_synthetic_tca_samples_stage615_event_tca_reducer_contract_audit_v1.csv`

## TODO

- read-only live snapshot：用户确认测试环境和 read-only 动作后，运行 Stage608 wrapper 显式 `--connect --wait-seconds 90`，刷新 target symbols 的 tick/account/position/contract 快照。
- live validator：把 fresh snapshot 输入 Stage612/606/607，使 live context 从 `0/45` 推进到可审计状态。
- exact `vt_orderid` writer：仅在用户明确确认测试环境和 submit 动作后，持久化 `main_engine.send_order` 返回的真实 `vt_orderid`。
- live TCA reducer：消费真实 `EVENT_ORDER/EVENT_TRADE/EVENT_TICK` CSV，P0 三类样本各累计 `3` 个有效样本，总计 `9/9`。
- 纪律：合成样本永远不能计入 live TCA；未达闸门前禁止 zero-bias claim、P0/P1 白名单、A/B 和实盘晋级。

## 合入建议

- 是否更新本线 `LINE.md`：是，更新当前状态和下一步。
- 是否更新 `research/registry.md`：是，更新最新阶段到 Stage315。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段不是正式候选、重要突破或跨线合入，只写本研究线。
