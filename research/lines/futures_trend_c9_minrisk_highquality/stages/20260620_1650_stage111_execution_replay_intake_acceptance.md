# Stage111 执行回放接入验收器

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-20 16:50 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读数据接入验收 / fail-closed gate；不写真引擎，不新增交易规则，不触发 A/B
- 是否重要突破：否，属于 Stage110 后的数据合同细化
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - HftBacktest 官方文档：高频/微观结构回放要基于 full order book 与 trade tick feed，并考虑 feed/order latency 和 queue position。
  - FIX 4.4 `ExecutionReport <8>` 官方字典：执行报告用于确认订单接收、订单状态、成交、拒单等生命周期信息，说明执行回放必须保存状态与成交事件，而不是只保存一个最终成交价。
  - vn.py `TickData/OrderData/TradeData` schema：Tick 包含 last trade、orderbook snapshot、日内统计；Order/Trade 包含 `vt_orderid`、状态、成交明细，适合作为本地接入字段合同的下限。
- 我的判断：
  - Stage110 证明本地没有 rule-ready 数据后，Stage111 不应再造规则，而应把“什么数据可以进入下一步规则研究”变成自动验收器。
  - Stage932 既有 smoke 输出里有少量订单/成交/行情格式行，但只有被同一策略信号、真实 submit 返回的 `vt_orderid`、EVENT_ORDER/EVENT_TRADE/EVENT_TICK 串起来，才可能算执行回放证据。dry-run、read-only、symbol/reference 不匹配的行只能作为 schema 样本。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage111_execution_replay_intake_acceptance.py`
- 修改脚本：无其他策略脚本；Stage111 自身图表从 pass=0 空图修正为 blocked=1 阻断视图
- 删除脚本：无
- 新增参数：无交易参数；固定审计 Stage110、Stage932、Stage591、Stage587、Stage605、Stage615 与官方资金路径
- 修改参数：无
- 删除参数：无
- 正式配置变更：无
- CTP 连接：无
- 订单 API 调用：无

## 审计参数

- 数据区间：沿用 Stage045 官方资金曲线、Stage108 风险地图、Stage110 数据合同结果。
- 本地执行/接入资产审计范围：
  - Stage932 official live CTP smoke order 既有输出
  - Stage591 bridge submit adapter dry-run submit plan
  - Stage587 live TCA bridge dry-run ledger
  - Stage605 live context contract adapter audit gates
  - Stage615 event TCA reducer writer contract
  - official Phase D execution ledger path
- 验收原则：
  - 不接受 synthetic `vt_orderid`
  - 不接受 dry-run 当作实盘回放
  - 不接受只读账户历史/快照行当作策略信号回放
  - 必须具备 `bridge_signal_id/order_reference/exact vt_orderid/EVENT_ORDER/EVENT_TRADE/EVENT_TICK` join
  - 必须有 raw provenance、right-tail/bottom-loss 视觉覆盖后才能进入规则研究

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：`36.0902%`
- 其他关键指标：
  - `evidence_source_count=8`
  - `rule_allowed_source_count=0`
  - `stage932_session_count=8`
  - `stage932_total_snapshot_rows=102`
  - `stage932_format_sample_only_count=5`
  - `stage932_valid_research_sample_count=0`
  - `intake_gate_count=5`
  - `intake_gate_pass_count=0`
  - `field_contract_count=8`
  - `field_contract_pass_count=0`
  - `true_engine_allowed=0`
  - `strategy_feature_usable=0`

## Stage932 关键发现

- `20260616_140951` 虽然 `smoke_passed=1`、有 `order_api_called_count=2`，但请求标的是 `rb2610.SHFE`，成交行仍是 `MA609.CZCE`，`trade_requested_symbol_count=0`，所以 `valid_research_sample=0`。
- `20260616_140920` 的请求标的是 `rb2610.SHFE`，但 order/trade 行是 `MA609.CZCE`，属于 symbol mismatch，只能算格式样本。
- 多数 session 为 `dry-run` 或 blocked，`summary_vt_orderid` 为空、`order_reference` 未联通，不能用于策略研究。

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage111_execution_replay_intake_acceptance/qmt_roll_stage111_c9_minrisk_execution_replay_intake_acceptance_report_stage111_execution_replay_intake_acceptance_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage111_execution_replay_intake_acceptance/qmt_roll_stage111_c9_minrisk_execution_replay_intake_acceptance_summary_stage111_execution_replay_intake_acceptance_v1.csv`
- evidence sources：`qmt_roll_stage111_c9_minrisk_execution_replay_intake_acceptance_evidence_sources_stage111_execution_replay_intake_acceptance_v1.csv`
- Stage932 audit：`qmt_roll_stage111_c9_minrisk_execution_replay_intake_acceptance_stage932_smoke_audit_stage111_execution_replay_intake_acceptance_v1.csv`
- intake gate matrix：`qmt_roll_stage111_c9_minrisk_execution_replay_intake_acceptance_intake_gate_matrix_stage111_execution_replay_intake_acceptance_v1.csv`
- field contract：`qmt_roll_stage111_c9_minrisk_execution_replay_intake_acceptance_field_contract_stage111_execution_replay_intake_acceptance_v1.csv`
- next action manifest：`qmt_roll_stage111_c9_minrisk_execution_replay_intake_acceptance_next_action_manifest_stage111_execution_replay_intake_acceptance_v1.csv`
- 视觉图：
  - `qmt_roll_stage111_c9_minrisk_execution_replay_intake_acceptance_official_path_intake_blockers_stage111_execution_replay_intake_acceptance_v1.png`
  - `qmt_roll_stage111_c9_minrisk_execution_replay_intake_acceptance_intake_gate_chart_stage111_execution_replay_intake_acceptance_v1.png`
  - `qmt_roll_stage111_c9_minrisk_execution_replay_intake_acceptance_stage932_smoke_linkage_chart_stage111_execution_replay_intake_acceptance_v1.png`
  - `qmt_roll_stage111_c9_minrisk_execution_replay_intake_acceptance_field_contract_chart_stage111_execution_replay_intake_acceptance_v1.png`

## 视觉检查

- official path intake blockers 图可读：阻断点覆盖权益阶梯、最大回撤段和近端，说明数据 gate 不是针对局部窗口。
- Stage932 linkage chart 可读：多个 session 有 order/trade/tick 行，但红色 valid sample gate 全为 `0`。
- intake gate chart 可读：`licensed_historical_quote_depth_imported`、`broker_or_production_execution_replay_imported`、`stage932_format_sample_not_strategy_sample`、`field_contract_all_pass`、`any_source_rule_research_allowed` 全部 blocked。
- field contract chart 可读：manifest、historical quote/depth、execution replay、context、right-tail gate 全部缺失或未联通。

## 结论

- 本阶段结论：`stage111_intake_acceptance_built_no_rule_data_still_blocked`。
- 是否进入下一步：是，但仍然只能推进数据接入，不进入策略规则。
- 下一步：
  - 优先导入/采购授权 historical quote/depth/orderflow，要求 raw_file、raw_sha256、schema_hash、source license、timezone、calendar version 完整。
  - 或导出/捕获同源 broker/production execution replay，要求 `bridge_signal_id -> order_reference -> exact vt_orderid -> EVENT_ORDER/EVENT_TRADE/EVENT_TICK` join。
  - 如果暂时没有数据，只能继续做 forward capture acceptance harness，积累自然 OOS 样本，不回填历史规则。

## 过拟合反思

- 运行前判断：否。Stage111 只审计数据能否进入研究，不按收益、年份、品种、方向或阈值构造规则。
- 运行后判断：否。即使 Stage932 有 `102` 行格式样本，也没有因为“有行”而放行，全部按同源联通和字段合同 fail-closed。
- 原因：验收条件来自外部执行回放原则和本线 Stage103/110 合同，不使用盈亏结果调整 gate。

## 继续价值反思

- 运行前判断：是。Stage110 后必须防止把 smoke/dry-run/只读历史行误当成执行回放。
- 运行后判断：是。Stage111 把下一步的判定标准固化成可复跑脚本，后续一旦有新数据，可以先跑验收器再决定是否允许规则研究。
- 原因：当前目标仍需要分钟级高质量信号，但没有同源执行/盘口数据时继续造 OHLC 规则是在原地过拟合；把数据接入 gate 做硬，才是能穿越周期的前置工作。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage111 结论与后续边界。
- 是否更新 `research/registry.md`：否，非正式候选、非跨线合并。
- 是否追加根目录 `memory.md/back_log.md`：否，非重要突破版本。
