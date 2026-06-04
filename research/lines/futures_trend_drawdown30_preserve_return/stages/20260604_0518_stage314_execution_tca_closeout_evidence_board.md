# Stage314 执行TCA关账证据板

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-04 05:18 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：执行无偏差证据闭环审计；只读合成 Stage587/589/591/612 输出。
- 对应脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage613_execution_tca_closeout_evidence_board.py`
- 输出报告：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage613_execution_tca_closeout_evidence_board_report_stage613_execution_tca_closeout_evidence_board_v1.md`
- 输出图表：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage613_execution_tca_closeout_evidence_board_chart_stage613_execution_tca_closeout_evidence_board_v1.png`
- 决策：`execution_tca_closeout_board_ready_contracts_green_live_evidence_red`
- 是否重要突破：否。它把执行证据缺口压成一张关账板，但没有形成可实盘结论。
- 是否触发 A/B：否。没有策略候选、没有收益回放、没有交易白名单。
- 是否新增回测：否。
- 是否修改策略：否。
- 是否连接 CTP/SimNow：否。
- 是否调用 `send_order`：否，`send_order_api_called_count=0`。

## 开始前反思

- 是否过拟合：否。本阶段只合成执行证据链，不改变策略、参数、收益曲线或选品。
- 是否有价值继续：有。当前目标要求“真实交易不存在偏差”，但现有证据只证明 dry-run 合同，不证明真实成交质量。

## 外部调研与判断

- `tcapy` 等 TCA 工程资料强调，TCA 不是只看回测成交价，而是要把订单/成交数据与市场 tick 数据合并，计算 arrival/mid/VWAP、slippage、impact 等指标。
- vn.py/VeighNa 的 MainEngine/EventEngine 合同提供 `EVENT_TICK`、`EVENT_ORDER`、`EVENT_TRADE` 与 `vt_orderid` 这条事件链，适合承接本线的 `bridge_signal_id -> vt_orderid -> order/trade/tick -> TCA`。
- Implementation shortfall 资料说明，真实执行成本要包含决策价到实际成交价、显性成本、市场冲击、时间风险和未成交机会成本。
- 本阶段判断：Stage587/589/591/612 已经证明“字段和 payload 合同存在”，但没有证明真实成交无偏差；不能把历史 reference price 或 dry-run payload 当作 live TCA。

参考：

- tcapy: https://github.com/cuemacro/tcapy
- vn.py MainEngine/EventEngine: https://deepwiki.com/vnpy/vnpy/2.2-main-engine
- vn.py event types: https://deepwiki.com/vnpy/vnpy
- Implementation Shortfall: https://trading.glass/en/academy/execution-precision/execution-metrics/implementation-shortfall

## 本阶段做了什么

- 读取 Stage587 live TCA bridge dry-run 结果。
- 读取 Stage589 pre-submit mapping ledger。
- 读取 Stage591 bridge submit adapter dry-run 结果。
- 读取 Stage612 post-connect live context validator 结果。
- 新增 Stage613 脚本，输出：
  - execution evidence chain；
  - TCA actual field matrix；
  - blockers；
  - hard gates；
  - decision JSON；
  - markdown report；
  - 可视化图表。
- 不连接 CTP，不订阅行情，不提交订单，不重放策略收益。

## 新增/修改/删除

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage613_execution_tca_closeout_evidence_board.py`
- 修改脚本：无既有策略脚本修改。
- 删除脚本：无。
- 新增参数：
  - `P0_REQUIRED_SAMPLES = 9`
  - `MAX_VWAP_COST_BPS = 50.0`
  - `MAX_IMPLEMENTATION_SHORTFALL_BPS = 75.0`
  - `MAX_PARTICIPATION_PCT = 25.0`
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

- intent rows：`5`
- mapping rows：`5`
- OrderRequest payload rows：`5`
- live context present：`0/45`
- real `vt_orderid` mappings：`0/5`
- P0 order/trade/tick joined rows：`0/3`
- P0 valid live TCA samples：`0/9`
- P0 TCA actual fields ready：`0/18`
- hard gates：`3/9`
- failed hard gates：`6`
- zero execution bias claim allowed：`false`
- `send_order_api_called_count`：`0`

## 关账闸门

| 闸门 | 状态 | 结果 |
| --- | --- | --- |
| no_strategy_or_return_change | 通过 | 不重放收益、不改策略。 |
| order_api_not_called | 通过 | Stage587/589/591/612 均为 `0`。 |
| reference_and_payload_ready | 通过 | `OrderRequest.reference` 和 dry-run payload 已就绪。 |
| live_context_ready | 失败 | `0/45`，没有 fresh contract/tick/account/position。 |
| real_vt_orderid_mapping_ready | 失败 | `0/5`，没有真实 `main_engine.send_order` 返回值。 |
| p0_order_trade_tick_join_ready | 失败 | `0/3`，没有 P0 order/trade/tick join。 |
| p0_tca_field_completeness_ready | 失败 | `0/18`。 |
| p0_valid_tca_samples_ready | 失败 | `0/9`。 |
| zero_bias_claim_allowed | 失败 | 当前不能声明真实交易无偏差。 |

## 图表视觉复盘

- 左上图显示执行证据链在前三步为绿：intent、mapping contract、payload dry-run 均存在；从 live context 开始全部为红。
- 右上图显示 hard gates 中只有“不改收益/未调用订单API/合同就绪”通过，其余真实证据闸门全部阻塞。
- 左下图显示 P0 TCA 实际字段全部 `0/3`，包括 submit/fill 时间、成交价、filled/unfilled、手续费、真实滑点、implementation shortfall、VWAP 偏差、账户权益和保证金。
- 右下图显示 blocker 集中在 fresh account/contract/position/tick、live limit price、margin available、actual VWAP/IS/fill 等字段缺失。
- 视觉结论：图表没有把 dry-run 合同误画成真实成交证据；红色断点清楚集中在 live evidence。

## 结论

- Stage587/589/591/612 合起来已经形成一条可执行合同链，但还不是执行无偏差证明。
- 当前可以说：信号意图、`OrderRequest.reference`、dry-run payload 都已就绪，且没有误调用订单 API。
- 当前不能说：真实交易不存在偏差。原因是缺 fresh live context、真实 `vt_orderid`、`EVENT_ORDER/EVENT_TRADE/EVENT_TICK` join 和 P0 `9/9` live TCA 样本。
- 下一步不应继续收益回测或选品白名单，而应先做 read-only live snapshot，再在用户确认测试环境和 submit 动作后做 exact `vt_orderid` writer 与事件归并 TCA。

## 结束后反思

- 是否过拟合：否。脚本没有根据收益、品种或窗口做任何选择，只把执行证据不足明确画红。
- 是否有价值继续：有。它把“真实交易无偏差”从泛泛说法变成 `45/45 live context + 5/5 vt_orderid + 3/3 joins + 9/9 valid TCA` 的可验证目标。

## 验证

- `.py311/bin/python -m py_compile examples/portfolio_backtesting/analyze_qmt_roll_stage613_execution_tca_closeout_evidence_board.py`：通过。
- `.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_stage613_execution_tca_closeout_evidence_board.py`：通过。
- 图表视觉检查：通过。
- 输出文件存在：通过。

## TODO

- read-only 阶段：用户确认测试环境和 read-only 动作后，运行 Stage608 wrapper 显式 `--connect --wait-seconds 90`，刷新 target symbols 的 tick/account/position/contract 快照。
- validator 阶段：把 fresh snapshot 输入 Stage612/606/607，使 live context 从 `0/45` 推进到可审计状态。
- submit 测试阶段：仅在用户明确确认测试环境和提交动作后，持久化 `main_engine.send_order` 返回的真实 `vt_orderid`，并归并 `EVENT_ORDER/EVENT_TRADE/EVENT_TICK`。
- TCA 阶段：P0 三类样本各累计 `3` 个有效样本，总计 `9/9`，字段包括 avg_fill、filled/unfilled、VWAP、implementation shortfall、participation、commission、account equity、broker margin。
