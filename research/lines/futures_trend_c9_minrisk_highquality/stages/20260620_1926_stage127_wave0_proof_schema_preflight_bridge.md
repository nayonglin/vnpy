# Stage127 W0 proof schema preflight bridge

## 基本信息

- 时间：2026-06-20 19:26
- 工作模式：day
- 研究线：`futures_trend_c9_minrisk_highquality`
- 工作区：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：W0 proof JSON schema 与 Stage124 request 合同之间的桥接预检；在 Stage126 schema 基础上增加 request_id、batch、合约、schema 类型和 request time span 覆盖校验。只做数据交付硬闸门，不写真引擎、不新增交易规则、不触发 A/B、不改正式配置、不连接 CTP、不调用订单 API、不下载外部数据。
- 决策：`stage127_proof_schema_preflight_bridge_ready_templates_blocked_no_real_data`
- 重要突破版本：否。它是 Stage125/126 之间的验收桥接增强，不是 alpha 或正式候选。
- 是否触发 A/B：否。没有策略候选。

## 开始前反思

- 是否在过拟合：否。本阶段不使用收益、回撤样本、交易方向、产品或年份做任何筛选；只校验 proof 是否属于对应 request，以及 proof 时间范围是否覆盖 request 合同。
- 是否还有价值继续：是。Stage126 能证明 JSON 格式合法，但“格式合法”不等于“该 proof 对应本 request”；真实交付中若复制错 request_id、batch、合约或时间段，单靠 schema 可能仍通过。Stage127 把这类错配提前挡在 Stage123 前。

## 外部调研与判断

- Python `jsonschema` 官方文档说明 `Draft202012Validator.check_schema` 可先检查 schema 自身，`iter_errors` 可枚举实例错误。判断：Stage127 应继续使用 Stage126 的 Draft2020-12 schema 做第一层结构验证。
- JSON Schema 官方 object 文档说明 `additionalProperties` 控制未列出的额外字段，默认允许扩展字段。判断：proof schema 不应因为供应商额外授权字段而拒收，但必须叠加 request 合同校验，否则额外字段无法保证 proof 属于当前 request。
- JSON Schema 官方关键字文档说明 `required`、`type`、`enum`、`pattern`、`minimum`、`const` 等关键字负责实例结构约束。判断：这些字段能挡住 synthetic、占位符、row_count=0、hash 格式错误，但无法表达“first_ts_event 必须早于 request_start、last_ts_event 必须晚于 request_end”的跨文件业务合同，必须在 Stage127 用代码显式校验。
- GitHub `python-jsonschema/jsonschema` 仓库定位该库是 Python JSON Schema 实现。判断：继续使用本地 `.py311` 中已有 `jsonschema`，不引入新依赖或替代验证器。

调研结论：Stage127 的正确形状不是放宽 schema，也不是把 schema 直接当最终验收，而是形成两层闸门：JSON Schema 先验结构，Stage124 request contract 再验身份和时间覆盖。只有两层都过，proof 才能给 Stage125/123 继续使用。

参考链接：

- https://python-jsonschema.readthedocs.io/en/latest/validate/
- https://json-schema.org/understanding-json-schema/reference/object
- https://json-schema.org/understanding-json-schema/keywords
- https://github.com/python-jsonschema/jsonschema

## 本阶段改动

- 新增工具：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage127_wave0_proof_schema_preflight_bridge.py`
  - 读取 Stage124 delivery file contract。
  - 读取 Stage126 proof schema 和 41 个 proof 模板索引。
  - 默认扫描 Stage125 空 drop：`outputs/stage125_wave0_receipt_preflight_audit/empty_drop`。
  - 对每个 request 建立 proof bridge audit：proof 是否存在、JSON 是否可读、schema 是否通过、request_id/batch/vt_symbol/schema 类型是否匹配、`first_ts_event/last_ts_event` 是否覆盖 request_start/request_end、是否仍有占位符、是否带 template flag。
  - 对 41 个 Stage126 模板复验 schema block，确保模板不能变成真实 proof。
  - 增加 5 个桥接自测：内存正例、request_id 错配负例、time span 覆盖不足负例、synthetic true 负例、模板占位负例。
  - 输出 summary、request audit、template audit、integration selftest、gate status、report、decision JSON 和 4 张视觉图。

## 参数与结果变更

- 新增参数：
  - `request_count=41`
  - `observed_proof_file_count=0`
  - `schema_valid_request_count=0`
  - `request_identity_match_count=0`
  - `request_span_cover_count=0`
  - `placeholder_free_request_count=0`
  - `proof_schema_bridge_ready_count=0`
  - `template_count=41`
  - `template_schema_blocked_count=41`
  - `template_schema_valid_count=0`
  - `integration_selftest_count=5`
  - `integration_selftest_pass_count=5`
  - `gate_pass_count=4/11`
  - `data_hard_gate_pass_count=0/4`
  - `ready_for_stage125=0`
  - `ready_for_stage123=0`
- 修改参数：无交易参数修改。
- 删除参数：无。
- 新增回测结果：无真实回测；只复用当前官方路径资金曲线做 proof schema bridge 视觉背景。
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
| observed proof files | 0 |
| schema valid proofs | 0 |
| request identity match | 0 |
| request span cover | 0 |
| proof schema bridge ready | 0 |
| templates blocked | 41/41 |
| integration selftests | 5/5 |
| ready for Stage125 | 0 |
| ready for Stage123 | 0 |
| true engine allowed | 0 |
| strategy feature usable | 0 |

Gate 解释：

- 通过项：Stage126 schema 可用且有效、Stage124 request contract 可用、Stage126 模板 `41/41` 被 schema 阻断、integration selftest `5/5` 通过。
- 阻塞项：真实 proof 文件 `0/41`、真实 proof schema valid `0/41`、request identity match `0/41`、request span cover `0/41`、proof schema bridge ready `0/41`、Stage125 previous ready `0`、Stage123 ready `0`。
- 自测中 `request_id_mismatch_negative` 和 `time_span_undercoverage_negative` 的 `schema_valid=1`，但 `actual_bridge_ready=0`；这证明 Stage127 的合同层能挡住“schema 格式正确但不是本 request/未覆盖本 request”的 proof。

## 视觉产物

- official path schema bridge status：`qmt_roll_stage127_c9_minrisk_wave0_proof_schema_preflight_bridge_official_path_schema_bridge_status_stage127_wave0_proof_schema_preflight_bridge_v1.png`
- request schema bridge matrix：`qmt_roll_stage127_c9_minrisk_wave0_proof_schema_preflight_bridge_request_schema_bridge_matrix_stage127_wave0_proof_schema_preflight_bridge_v1.png`
- integration selftest chart：`qmt_roll_stage127_c9_minrisk_wave0_proof_schema_preflight_bridge_integration_selftest_chart_stage127_wave0_proof_schema_preflight_bridge_v1.png`
- template schema block chart：`qmt_roll_stage127_c9_minrisk_wave0_proof_schema_preflight_bridge_template_schema_block_chart_stage127_wave0_proof_schema_preflight_bridge_v1.png`

视觉观察：

- official path schema bridge status 图保留资金、回撤和 broker10 曲线；所有 W0 request marker 为红色，表示没有 proof schema bridge ready，不是交易信号。
- request schema bridge matrix 全红，说明空 drop 下每个 request 都缺 proof，不能进入 schema/identity/span 通过状态。
- integration selftest chart 显示 5 个桥接自测全部 PASS，尤其证明 schema 可通过但 contract mismatch 仍会被阻断。
- template schema block chart 显示 41 个模板全部 blocked，且均含 placeholder，模板仍不能冒充真实 proof。

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage127_wave0_proof_schema_preflight_bridge/qmt_roll_stage127_c9_minrisk_wave0_proof_schema_preflight_bridge_report_stage127_wave0_proof_schema_preflight_bridge_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage127_wave0_proof_schema_preflight_bridge/qmt_roll_stage127_c9_minrisk_wave0_proof_schema_preflight_bridge_summary_stage127_wave0_proof_schema_preflight_bridge_v1.csv`
- request audit：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage127_wave0_proof_schema_preflight_bridge/qmt_roll_stage127_c9_minrisk_wave0_proof_schema_preflight_bridge_request_schema_bridge_audit_stage127_wave0_proof_schema_preflight_bridge_v1.csv`
- template audit：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage127_wave0_proof_schema_preflight_bridge/qmt_roll_stage127_c9_minrisk_wave0_proof_schema_preflight_bridge_template_schema_block_audit_stage127_wave0_proof_schema_preflight_bridge_v1.csv`
- integration selftest：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage127_wave0_proof_schema_preflight_bridge/qmt_roll_stage127_c9_minrisk_wave0_proof_schema_preflight_bridge_integration_selftest_stage127_wave0_proof_schema_preflight_bridge_v1.csv`
- gate status：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage127_wave0_proof_schema_preflight_bridge/qmt_roll_stage127_c9_minrisk_wave0_proof_schema_preflight_bridge_proof_schema_bridge_gate_status_stage127_wave0_proof_schema_preflight_bridge_v1.csv`

## 结论

Stage127 证明：Stage126 schema 已可作为 proof 第一层结构验证，但还必须叠加 Stage124 request 合同校验。桥接层已能挡住两类 schema 本身难以保证的风险：proof 属于错误 request，以及 proof 时间范围不足以覆盖 request 窗口。

当前真实状态仍是 `observed_proof_file_count=0`、`proof_schema_bridge_ready_count=0`、`ready_for_stage125=0`、`ready_for_stage123=0`、`real_w0_data_delivered=0`、`true_engine_allowed=0`、`strategy_feature_usable=0`。因此微观结构/分钟规则预检、true engine、A/B 和正式候选继续阻塞。

## 后续规划和 TODO

1. 真实 W0 drop 到货后，先运行 Stage127 schema bridge：`.py311/bin/python research/lines/futures_trend_c9_minrisk_highquality/tools/stage127_wave0_proof_schema_preflight_bridge.py --drop-dir <real_drop_dir> --case-id real_w0_proof_schema_bridge`
2. Stage127 只证明 proof schema/identity/span；仍必须继续运行 Stage125 receipt preflight 和 Stage123 全链路。
3. 后续可把 Stage127 输出作为 Stage125 的前置 overlay 或在 Stage123 checkpoint 前串联，但在真实 W0 到货前不改策略、不做微观结构候选。
4. 继续禁止用 synthetic、模板 proof、旧 OHLC、本地 Tq tick 或 smoke 数据构造分钟进出场规则。

## 结束反思

- 是否在过拟合：否。Stage127 没有引入任何收益或交易条件，只把 request 身份和时间覆盖这类普世数据合同固定为机器闸门；这是反数据污染，不是历史样本拟合。
- 是否还有价值继续：有。它补上了 Stage126 schema 与 Stage125 收货预检之间的合同断点，能减少真实 W0 到货后把错 request 或时间不足的 proof 送入 Stage123/112/113 的风险；但它本身不推进 alpha，真正策略研究仍等待授权 W0 数据通过硬闸门。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage127 schema bridge 状态。
- 是否更新 `research/registry.md`：否。本阶段不新增研究线。
- 是否追加根目录 `memory.md/back_log.md`：否。不是正式候选、重要突破或跨线合入。
