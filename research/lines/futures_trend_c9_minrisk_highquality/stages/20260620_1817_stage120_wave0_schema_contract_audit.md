# Stage120 W0 schema contract audit

## 基本信息

- 时间：2026-06-20 18:17
- 工作模式：day
- 研究线：`futures_trend_c9_minrisk_highquality`
- 工作区：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：W0 授权盘口数据 canonical schema 合同与视觉审计；不写真引擎、不新增交易规则、不触发 A/B、不改正式配置、不连接 CTP、不调用订单 API、不下载外部数据。
- 决策：`stage120_schema_contract_built_real_w0_missing_no_strategy`
- 重要突破版本：否。它固定真实 W0 到货后的字段验收合同，但当前没有真实 W0 数据。
- 是否触发 A/B：否。没有候选策略，也没有有价值新策略版本。

## 开始前反思

- 是否在过拟合：否。本阶段只定义授权盘口数据的字段语义、schema gate 与可视化验收，不读取收益分组、不做阈值、不筛产品/年份/方向。
- 是否还有价值继续：是。Stage117 只证明 raw/parquet/proof、时间跨度和 `ts_event/ts_recv` 等基础可读性；真实盘口数据如果字段语义不固定，后续“高质量信号”规则会建立在错误数据上。

## 外部调研与判断

- Databento schema 文档把 MBO 定义为 L3 full order book，MBP-10 定义为 L2 top-ten aggregate depth；判断：W0 必须区分 `authorized_mbo_l3_preferred` 与 `authorized_mbp10_l2_minimum`，不能把顶一档 synthetic parquet 当成 MBP-10。
- Databento common fields 文档强调 `ts_recv` / `ts_event`、index timestamp、UTC 与 start-inclusive/end-exclusive 语义；判断：Stage120 继续把 `ts_event`、`ts_recv`、`sequence` 作为两个 schema 共享硬字段。
- Apache Arrow 文档说明 schema-level 与 field-level metadata 可保留；判断：真实 normalized parquet 应保留可审计字段/元数据，不能只靠文件名解释语义。
- Frictionless Table Schema 要求字段名、类型、约束可描述；判断：W0 需要 canonical field contract 和 accepted aliases，避免供应商列名变化导致人工解释。
- LOBSTER order book reconstruction 论文强调订单簿重建依赖通用 order-processing algorithm；判断：MBO/L3 合同必须包含 `action/side/price/size/order_id`，否则不能支持订单级状态重建。

调研结论：Stage120 的职责是把“到货数据是否具备盘口研究资格”变成机械 schema gate；它不是替代 Stage117，也不是策略规则。真实路径应是 Stage119 生成 manifest、Stage117 验 raw/proof/time span、Stage120 验 canonical schema，然后才允许讨论 Stage112/113 intake。

参考链接：

- https://databento.com/docs/schemas-and-data-formats
- https://databento.com/docs/schemas-and-data-formats/mbp-10
- https://databento.com/docs/standards-and-conventions/common-fields-enums-types
- https://arrow.apache.org/docs/python/data.html
- https://specs.frictionlessdata.io/table-schema/
- https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1977207

## 本阶段改动

- 新增工具：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage120_wave0_schema_contract_audit.py`
- 新增输出目录：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage120_wave0_schema_contract_audit/`
- 新增核心输出：
  - `canonical_field_contract`：固定 MBP-10 / MBO canonical 字段、别名、字段语义与 contract hash。
  - `w0_request_schema_status`：逐 W0 request 绑定 required schema 与 schema contract。
  - `manifest_schema_audit`：对 Stage116 空 manifest 与 Stage119 synthetic manifest 做 schema 差距审计。
  - `schema_contract_gate_status`：规划、反挑样本锁、真实 data hard gate 状态。

## 参数与结果变更

- 新增 schema 合同：
  - MBP-10 minimum：`43` 个硬字段，包含 `ts_event/ts_recv/sequence` 与 10 档 bid/ask price/size。
  - MBO L3 preferred：`8` 个硬字段，包含 `ts_event/ts_recv/sequence/action/side/price/size/order_id`。
- 新增参数：
  - `real_w0_schema_contract_pass=0`
  - `real_w0_data_delivered=0`
  - `real_stage112_intake_allowed_now=0`
  - `true_engine_allowed=0`
  - `strategy_feature_usable=0`
- 修改参数：无。
- 删除参数：无。
- 新增回测结果：无真实回测；只复用当前路径资金曲线做 schema 请求覆盖视觉检查。
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

## 关键结果

| 项目 | 结果 |
| --- | ---: |
| W0 request_count | 41 |
| MBP-10 minimum request_count | 30 |
| MBO L3 preferred request_count | 11 |
| contract_field_count | 48 |
| mbp10_hard_field_count | 43 |
| mbo_hard_field_count | 8 |
| planning_gate | 4/4 |
| anti_selection_gate | 2/2 |
| data_hard_gate | 0/2 |
| synthetic_schema_structural_pass_count | 0 |
| real_w0_schema_structural_pass_count | 0 |
| real_w0_schema_contract_pass | 0 |
| true_engine_allowed | 0 |

Gate 结果：

| gate | 结果 |
| --- | --- |
| `w0_request_schema_mapped` | `41/41` 通过 |
| `universal_time_sequence_contract_defined` | `ts_event/ts_recv/sequence` 通过 |
| `mbp10_top10_ladder_contract_defined` | `43/43` 通过 |
| `mbo_l3_order_event_contract_defined` | `8/8` 通过 |
| `synthetic_fixture_blocked_from_real_contract` | 通过，synthetic `41` 行 accept_now 全为 `0` |
| `strategy_locks_zero` | 通过 |
| `real_w0_manifest_delivered` | `0/41` 失败 |
| `real_w0_schema_contract_pass` | `0/41` 失败 |

## 视觉产物

- official path schema status：`qmt_roll_stage120_c9_minrisk_wave0_schema_contract_audit_official_path_schema_status_stage120_wave0_schema_contract_audit_v1.png`
- contract field matrix：`qmt_roll_stage120_c9_minrisk_wave0_schema_contract_audit_contract_field_matrix_stage120_wave0_schema_contract_audit_v1.png`
- request schema exchange matrix：`qmt_roll_stage120_c9_minrisk_wave0_schema_contract_audit_request_schema_exchange_matrix_stage120_wave0_schema_contract_audit_v1.png`
- synthetic schema gap chart：`qmt_roll_stage120_c9_minrisk_wave0_schema_contract_audit_synthetic_schema_gap_chart_stage120_wave0_schema_contract_audit_v1.png`

视觉观察：

- official path schema status 图把 W0 request 点标在权益、回撤、broker10 三条路径上；请求覆盖右尾、回撤和保证金压力区，但真实 W0 仍缺失。
- contract field matrix 显示 MBP-10 与 MBO 字段合同互相隔离，只有 `ts_event/ts_recv/sequence` 是共享硬字段。
- request schema exchange matrix 显示 W0 共有 `30` 个 MBP-10 minimum request、`11` 个 MBO L3 preferred request；交易所分布为 CZCE `24`、SHFE `12`、DCE `4`、GFEX `1`。
- synthetic schema gap chart 显示 Stage119 合成 parquet 不满足真实合同：MBP-10 平均缺 `36` 个 canonical 字段，MBO 缺 `5` 个；因此 synthetic fixture 不能被误用作真实盘口研究数据。

## 结论

Stage120 证明：W0 的 schema 合同已经固定，真实数据到货后不能只通过 Stage117 的基础可读性就进入研究，还必须满足 Stage120 的 canonical field contract。当前真实状态仍是 `real_w0_data_delivered=0`、`real_w0_schema_contract_pass=0`、`real_stage112_intake_allowed_now=0`，因此 true engine、A/B、正式候选和微观结构/分钟规则预检继续阻塞。

本阶段的有效进展是：把授权盘口数据的“字段是否够研究”从人工解释变成机械 gate，且明确 synthetic fixture 虽能测试文件链路，但不能满足真实 MBP-10/MBO schema 合同。

## 后续规划和 TODO

1. 真实 W0 drop 到货后，先用 Stage119 生成 manifest。
2. 用 Stage117 验 raw/proof/time span/sha256/sequence proof。
3. 用 Stage120 验 canonical schema；只有真实 `41/41` 通过后，才允许 Stage112/113 intake。
4. 若供应商只给一档 bid/ask 或缺 `action/side/price/size/order_id`，不得把它降格包装成 MBO/L3 或 MBP-10 研究数据；只能补数或改合同。
5. 没有真实 W0 前，不再围绕本地 Tq tick、synthetic parquet、旧 OHLC 代理或 Stage932 smoke 构造交易规则。

## 结束反思

- 是否在过拟合：否。Stage120 没有使用收益标签做规则，也没有参数搜索；字段合同来自数据语义和外部盘口 schema 资料。
- 是否还有价值继续：有。它进一步降低真实数据到货后的解释自由度；但在真实 W0 仍为 `0` 的情况下，本线仍不能推进 alpha 或 true engine。
