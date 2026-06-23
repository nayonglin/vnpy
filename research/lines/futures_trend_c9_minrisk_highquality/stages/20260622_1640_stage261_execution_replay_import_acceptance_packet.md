# Stage261 执行回放导入验收包

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-22 16:40`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读 execution replay import acceptance packet；不创建交易规则，不运行 true engine，不触发 A/B，不改正式配置，不连接 CTP/SimNow，不调用订单 API。
- 是否重要突破：否。它把 Stage260 后的数据到货验收标准固化，但不是策略候选。
- 是否触发A/B：否。

## 外部调研与判断

- vn.py `OrderData/TradeData` 以 `vt_orderid`、`vt_tradeid`、`vt_symbol`、`direction`、`offset`、`price`、`volume`、`datetime` 串联订单与成交：https://github.com/vnpy/vnpy/blob/master/vnpy/trader/object.py
- vn.py CTA engine 在订单/成交事件处理中用 `vt_orderid` 维护 strategy-order 映射，并处理 `EVENT_ORDER`/`EVENT_TRADE` 路径：https://github.com/vnpy/vnpy_ctastrategy/blob/main/vnpy_ctastrategy/engine.py
- CTP `ReqOrderInsert` 正确路径会回报 `OnRtnOrder`、`OnRtnTrade`，因此回放包必须能覆盖订单状态与成交回报，而不只是请求草案：https://documentation.help/CTP-API-cn/REQORDERINSERT.html
- FIX `ExecutionReport(8)` 用于确认订单、状态变化、成交回报、拒单等；Drop Copy/FIX 语义需要 `OrderID/ExecID/OrdStatus/ExecType/LastPx/LastQty/TransactTime` 等链路字段：https://www.onixs.biz/fix-dictionary/4.4/msgtype_8_8.html
- 我的判断：执行回放导入必须同时满足 vn.py 的 `vt_orderid/vt_tradeid` 事件链、CTP 的订单/成交回报链、FIX 的执行报告链，以及本线 Stage260 固定的 raw hash/license/全 entry/右尾底部亏损视觉 gate。只要缺任一环，就不能进入高质量信号规则、true engine 或 A/B。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage261_execution_replay_import_acceptance_packet.py`
- 新增输出目录：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage261_execution_replay_import_acceptance_packet/`
- 新增产物：
  - required schema contract：`58` 个必需字段
  - field mapping template：`58` 行，映射 vn.py / CTP / FIX Drop Copy 来源
  - manifest template：`7` 类文件角色
  - fixture selftest：`6` 个自测 case
  - acceptance gate：`8` 项
  - operator runbook
  - 5 张视觉图
- 新增参数：
  - `FULL_ENTRY_DECISION_COUNT=219`
  - `RIGHT_TAIL_REQUIRED_COUNT=18`
  - `BOTTOM_LOSS_REQUIRED_COUNT=18`
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：沿用 Stage251 官方 A 臂曲线，`2018-01-02` 至 `2026-06-15`
- 账户规模：沿用官方 A 臂 `150,000`
- 成本口径：沿用官方 A 臂成本口径
- 样本过滤：无新增交易样本；只继承 Stage260 的执行回放覆盖缺口
- 策略/归因口径：数据导入验收，不生成交易信号

## 结果

- 官方 A 臂不变：
  - 期末权益：`39,176,437.60`
  - 总收益：`26017.6251%`
  - 最大回撤：`-45.0827%`
  - Sharpe：`1.6331`
  - 总滑点：`2,730,130`
  - 总交易次数：`787`
  - 胜率：`53.2560%`
- Stage261 核心指标：
  - decision：`stage261_execution_replay_import_acceptance_packet_ready_no_data_no_rule`
  - required schema field count：`58`
  - manifest file roles：`7`
  - field mapping rows：`58`
  - fixture selftest：`6/6`
  - acceptance gate：`3/8`
  - real replay package supplied：`0`
  - accepted real replay package：`0`
  - Stage260 accepted same-source replay file：`0`
  - full orderflow/execution replay coverage：`0/219`
  - missing：`219/219`
  - field contract pass：`0/18`
- 自测拒收逻辑：
  - synthetic full schema：拒收
  - missing license：拒收
  - broken order-trade join：拒收
  - low coverage：拒收
  - smoke/read-only/adapter：拒收
  - hypothetical target real full contract：正向路径可通过，用于证明 validator 不是只会全拒。

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage261_execution_replay_import_acceptance_packet/qmt_roll_stage261_c9_minrisk_execution_replay_import_acceptance_packet_report_stage261_execution_replay_import_acceptance_packet_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage261_execution_replay_import_acceptance_packet/qmt_roll_stage261_c9_minrisk_execution_replay_import_acceptance_packet_summary_stage261_execution_replay_import_acceptance_packet_v1.csv`
- schema：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage261_execution_replay_import_acceptance_packet/qmt_roll_stage261_c9_minrisk_execution_replay_import_acceptance_packet_required_schema_contract_stage261_execution_replay_import_acceptance_packet_v1.csv`
- field mapping：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage261_execution_replay_import_acceptance_packet/qmt_roll_stage261_c9_minrisk_execution_replay_import_acceptance_packet_field_mapping_template_stage261_execution_replay_import_acceptance_packet_v1.csv`
- manifest template：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage261_execution_replay_import_acceptance_packet/qmt_roll_stage261_c9_minrisk_execution_replay_import_acceptance_packet_manifest_template_stage261_execution_replay_import_acceptance_packet_v1.csv`
- fixture selftest：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage261_execution_replay_import_acceptance_packet/qmt_roll_stage261_c9_minrisk_execution_replay_import_acceptance_packet_fixture_selftest_results_stage261_execution_replay_import_acceptance_packet_v1.csv`
- runbook：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage261_execution_replay_import_acceptance_packet/qmt_roll_stage261_c9_minrisk_execution_replay_import_acceptance_packet_operator_runbook_stage261_execution_replay_import_acceptance_packet_v1.md`
- 视觉图：
  - official path import gate：`qmt_roll_stage261_c9_minrisk_execution_replay_import_acceptance_packet_official_path_import_gate_status_stage261_execution_replay_import_acceptance_packet_v1.png`
  - required schema matrix：`qmt_roll_stage261_c9_minrisk_execution_replay_import_acceptance_packet_required_schema_matrix_stage261_execution_replay_import_acceptance_packet_v1.png`
  - fixture selftest matrix：`qmt_roll_stage261_c9_minrisk_execution_replay_import_acceptance_packet_fixture_selftest_matrix_stage261_execution_replay_import_acceptance_packet_v1.png`
  - acceptance gate cascade：`qmt_roll_stage261_c9_minrisk_execution_replay_import_acceptance_packet_acceptance_gate_cascade_stage261_execution_replay_import_acceptance_packet_v1.png`
  - next action chart：`qmt_roll_stage261_c9_minrisk_execution_replay_import_acceptance_packet_next_action_chart_stage261_execution_replay_import_acceptance_packet_v1.png`

## 结论

- 本阶段结论：导入验收包已 ready，但真实 broker/production execution replay 仍未到货；当前仍不能进入策略规则、true engine、A/B 或正式候选。
- 是否进入下一步：不进入交易规则。只有真实回放包或授权 orderflow 到货后，才按 Stage261 包跑验收。
- 下一步：
  1. 使用 Stage261 runbook 接收真实 broker/production replay package；
  2. 或采购/采集授权 orderflow/depth/MBO/MBP10；
  3. 若没有新数据，只能做不改变正式持仓路径的账户外层治理；
  4. 明确禁止回到本地 OHLCV/OI、smoke/read-only、adapter、pending order 或普通回测 ledger 上救参。

## 过拟合反思

- 运行前判断：否。Stage261 只固定导入验收与拒收门槛，不使用历史盈亏扫阈值。
- 运行后判断：否。结果是继续阻断规则化，并明确拒收 synthetic/smoke/read-only/低覆盖数据。
- 原因：没有新增任何交易规则、参数优化、品种/年份/方向补丁或 true engine 候选；正向 fixture 只是 validator 自测，不是研究样本。

## 继续价值反思

- 运行前判断：有价值。Stage260 证明数据缺口是真 blocker，先固定导入合同能避免未来把伪数据误接成规则。
- 运行后判断：有价值但边界明确。对真实回放/订单流到货有价值；对继续本地阈值、回测 ledger 或 smoke 文件救参没有价值。
- 原因：本阶段把下一步从“缺数据”细化成可执行的 drop 目录、字段映射、manifest、raw hash/license、219 entry coverage 和右尾/底部亏损视觉覆盖 gate。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage261 摘要。
- 是否更新 `research/registry.md`：否。没有新研究线、正式候选或路线合并。
- 是否追加根目录 `memory.md/back_log.md`：否。它是数据工程验收包，不是正式候选或重要突破。
