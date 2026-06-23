# Stage103 订单流/盘口数据合同审计

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-20 15:13 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：数据合同与路线闸门审计；不是真引擎、不生成交易规则
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - vn.py `TickData` GitHub：`https://github.com/vnpy/vnpy/blob/master/vnpy/trader/object.py`
  - vn.py `BarGenerator.update_tick` GitHub：`https://github.com/vnpy/vnpy/blob/master/vnpy/trader/utility.py`
  - LocalCTP GitHub：`https://github.com/dearleeyoung/LocalCTP`
  - CTP/ThostFtdc `DepthMarketData` GitHub 参考：`https://github.com/QuantBox/CTP/blob/master/C-CTP/src/QuantBox.C2CTP/include/CTP/ThostFtdcUserApiStruct.h`
- 我的判断：vn.py 的 tick schema 能表达 last trade、盘口快照和日内统计，`BarGenerator` 也说明分钟K来自 tick 聚合；但这只证明“实时/forward 可记录”，不证明“历史全覆盖、同源、可复验、能判断队列/成交主动方向”。LocalCTP/CTP 类链路可做仿真或实时接入，但不能替代历史授权 quote/depth/orderflow archive。Stage102 已证明分钟OHLC近触价路线不够，因此 Stage103 必须把数据合同写硬：没有授权历史盘口/队列/成交流或生产执行回放前，不能进入微观结构规则。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage103_orderflow_data_contract_audit.py`
- 修改脚本：无
- 删除脚本：无
- 新增输出：
  - `local_asset_audit`
  - `data_contract`
  - `action_queue`
  - `promotion_gate`
  - `official_path_data_route_chart`
  - `readiness_heatmap`
  - `action_queue_chart`
  - `promotion_gate_chart`
- 新增参数：无
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用既有基准路径；读取 Stage068/080/099/102 的既有证据。
- 账户规模：沿用基准路径，仅作背景路径。
- 成本口径：沿用基准统计，总滑点 `2,730,130`。
- 样本过滤：无新增收益过滤；只做本地资产和数据路线合同审计。
- 策略/归因口径：数据工程闸门，`rule_allowed_route_count=0`、`true_engine_allowed_route_count=0`、`ab_allowed_route_count=0`、`strategy_feature_usable=0`。

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：closed-lot win rate `36.0902%`
- 其他关键指标：
  - `decision=stage103_orderflow_contract_blocks_rules_data_first`
  - `route_count=6`
  - `local_asset_count=7`
  - `initial_entry_tick_ready_count=5`
  - `initial_entry_tick_planned_count=219`
  - `initial_entry_tick_ready_rate_pct=2.2831%`
  - `stage102_low_resolution_order_count=93`
  - `rule_allowed_route_count=0`
  - `true_engine_allowed_route_count=0`
  - `ab_allowed_route_count=0`
  - `max_contract_pass_rate_pct=30.0000%`
  - `promotion_gate_count=6`
  - `promotion_gate_pass_count=0`
  - `official_config_changed=0`、`strategy_rule_created=0`、`true_engine_run=0`、`ab_triggered=0`、`order_api_called=0`、`ctp_connected=0`

## 视觉观察

- official path data route chart：资金曲线未改变；底部本地资产柱显示 Stage068 initial-entry tick 仅 `5/219` ready，Stage102 low-resolution OHLC 区仍是大阻断。
- readiness heatmap：`authorized_historical_quote_depth` 与 `broker_or_production_execution_replay` 当前全红，说明最有价值路线还没有本地证据；`ctp_realtime_forward_capture` 只满足 top-of-book schema 与权限/可接入假设，不满足历史覆盖、同源执行、raw hash、右尾保护。
- action queue chart：最高信息增益是授权历史 quote/depth 和生产执行回放，但摩擦也最高；local Tq tick 和 transform union 信息增益低且已被降级为 TCA/forward watch。
- promotion gate chart：六个 gate 全部 blocked；核心阻断是 initial-entry tick 覆盖仅 `2.2831%`、无历史全覆盖、无同源执行账本、无微观结构 raw provenance、Stage102 OHLC 近触价低分辨率区 `93` 笔、没有任何右尾保护审计通过。

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage103_orderflow_data_contract_audit/qmt_roll_stage103_c9_minrisk_orderflow_data_contract_audit_report_stage103_orderflow_data_contract_audit_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage103_orderflow_data_contract_audit/qmt_roll_stage103_c9_minrisk_orderflow_data_contract_audit_summary_stage103_orderflow_data_contract_audit_v1.csv`
- decision：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage103_orderflow_data_contract_audit/qmt_roll_stage103_c9_minrisk_orderflow_data_contract_audit_decision_stage103_orderflow_data_contract_audit_v1.json`
- local asset audit：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage103_orderflow_data_contract_audit/qmt_roll_stage103_c9_minrisk_orderflow_data_contract_audit_local_asset_audit_stage103_orderflow_data_contract_audit_v1.csv`
- data contract：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage103_orderflow_data_contract_audit/qmt_roll_stage103_c9_minrisk_orderflow_data_contract_audit_data_contract_stage103_orderflow_data_contract_audit_v1.csv`
- action queue：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage103_orderflow_data_contract_audit/qmt_roll_stage103_c9_minrisk_orderflow_data_contract_audit_action_queue_stage103_orderflow_data_contract_audit_v1.csv`
- promotion gate：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage103_orderflow_data_contract_audit/qmt_roll_stage103_c9_minrisk_orderflow_data_contract_audit_promotion_gate_stage103_orderflow_data_contract_audit_v1.csv`
- charts：
  - `qmt_roll_stage103_c9_minrisk_orderflow_data_contract_audit_official_path_data_route_chart_stage103_orderflow_data_contract_audit_v1.png`
  - `qmt_roll_stage103_c9_minrisk_orderflow_data_contract_audit_readiness_heatmap_stage103_orderflow_data_contract_audit_v1.png`
  - `qmt_roll_stage103_c9_minrisk_orderflow_data_contract_audit_action_queue_chart_stage103_orderflow_data_contract_audit_v1.png`
  - `qmt_roll_stage103_c9_minrisk_orderflow_data_contract_audit_promotion_gate_chart_stage103_orderflow_data_contract_audit_v1.png`

## 结论

- 本阶段结论：订单流/盘口是正确的下一信息层，但当前仓库没有满足规则研究的数据合同；微观结构 route 必须 data-first。
- 原因：
  - Stage068 initial-entry tick 覆盖只有 `5/219=2.2831%`，远低于能做全样本右尾保护审计的最低要求。
  - Stage080 已证明本地 Tq tick 不能统一映射官方同源执行语义，只能 TCA/forward watch。
  - Stage102 证明分钟 OHLC 近触价低分辨率区有 `93` 笔，且混有右尾与底部亏损，不能继续靠 OHLC 拆。
  - CTP/vn.py 的实时 tick schema 有价值，但没有历史全覆盖、raw packet hash、同源执行账本和右尾保护前，不能变成回测规则。
- 下一步：
  - 优先数据路线：采购/接入授权历史 tick/quote/depth/orderflow，或导出 broker/生产执行回放账本；字段必须包含 event_timestamp、exchange_timestamp、contract、bid/ask、depth、last trade、volume/OI、raw hash、schema version、source permission。
  - 如果暂不做采购，只允许做严格远离触价、非 close 后立即成交、不会切断首根/第二根右尾的分钟级只读 preflight；不允许围绕 Tq tick、first/average/topbook transform 或 OHLC near-touch bucket 救参。

## 过拟合反思

- 运行前判断：否。Stage103 是数据合同审计，不按收益或亏损样本设计规则。
- 运行后判断：否。结论是阻止当前资产规则化，而不是用局部 right-tail/bottom-loss 反推条件。
- 原因：所有 gate 都是数据前提、同源性、历史覆盖、raw provenance 和右尾保护，未使用产品、方向、年份、月份或收益阈值。

## 继续价值反思

- 运行前判断：有价值。Stage102 后必须判断是否值得继续微观结构方向。
- 运行后判断：研究线继续有价值，但微观结构规则必须先补数据；没有授权历史盘口/队列/成交流时，继续在现有 Tq tick 或分钟OHLC上挖规则价值低。
- 原因：当前本地资产能解释执行质量，但不能证明普世、可穿越周期、右尾安全的交易规则；数据合同收紧能避免后续过拟合。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage103 摘要和下一步边界。
- 是否更新 `research/registry.md`：否，不是正式候选、重要突破或路线合并。
- 是否追加根目录 `memory.md/back_log.md`：否，不是正式候选、重要突破或跨线合并。
