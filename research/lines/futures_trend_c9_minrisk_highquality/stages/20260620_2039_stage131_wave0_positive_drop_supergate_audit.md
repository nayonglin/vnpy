# Stage131 W0 正向交付 supergate 验收审计

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：2026-06-20 20:39 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：W0 数据交付链路正向验收；不是策略规则、不是 true engine、不是 A/B。
- 是否重要突破：策略层不是；数据验收链路是关键正例突破。
- 是否触发A/B：否。

## 外部调研与判断

- 参考资料：
  - Apache Parquet Concepts：https://parquet.apache.org/docs/concepts/
  - Apache Parquet Metadata：https://parquet.apache.org/docs/file-format/metadata/
  - PyArrow `read_table`：https://arrow.apache.org/docs/python/generated/pyarrow.parquet.read_table.html
  - PyArrow Parquet guide：https://arrow.apache.org/docs/python/parquet.html
  - Great Expectations schema validation：https://docs.greatexpectations.io/docs/reference/learn/data_quality_use_cases/schema/
  - Pandera DataFrame schema：https://pandera.readthedocs.io/en/latest/dataframe_schemas.html
- 我的判断：
  - Stage129/130 已证明坏 drop 会被拒绝，但还缺一个正向 happy-path 证据来证明 gate 不是“只会拒绝不会接收”。
  - Parquet footer/schema/row group metadata、PyArrow 读取行数与 schema、数据质量框架的 schema/row-count/字段契约思想，都支持把正向验收做成可复验管道合同。
  - 本阶段只能证明接收链路可全绿；本地构造 fixture 不能被当成真实 vendor W0 行情，更不能进入策略规则或收益归因。

## 本次变更

- 新增脚本：
  - `research/lines/futures_trend_c9_minrisk_highquality/tools/stage131_wave0_positive_drop_supergate_audit.py`
- 修改脚本：
  - `research/lines/futures_trend_c9_minrisk_highquality/tools/stage123_wave0_intake_chain_checkpoint.py`
    - 修正 CLI 正向 drop 的最终期望：非 synthetic 且调用方 `--expected-stage112-intake 1` 时，`final_stage112_ready` 允许期望为 `1`。
    - synthetic case 仍强制最终期望 `0`，保持反挑样本不能 final accept。
- 删除脚本：无。
- 新增参数：
  - Stage131 固定 `positive_case_id=contract_positive_fixture_drop`。
  - 每个 request 写入 `2` 行 schema-complete normalized Parquet。
  - Stage128 CLI 固定用 `--expected-stage112-intake 1` 验证正向路径。
- 修改参数：
  - Stage123 的 `final_stage112_ready` gate 从写死 `0` 改为按 `expected_stage112` 与 `synthetic_case` 共同决定。
- 删除参数：无。

## 回测/归因参数

- 数据区间：沿用官方 C9 曲线路径；W0 request 覆盖 Stage124 的 `41` 个 W0 request。
- 账户规模：沿用当前 C9/15w 官方曲线口径。
- 成本口径：沿用官方曲线既有成本口径；本阶段不跑 true engine。
- 样本过滤：不按盈亏、年份、品种、方向过滤；正向 fixture 对全部 `41/41` request 等量生成 raw/parquet/proof。
- 策略/归因口径：只验收 Stage127 -> Stage125 -> Stage123 -> Stage128 supergate；`strategy_use_allowed_now` 必须保持 `0`。

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：`36.0902%`
- 其他关键指标：
  - `generated_positive_file_count=124`，其中 raw `41`、normalized Parquet `41`、proof `41`、SHA256SUMS `1`。
  - `positive_request_ready_count=41/41`
  - `positive_full_supergate_ready_count=1`
  - `expectation_matched_count=1/1`
  - `stage128_returncode_zero=1`
  - `stage128_all_inner_commands_returncode_zero=1`
  - `stage128_positive_decision=stage128_full_intake_supergate_ready_for_stage112_no_strategy`
  - `strategy_allowed_count=0`
  - `real_w0_data_delivered=0`
  - `real_stage112_intake_allowed_now=0`
  - `stage128_default_restored=1`

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage131_wave0_positive_drop_supergate_audit/qmt_roll_stage131_c9_minrisk_wave0_positive_drop_supergate_audit_report_stage131_wave0_positive_drop_supergate_audit_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage131_wave0_positive_drop_supergate_audit/qmt_roll_stage131_c9_minrisk_wave0_positive_drop_supergate_audit_summary_stage131_wave0_positive_drop_supergate_audit_v1.csv`
- expectation：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage131_wave0_positive_drop_supergate_audit/qmt_roll_stage131_c9_minrisk_wave0_positive_drop_supergate_audit_positive_expectation_audit_stage131_wave0_positive_drop_supergate_audit_v1.csv`
- request audit：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage131_wave0_positive_drop_supergate_audit/qmt_roll_stage131_c9_minrisk_wave0_positive_drop_supergate_audit_positive_request_audit_stage131_wave0_positive_drop_supergate_audit_v1.csv`
- gate status：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage131_wave0_positive_drop_supergate_audit/qmt_roll_stage131_c9_minrisk_wave0_positive_drop_supergate_audit_positive_gate_status_stage131_wave0_positive_drop_supergate_audit_v1.csv`
- inventory：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage131_wave0_positive_drop_supergate_audit/qmt_roll_stage131_c9_minrisk_wave0_positive_drop_supergate_audit_positive_drop_file_inventory_stage131_wave0_positive_drop_supergate_audit_v1.csv`
- 资金曲线/视觉图：
  - `qmt_roll_stage131_c9_minrisk_wave0_positive_drop_supergate_audit_official_path_positive_supergate_stage131_wave0_positive_drop_supergate_audit_v1.png`
  - `qmt_roll_stage131_c9_minrisk_wave0_positive_drop_supergate_audit_positive_request_supergate_matrix_stage131_wave0_positive_drop_supergate_audit_v1.png`
  - `qmt_roll_stage131_c9_minrisk_wave0_positive_drop_supergate_audit_positive_gate_matrix_stage131_wave0_positive_drop_supergate_audit_v1.png`
  - `qmt_roll_stage131_c9_minrisk_wave0_positive_drop_supergate_audit_positive_inventory_burden_stage131_wave0_positive_drop_supergate_audit_v1.png`

## 视觉观察

- 官方路径图：绿色 W0 ready 点分布在官方权益、回撤、broker10 路径上；底部 bar 显示 `stage127_bridge_ready_count=41`、Stage125/Stage123/final supergate 均通过，但 `strategy_use_allowed_now=0`。
- request 矩阵：`proof_schema_bridge_ready`、`role_complete`、`checksum_match`、`proof_required_fields_present`、`preflight_request_ready`、`stage127_125_request_ready`、`full_supergate_request_ready` 全部为绿；唯一红列是策略锁，符合预期。
- gate 矩阵：Stage128 与 Stage123 chain gate 全绿，说明 Stage123 正向期望修正后不会把真实/正向 drop 误标为失败。
- inventory 图：文件数为 raw/parquet/proof 各 `41`，checksum manifest `1`；Parquet 字节量最大，符合 schema-complete fixture 的文件结构。

## 结论

- 本阶段结论：
  - Stage128 full supergate 已具备正向接收能力：一个 request-id keyed、raw/parquet/proof/SHA256SUMS 完整、schema-complete、row_count>0、span 覆盖完整、checksum 正确、非 synthetic/smoke 污染的 W0 drop 可以达到 `41/41` request ready 和 `final_supergate_ready=1`。
  - 策略权限仍被锁死：`strategy_allowed_count=0`、`strategy_feature_usable=0`。
  - 这不是实盘/真实 W0 数据到货，Stage131 summary 明确 `real_w0_data_delivered=0`，后续不能拿该 fixture 做信号、PnL、规则或 A/B。
- 是否进入下一步：是，进入真实 W0 交付前的“防误用与 Stage112/113 衔接”检查。
- 下一步：
  - Stage132 优先做 positive fixture 防误用审计：确认 `contract_positive_fixture`、本地构造路径、fixture dataset 不会被 Stage112/113 或后续策略脚本当成真实 vendor 数据。
  - 或者若真实 W0 到货，直接用同一入口替换 drop：`stage128_wave0_full_intake_supergate.py --drop-dir <real_drop_dir> --expected-stage112-intake 1`，并继续 Stage112/113。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：
  - 本阶段没有新增交易规则、没有收益优化、没有按亏损窗口反推阈值，只验证数据合同的正向可接收性。
  - 正向 fixture 覆盖全部 `41/41` W0 request，没有按产品、年份、方向、盈亏切片。
  - 关键约束是普世数据工程合同：raw hash、Parquet schema/row count、proof identity/span、checksum、anti-selection lock。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值。
- 原因：
  - Stage129/130 证明坏数据会被挡住，Stage131 补上好数据能通过的证据，形成完整验收闭环。
  - 没有正向闭环时，真实 W0 到货后无法区分“数据坏”与“gate 写死不接收”；现在可以用同一入口做真实 drop 验收。
  - 对最终目标仍有价值，因为分钟级高质量信号必须建立在可信同源微观数据之上；否则低回撤规则只是历史闭合交易里的事后切片。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage131 摘要。
- 是否更新 `research/registry.md`：否，未进入正式候选、未跨线合并。
- 是否追加根目录 `memory.md/back_log.md`：否，不是策略突破或正式候选；只保留在线内记录。
