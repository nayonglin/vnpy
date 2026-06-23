# Stage130 W0 raw/parquet/checksum failure-mode audit

## 基本信息

- 时间：2026-06-20 20:23
- 工作模式：day
- 研究线：`futures_trend_c9_minrisk_highquality`
- 工作区：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：W0 文件级坏交付审计；在 Stage129 proof-only 负例之后，继续验证 raw、Parquet、SHA256SUMS、Stage117、Stage120 与 Stage128 full supergate 的联合阻断能力。只做本地验收和视觉 QA，不写真引擎、不新增交易规则、不触发 A/B、不改正式配置、不连接 CTP、不调用订单 API、不下载外部数据。
- 决策：`stage130_raw_parquet_checksum_failure_modes_blocked_no_strategy`
- 重要突破版本：否。它是数据入口 hard gate 的防错补强，不是 alpha 或正式候选。
- 是否触发 A/B：否。没有策略候选。

## 开始前反思

- 是否在过拟合：否。本阶段没有收益标签、交易阈值、品种/年份/方向筛选；所有规则都是普世数据完整性规则：raw checksum、唯一角色、Parquet 可读、必要字段、物理行数和 canonical schema。
- 是否还有价值继续：是。Stage129 证明 proof-only 错误不会放行，但真实供应交付更可能出现 checksum 错、raw 重复、Parquet 可读但 schema 不对、Parquet 0 行等问题。Stage130 覆盖这些更底层的坏数据形态。

## 外部调研与判断

- Apache Parquet 官方文档说明 Parquet 是列式文件格式，并把 metadata/schema 与数据分开存储。判断：验收不能只看 `.parquet` 文件存在，必须读 metadata、schema 和行数。
- Apache Arrow/PyArrow 文档说明 `pyarrow.parquet.write_table` 会把 Arrow schema 写入 Parquet metadata。判断：Stage130 用 PyArrow 构造 schema-complete、schema-gap、invalid bytes、zero-row 等可复验负例。
- Python `hashlib` 官方文档提供 SHA256 等安全哈希算法。判断：raw 完整性必须是字节级 digest 校验，不能靠文件名或 proof 自报。
- Apache Arrow GitHub 官方代码示例里 `pq.write_table(...)` 与 `ParquetFile(...)` 是标准读写/读取路径。判断：本阶段采用官方库生成和读取 Parquet，不用字符串伪造 schema。

调研结论：W0 文件验收要把 checksum、Parquet metadata/schema、物理行数和 request proof 串起来；schema valid 或文件存在都不是充分条件。

参考链接：

- https://parquet.apache.org/docs/file-format/
- https://arrow.apache.org/docs/python/generated/pyarrow.parquet.write_table.html
- https://docs.python.org/3/library/hashlib.html
- https://github.com/apache/arrow/blob/master/python/pyarrow/parquet/core.py

## 本阶段改动

- 修改工具：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage117_wave0_delivery_verifier.py`
  - 新增 `parquet_row_count_positive` hard gate。
  - `hard_accept` 现在要求 Parquet metadata `num_rows > 0`，防止 proof 自报 `row_count>0` 但 Parquet 物理 0 行。
  - 输出 summary 新增 `parquet_row_count_positive_count`。
- 修改工具：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage128_wave0_full_intake_supergate.py`
  - request audit 新增 `stage127_125_request_ready`。
  - `full_supergate_request_ready` 现在同时要求 Stage123 ready，不再只表示 Stage127+Stage125。
  - 这修正了 request-level 图表命名误导；case-level final gate 原本就是正确的。
- 新增工具：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage130_wave0_raw_parquet_checksum_failure_mode_audit.py`
  - 读取 Stage124 交付契约、Stage120 canonical schema contract。
  - 构造 `6` 类 full-shape bad drop，共 `785` 个本地负例文件。
  - 每个 bad drop 逐一运行 Stage128 CLI，并捕获 Stage128 case/request/gate 与 Stage123 gate detail。
  - 最后恢复 Stage128 默认负例输出。

构造的 6 类负例：

| failure case | 构造方式 | 预期阻断点 |
| --- | --- | --- |
| `checksum_digest_mismatch_drop` | raw/parquet/proof 完整，但 SHA256SUMS digest 全错 | Stage125/full supergate 阻断 |
| `duplicate_raw_role_drop` | 每个 request 有两个 raw 文件 | Stage125/full supergate 阻断 |
| `invalid_parquet_bytes_drop` | `.parquet` 文件存在但不是 Parquet | Stage117/120/123 阻断 |
| `parquet_missing_universal_fields_drop` | Parquet 可读但缺 `ts_event/ts_recv` | Stage117/120/123 阻断 |
| `parquet_missing_canonical_depth_fields_drop` | Parquet 有 `ts_event/ts_recv/sequence`，但缺 MBP/MBO hard fields | Stage120/123 阻断 |
| `zero_row_schema_complete_drop` | Parquet schema 完整但物理 0 行，proof 自报 row_count>0 | Stage117 新 row-count gate 阻断 |

## 参数与结果变更

- 新增参数：
  - `failure_case_count=6`
  - `generated_bad_drop_file_count=785`
  - `stage117_parquet_row_count_gate_added=1`
  - `stage128_cli_run_count=6`
  - `stage128_returncode_zero=1`
  - `stage128_all_inner_commands_returncode_zero=1`
  - `stage128_default_restored=1`
  - `blocked_case_count=6`
  - `unexpected_pass_count=0`
  - `expectation_matched_count=6/6`
  - `full_supergate_ready_count=0`
  - `strategy_allowed_count=0`
  - `stage125_ready_case_count=4`
  - `stage117_ready_case_count=3`
  - `stage120_ready_case_count=3`
  - `stage123_ready_case_count=2`
- 修改参数：无交易参数修改。
- 删除参数：无。
- 新增回测结果：无真实回测；复用当前官方路径资金曲线做文件级 gate 视觉背景。
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

| failure case | Stage125 ready | Stage117 intake | Stage120 schema pass | Stage123 final ready | full supergate | unexpected pass |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| checksum_digest_mismatch_drop | 0 | 1 | 1 | 1 | 0 | 0 |
| duplicate_raw_role_drop | 0 | 1 | 1 | 1 | 0 | 0 |
| invalid_parquet_bytes_drop | 1 | 0 | 0 | 0 | 0 | 0 |
| parquet_missing_universal_fields_drop | 1 | 0 | 0 | 0 | 0 | 0 |
| parquet_missing_canonical_depth_fields_drop | 1 | 1 | 0 | 0 | 0 | 0 |
| zero_row_schema_complete_drop | 1 | 0 | 1 | 0 | 0 | 0 |

解释：

- `checksum_digest_mismatch_drop` 与 `duplicate_raw_role_drop` 即使 Stage117、Stage120、Stage123 可 ready，也被 Stage125/full supergate 拦住，证明 Stage128 的 receipt preflight 是必要层。
- `invalid_parquet_bytes_drop` 和 `parquet_missing_universal_fields_drop` 被 Stage117 内容层阻断，证明文件存在不等于可用数据。
- `parquet_missing_canonical_depth_fields_drop` 能过 Stage117 的基础时间字段检查，但被 Stage120 canonical schema 拦住，证明 Stage120 是必要层。
- `zero_row_schema_complete_drop` 能过 Stage120 schema，但被 Stage117 新增 `parquet_row_count_positive` 拦住，补上了“schema 完整但无物理数据”的漏洞。
- request-level 审计显示：`invalid_parquet_bytes_drop`、`parquet_missing_*`、`zero_row_schema_complete_drop` 的 `stage127_125_request_ready=41/41`，但修正后的 `full_supergate_request_ready=0/41`，与 case-level full supergate 一致。

## 视觉产物

- official path raw/parquet failure status：`qmt_roll_stage130_c9_minrisk_wave0_raw_parquet_checksum_failure_mode_audit_official_path_raw_parquet_failure_status_stage130_wave0_raw_parquet_checksum_failure_mode_audit_v1.png`
- raw/parquet supergate matrix：`qmt_roll_stage130_c9_minrisk_wave0_raw_parquet_checksum_failure_mode_audit_raw_parquet_supergate_matrix_stage130_wave0_raw_parquet_checksum_failure_mode_audit_v1.png`
- expected vs observed raw/parquet failures：`qmt_roll_stage130_c9_minrisk_wave0_raw_parquet_checksum_failure_mode_audit_expected_vs_observed_raw_parquet_failures_stage130_wave0_raw_parquet_checksum_failure_mode_audit_v1.png`
- request receipt failure matrix：`qmt_roll_stage130_c9_minrisk_wave0_raw_parquet_checksum_failure_mode_audit_request_receipt_failure_matrix_stage130_wave0_raw_parquet_checksum_failure_mode_audit_v1.png`

视觉观察：

- official path 图保留资金、回撤和 broker10 曲线；bad-drop marker 只表示验收窗口，不是交易信号。
- case matrix 显示 6 个 case 的 `actual_full_supergate_ready`、`actual_strategy_use_allowed_now`、`unexpected_pass` 全部为 0。
- expected vs observed 图中每个 case 的预期和观测完全一致，`expectation_matched_count=6/6`。
- request matrix 在修正 Stage128 后，`stage127_125_request_ready` 与 `full_supergate_request_ready` 分离；所有 case 的真正 full supergate request readiness 全红。

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage130_wave0_raw_parquet_checksum_failure_mode_audit/qmt_roll_stage130_c9_minrisk_wave0_raw_parquet_checksum_failure_mode_audit_report_stage130_wave0_raw_parquet_checksum_failure_mode_audit_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage130_wave0_raw_parquet_checksum_failure_mode_audit/qmt_roll_stage130_c9_minrisk_wave0_raw_parquet_checksum_failure_mode_audit_summary_stage130_wave0_raw_parquet_checksum_failure_mode_audit_v1.csv`
- failure expectation：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage130_wave0_raw_parquet_checksum_failure_mode_audit/qmt_roll_stage130_c9_minrisk_wave0_raw_parquet_checksum_failure_mode_audit_failure_expectation_audit_stage130_wave0_raw_parquet_checksum_failure_mode_audit_v1.csv`
- case summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage130_wave0_raw_parquet_checksum_failure_mode_audit/qmt_roll_stage130_c9_minrisk_wave0_raw_parquet_checksum_failure_mode_audit_failure_case_summary_stage130_wave0_raw_parquet_checksum_failure_mode_audit_v1.csv`
- request audit：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage130_wave0_raw_parquet_checksum_failure_mode_audit/qmt_roll_stage130_c9_minrisk_wave0_raw_parquet_checksum_failure_mode_audit_failure_request_audit_stage130_wave0_raw_parquet_checksum_failure_mode_audit_v1.csv`
- Stage123 gate detail：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage130_wave0_raw_parquet_checksum_failure_mode_audit/qmt_roll_stage130_c9_minrisk_wave0_raw_parquet_checksum_failure_mode_audit_stage123_gate_detail_stage130_wave0_raw_parquet_checksum_failure_mode_audit_v1.csv`
- inventory：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage130_wave0_raw_parquet_checksum_failure_mode_audit/qmt_roll_stage130_c9_minrisk_wave0_raw_parquet_checksum_failure_mode_audit_bad_drop_file_inventory_stage130_wave0_raw_parquet_checksum_failure_mode_audit_v1.csv`

## 结论

Stage130 证明：Stage128 full supergate 能拦住 raw/parquet/checksum 层面的非空坏交付；同时补上了 Stage117 对 Parquet 物理 0 行的 hard gate，并修正了 Stage128 request-level full-supergate 命名语义。

当前真实状态仍是 `full_supergate_ready_count=0`、`real_w0_data_delivered=0`、`real_stage112_intake_allowed_now=0`、`true_engine_allowed=0`、`strategy_feature_usable=0`。因此 Stage112/113、微观结构/分钟规则预检、true engine、A/B 和正式候选继续阻塞。

## 后续规划和 TODO

1. 真实 W0 到货后，继续只跑 Stage128 CLI；若失败，用 Stage129/130 failure atlas 定位 proof、checksum、duplicate role、Parquet readability、universal fields、canonical fields 或 zero-row 问题。
2. 下一阶段若仍无真实 W0，可做 Stage131：把 Stage124/126/129/130 的 failure atlas 汇总成供应商回执验收 checklist 和自动报告，减少真实交付后的人工沟通成本。
3. 若出现真实 W0 文件，不得跳过 Stage128/112/113 直接进入微观结构规则。
4. 没有真实 W0 通过 Stage128/112/113 前，不从本地旧 OHLC、synthetic、Tq smoke 或模板 proof 构造任何分钟进出场规则。

## 结束反思

- 是否在过拟合：否。Stage130 只增加数据物理完整性和验收链路一致性，没有收益优化或交易阈值。
- 是否还有价值继续：有。它把真实供应交付中最常见的文件级风险纳入自动阻断，避免后续把坏数据误当高质量信号；但它本身不推进 alpha，真正策略研究仍等待授权 W0 通过 Stage128/112/113。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage130 raw/parquet/checksum failure-mode audit 状态。
- 是否更新 `research/registry.md`：否。本阶段不新增研究线。
- 是否追加根目录 `memory.md/back_log.md`：否。不是正式候选、重要突破或跨线合入。
