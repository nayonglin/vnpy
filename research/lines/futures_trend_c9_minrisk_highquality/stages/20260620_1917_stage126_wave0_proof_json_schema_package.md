# Stage126 W0 proof JSON schema package

## 基本信息

- 时间：2026-06-20 19:17
- 工作模式：day
- 研究线：`futures_trend_c9_minrisk_highquality`
- 工作区：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：W0 proof JSON 结构合同固化；把 Stage124 的 proof 字段自然语言合同升级为 Draft 2020-12 JSON Schema，并生成 41 个 request-specific proof 模板。只做数据交付硬闸门，不写真引擎、不新增交易规则、不触发 A/B、不改正式配置、不连接 CTP、不调用订单 API、不下载外部数据。
- 决策：`stage126_wave0_proof_json_schema_package_built_templates_blocked_no_real_data`
- 重要突破版本：否。它是数据验收工程闸门增强，不是 alpha 或正式候选。
- 是否触发 A/B：否。没有策略候选。

## 开始前反思

- 是否在过拟合：否。本阶段完全不读取收益标签、不按盈亏筛样本、不修改品种/年份/方向/阈值；只把授权 W0 proof 的字段、类型、占位符和 synthetic 禁止规则写成固定 schema。
- 是否还有价值继续：是。Stage125 已能手工审 proof 字段，但真实供应商交付时最容易出现占位符、synthetic/smoke 标记、row_count 为 0、schema_hash 非 64 位 SHA 等机械错误；schema 化能把这些错误提前固定成可复验的拒收规则。

## 外部调研与判断

- JSON Schema 官方文档说明关键字可用来约束类型、必填、枚举、数值范围和对象属性。判断：Stage126 应使用 `required`、`type`、`enum`、`pattern`、`minimum`、`const`、`not` 等基础关键字，避免把供应商口头描述当成验收依据。
- JSON Schema Draft 2020-12 是当前可引用的规范版本。判断：schema 文件显式声明 `$schema=https://json-schema.org/draft/2020-12/schema`，便于后续工具链一致验证。
- Python `jsonschema` 文档说明 `Draft202012Validator.check_schema` 可先验证 schema 自身，`iter_errors` 可返回实例错误。判断：Stage126 要有正例、缺字段负例、synthetic 负例和模板占位负例自测，证明不会误放行。
- `additionalProperties` 可控制对象中非声明字段。判断：本阶段保留 `additionalProperties=true`，允许供应商追加授权元数据；硬字段仍由必填字段和 anti-synthetic 规则兜底，避免过早把供应商扩展字段拒掉。

调研结论：proof schema 只负责结构真实性和反合成污染，不负责市场真实性；真实 W0 仍必须继续经过 Stage125、Stage123、Stage112 和 Stage113。schema 模板必须默认无效，供应商只有替换占位符、提供真实 hash 和非零 row_count 后才可能进入下一道验收。

参考链接：

- https://json-schema.org/understanding-json-schema/keywords
- https://json-schema.org/understanding-json-schema/reference/object
- https://json-schema.org/understanding-json-schema/reference/numeric
- https://json-schema.org/draft/2020-12
- https://python-jsonschema.readthedocs.io/en/stable/validate/

## 本阶段改动

- 新增工具：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage126_wave0_proof_json_schema_package.py`
  - 读取 Stage124 delivery file contract 与 proof field contract。
  - 读取 Stage125 summary，继承当前真实 W0 仍未 ready 的状态。
  - 输出 Draft 2020-12 proof schema：`request_id`、`batch_id`、`vt_symbol`、`required_schema_request`、`vendor`、`license_id`、`dataset`、`schema_hash`、`field_dictionary_version`、`ts_event_timezone`、`ts_recv_timezone`、`first_ts_event`、`last_ts_event`、`row_count`、`sequence_gap_count`、`capture_continuity_proof`、`synthetic_fixture` 共 17 个 required 字段。
  - 为 41 个 W0 request 生成 41 个 proof JSON 模板。
  - 模板中保留 `<...>` 占位符、`row_count=0`、`template_only_not_real_proof=true`，确保模板本身不能被 schema 误判为真实 proof。
  - 运行 4 个 schema 自测：内存正例、缺 `vendor` 负例、`synthetic_fixture=true` 负例、模板占位负例。
  - 输出 summary、schema、template index、validation selftest、gate status、report、decision JSON 和 4 张视觉图。

## 参数与结果变更

- 新增参数：
  - `request_count=41`
  - `proof_template_count=41`
  - `proof_schema_required_field_count=17`
  - `proof_schema_property_count=21`
  - `schema_check_pass=1`
  - `validation_selftest_count=4`
  - `validation_selftest_pass_count=4`
  - `template_placeholder_count=41`
  - `template_schema_valid_count=0`
  - `template_schema_blocked_count=41`
  - `gate_pass_count=7/11`
  - `data_hard_gate_pass_count=0/2`
  - `ready_for_stage125=0`
  - `ready_for_stage123=0`
- 修改参数：无交易参数修改。
- 删除参数：无。
- 新增回测结果：无真实回测；只复用当前官方路径资金曲线做 proof schema 视觉背景。
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
| W0 requests | 41 |
| proof templates | 41 |
| schema required fields | 17 |
| schema valid | 1 |
| validation selftests | 4/4 |
| placeholder templates blocked | 41/41 |
| real proof present | 0/41 |
| ready for Stage125 | 0 |
| ready for Stage123 | 0 |
| true engine allowed | 0 |
| strategy feature usable | 0 |

Gate 解释：

- 通过项：Stage124 request contract、Stage124 proof required fields、Draft 2020-12 schema valid、41/41 模板生成、41/41 模板含占位符、41/41 模板被 schema 阻断、4/4 自测通过。
- 阻塞项：`real_proof_present=0/41`、`stage125_previous_ready_for_stage123=0`、`ready_for_stage125=0/41`、`ready_for_stage123=0`。
- 模板不是真实 proof；它们只是供应商填写格式，不能进入 Stage125/123。

## 视觉产物

- official path proof schema status：`qmt_roll_stage126_c9_minrisk_wave0_proof_json_schema_package_official_path_proof_schema_status_stage126_wave0_proof_json_schema_package_v1.png`
- proof field schema matrix：`qmt_roll_stage126_c9_minrisk_wave0_proof_json_schema_package_proof_field_schema_matrix_stage126_wave0_proof_json_schema_package_v1.png`
- request template readiness matrix：`qmt_roll_stage126_c9_minrisk_wave0_proof_json_schema_package_request_template_readiness_matrix_stage126_wave0_proof_json_schema_package_v1.png`
- validation selftest chart：`qmt_roll_stage126_c9_minrisk_wave0_proof_json_schema_package_validation_selftest_chart_stage126_wave0_proof_json_schema_package_v1.png`

视觉观察：

- official path proof schema status 图继续显示资金、回撤、broker10 曲线和 W0 request marker；底部 gate 视觉上只有 planning/anti-selection 通过，data/final hard 仍失败。
- proof field schema matrix 显示 17 个 required 字段均进入 schema，`schema_hash`、时间戳、枚举、`sequence_gap_count=0`、`synthetic_fixture=false` 等关键约束已结构化。
- request template readiness matrix 前三列为绿色：模板已生成、占位符存在、模板被阻断；后四列为红色：没有真实 proof、不能进入 Stage125/123、不能作为策略输入。
- validation selftest chart 显示正例通过，缺字段、synthetic 和模板占位三类负例全部按预期失败。

## 输出文件

- schema：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage126_wave0_proof_json_schema_package/qmt_roll_stage126_c9_minrisk_wave0_proof_json_schema_package_proof_schema_stage126_wave0_proof_json_schema_package_v1.json`
- templates：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage126_wave0_proof_json_schema_package/proof_templates/`
- template index：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage126_wave0_proof_json_schema_package/qmt_roll_stage126_c9_minrisk_wave0_proof_json_schema_package_proof_template_index_stage126_wave0_proof_json_schema_package_v1.csv`
- validation selftest：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage126_wave0_proof_json_schema_package/qmt_roll_stage126_c9_minrisk_wave0_proof_json_schema_package_validation_selftest_stage126_wave0_proof_json_schema_package_v1.csv`
- gate status：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage126_wave0_proof_json_schema_package/qmt_roll_stage126_c9_minrisk_wave0_proof_json_schema_package_proof_schema_gate_status_stage126_wave0_proof_json_schema_package_v1.csv`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage126_wave0_proof_json_schema_package/qmt_roll_stage126_c9_minrisk_wave0_proof_json_schema_package_summary_stage126_wave0_proof_json_schema_package_v1.csv`
- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage126_wave0_proof_json_schema_package/qmt_roll_stage126_c9_minrisk_wave0_proof_json_schema_package_report_stage126_wave0_proof_json_schema_package_v1.md`

## 结论

Stage126 证明：W0 proof JSON 已有正式 schema 和 request-specific 模板包。schema 自身通过 Draft 2020-12 校验，4 个正/负自测全部符合预期，41 个模板全部因占位符和 `row_count=0` 被阻断，不会误放行为真实 proof。

当前真实状态仍是 `real_proof_present_count=0`、`ready_for_stage125=0`、`ready_for_stage123=0`、`real_w0_data_delivered=0`、`true_engine_allowed=0`、`strategy_feature_usable=0`。因此微观结构/分钟规则预检、true engine、A/B 和正式候选继续阻塞。

## 后续规划和 TODO

1. 把 Stage126 schema 和 41 个 proof 模板作为 W0 供应商交付格式的一部分；供应商必须替换所有 `<...>` 占位符，提供真实 64 位 hash、非零 `row_count`、`sequence_gap_count=0` 和 `synthetic_fixture=false`。
2. 真实 W0 drop 到货后，先跑 Stage125 receipt preflight；只有 `ready_for_stage123=1` 时，再跑 Stage123 全链路。
3. 即使 Stage126/125 通过，也不能进入策略研究；必须继续通过 Stage123、Stage112 和 Stage113。
4. 在真实 W0 通过前，不再用 synthetic、旧 OHLC、本地 Tq tick、smoke 或模板 proof 构造微观结构/分钟策略规则。

## 结束反思

- 是否在过拟合：否。Stage126 没有任何收益目标、交易阈值、品种/年份/方向筛选，只把 W0 证明文件的普世工程约束固定成 schema；模板默认无效，反而降低数据污染和反选择风险。
- 是否还有价值继续：有。它把真实数据到货后的 proof 错误从人工解释推进到机器可复验；但它本身不推进 alpha，下一步价值取决于真实 W0 数据是否通过 Stage125/123/112/113。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage126 proof schema/template 状态。
- 是否更新 `research/registry.md`：否。本阶段不新增研究线。
- 是否追加根目录 `memory.md/back_log.md`：否。不是正式候选、重要突破或跨线合入。
