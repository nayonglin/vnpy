# Stage112 授权微观结构数据包验收器

## 基本信息

- 时间：2026-06-20 17:02
- 工作模式：day
- 研究线：`futures_trend_c9_minrisk_highquality`
- 阶段性质：只读数据入口验收器；不写真引擎、不新增交易规则、不触发 A/B、不改正式配置、不连接 CTP、不调用订单 API。
- 决策：`stage112_authorized_microstructure_data_drop_validator_built_no_data_no_rule`
- 重要突破版本：否。它是数据工程闸门版本，价值在于防止旧 Tq/Stage932/smoke 产物被误包装成微观结构规则数据。

## 开始前反思

- 是否在过拟合：否。本阶段没有按年份、品种、方向、盈亏 cohort 或参数阈值筛交易，只固定授权数据包验收字段和覆盖要求。
- 是否还有价值继续：是。Stage110/111 已证明现有本地数据不能支撑规则，本阶段把下一步“拿到什么数据才算可继续”固化成可复跑工具，比继续挖旧样本更有价值。

## 外部调研与判断

- Databento MBO 文档：MBO 是按 order id keyed 的逐笔订单簿事件，包含 add/cancel/modify/trade/fill/book clear 等事件，字段含 `ts_recv`、`ts_event`、`action`、`side`、`price`、`size`、`order_id`、`sequence`。判断：若要研究队列位置、挂撤单压力或真实 orderflow，必须优先要求 MBO/L3。
- Databento MBP-10 文档：MBP-10 是按价格聚合的 top-10 深度事件，含 bid/ask price/size/order count。判断：若只做盘口深度、imbalance、冲击成本和可成交性审计，MBP-10/L2 可以作为次优可验收形态，但不能替代队列级 MBO。
- Apache Parquet Metadata 文档：Parquet 文件元数据可以用于 schema/page metadata 检查。判断：Stage112 可以用 Parquet metadata 快速验 schema，但 raw hash、schema hash、query params、source permission 仍必须在 manifest 中保存，不能只信派生 parquet。
- LOBSTER order book reconstruction 论文页：order book reconstruction 依赖 order-driven market 的逐订单处理算法和 ITCH 类原始事件。判断：分钟 OHLC 或 L1 tick 不足以替代历史盘口/订单簿事件，必须保留原始事件和可复算 provenance。

调研结论：后续微观结构路线只接受授权 MBO/L3 或 MBP-10/L2 top-10 depth 包；本地 Tq tick、Stage932 smoke、read-only snapshot、synthetic/dry-run 行继续只能做 TCA/forward-watch/schema 参考，不能进入策略规则。

参考链接：

- https://databento.com/docs/schemas-and-data-formats/mbo
- https://databento.com/docs/schemas-and-data-formats/mbp-10
- https://parquet.apache.org/docs/file-format/metadata/
- https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1977207

## 本阶段改动

- 新增工具：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage112_authorized_microstructure_data_drop_validator.py`
- 新增输出目录：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage112_authorized_microstructure_data_drop_validator/`
- 新增 intake 根目录验收对象，但未创建输入目录：
  - `research/lines/futures_trend_c9_minrisk_highquality/data/authorized_microstructure_intake`
  - `research/lines/futures_trend_c9_minrisk_highquality/inputs/authorized_microstructure_intake`
- 新增 schema 合同：
  - `authorized_mbo_l3`
  - `authorized_mbp10_l2`
  - `vnpy_l1_tick_forward_watch_only` 仅 forward-watch/TCA，不 rule-ready。
- 新增 hard gates：
  - 授权 intake root + manifest 存在
  - raw file / raw sha256 / schema hash / source permission 完整
  - MBO/L3 或 MBP-10/L2 深度 schema
  - 单一同源或显式 normalized source map
  - 不含 Tq/smoke/Stage932/synthetic/dry-run 降级标记
  - timestamp-ready 覆盖 >=95%
  - right-tail / bottom-loss / maxDD context 视觉覆盖

## 参数与结果变更

- 新增参数：固定 `2` 个 intake root；固定 `9` 个 hard acceptance gates；固定 `4` 个 coverage gates。
- 修改参数：无。
- 删除参数：无。
- 新增回测结果：无真实回测；只复用当前官方路径资金曲线生成视觉 gate。
- 修改回测结果：无。
- 删除回测结果：无。

当前路径指标保持不变：

| 指标 | 数值 |
| --- | ---: |
| 期末权益 | 39,176,437.60 |
| 总收益 | 26017.6251% |
| 最大回撤 | -45.0827% |
| Sharpe | 1.6331 |
| 总滑点 | 2,730,130 |
| 总交易次数 | 787 |
| 胜率 | 36.0902% |
| broker10 峰值 | 111.7365% |

## 关键验收结果

| 项目 | 结果 |
| --- | ---: |
| candidate_intake_root_count | 2 |
| existing_candidate_intake_root_count | 0 |
| manifest_file_count | 0 |
| manifest_row_count | 0 |
| data_file_count | 0 |
| basic_intake_pass_file_count | 0 |
| rule_ready_data_file_count | 0 |
| accepted_mbo_file_count | 0 |
| accepted_mbp10_file_count | 0 |
| acceptance_gate_pass_count | 0 / 9 |
| coverage_gate_pass_count | 0 / 4 |
| true_engine_allowed | 0 |
| strategy_feature_usable | 0 |

覆盖要求：

| gate | required | accepted |
| --- | ---: | ---: |
| timestamp_ready_order_windows | 219，要求 >=95% | 0 |
| right_tail_visual_orders | 18，要求 100% | 0 |
| bottom_loss_visual_orders | 18，要求 100% | 0 |
| maxdd_context_orders | 24，要求视觉包覆盖 | 0 |

## 视觉产物

- official path data-drop gate：`qmt_roll_stage112_c9_minrisk_authorized_microstructure_data_drop_validator_official_path_data_drop_gate_stage112_authorized_microstructure_data_drop_validator_v1.png`
- inventory chart：`qmt_roll_stage112_c9_minrisk_authorized_microstructure_data_drop_validator_inventory_chart_stage112_authorized_microstructure_data_drop_validator_v1.png`
- schema gate chart：`qmt_roll_stage112_c9_minrisk_authorized_microstructure_data_drop_validator_schema_gate_chart_stage112_authorized_microstructure_data_drop_validator_v1.png`
- coverage requirement chart：`qmt_roll_stage112_c9_minrisk_authorized_microstructure_data_drop_validator_coverage_requirement_chart_stage112_authorized_microstructure_data_drop_validator_v1.png`

视觉观察：

- 资金/回撤/broker10 路径仍显示当前目标的关键问题：右尾强，但 `2022` 主回撤与 broker10 尖峰仍是必须处理的结构风险。
- inventory 图显示两个授权 intake 根目录都不存在，不存在可验收数据包。
- schema gate 图 9 个 hard gate 全红，说明没有任何数据能进入微观结构规则研究。
- coverage 图显示 Stage108 提出的 `219/18/18/24` 覆盖要求全部未满足；这防止只拿局部 right-tail 或 bottom-loss 样本做过拟合规则。

## 结论

Stage112 把“下一步拿到什么数据才算继续微观结构路线”固化成可复跑验收器。当前没有授权 MBO/L3 或 MBP-10/L2 数据包，也没有通过 Stage111 的同源执行回放，因此不得进入 true engine、A/B、正式候选或任何分钟/盘口规则。

旧本地 Tq tick、Stage608 read-only probe、Stage932 smoke、Stage591/587/605/615 代码合同仍然只能作为负证据、TCA 或 forward-watch/schema 参考，不得包装成策略研究数据。

## 后续规划和 TODO

1. 若拿到授权数据包，放入固定 intake root，并提供 manifest：`data_file`、`raw_file`、`raw_sha256`、`schema_hash`、`source_license`、`query_params`、`timezone`、`calendar_version`、覆盖指标必须完整。
2. 先复跑 Stage112；只有 MBO/L3 或 MBP-10/L2 schema、raw provenance、授权权限、覆盖 gate 全过，才允许进入 Stage111 或等价 execution/intake gate。
3. 只有 Stage112/111 均通过后，才讨论下一阶段只读规则预检；通过前继续做 procurement/import/forward-capture 验收，不造内部 OHLC 规则。

## 结束反思

- 是否在过拟合：否。输出是数据合同和验收器，不使用盈亏标签构造规则，也不调整策略参数。
- 是否还有价值继续：有，但价值集中在“获取或导入授权数据包并复跑验收”。如果没有新数据，继续从现有分钟 OHLC、Tq tick、smoke row 中挖规则的边际价值很低且过拟合风险高。
