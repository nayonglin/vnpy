# Stage155 权威分钟 OHLCV 交付负例审计

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：2026-06-21 00:13 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：负例审计 / 数据闸门防误用 / 非规则候选
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - JSON Schema docs：https://json-schema.org/docs
  - Apache Parquet metadata：https://parquet.apache.org/docs/file-format/metadata/
  - NIST FIPS 180-4 SHA-256：https://csrc.nist.gov/pubs/fips/180-4/upd1/final
- 我的判断：JSON Schema 只能证明结构，不等于证明数据真实；Parquet metadata 可读和 row count 可作为验收输入，但可读零行仍不可研究；SHA-256 能证明文件未被改动，但不能替代 vendor provenance、license、session calendar 和 no-trade policy。因此 Stage155 必须构造“看起来有文件”的负例，确认 Stage153 不会被模板、proof-only、错 hash、坏 parquet、零行 parquet 或本地伪正例绕过。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage155_authoritative_minute_ohlcv_delivery_failure_modes.py`
- 修改脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage153_authoritative_minute_ohlcv_intake_validator.py`
- 删除脚本：无
- 新增参数：无
- 修改参数：Stage153/Stage155 的 forbidden marker scanner 从“扫描 JSON key+value”改为“只扫描字符串 value 和路径”，避免把合法字段名 `synthetic_or_adjusted_flag` 中的 `synthetic` 误判为禁用 provenance marker。
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用 Stage152 request manifest、Stage153 intake summary 与 Stage154 proof schema/templates；本阶段不新增策略回测。
- 账户规模：沿用本线 C9 minrisk 研究口径。
- 成本口径：沿用输入账本，`total_slippage=2,730,130`
- 样本过滤：构造隔离负例，不写真实 `incoming/`；负例目录为本线输出下的 `negative_drops/`。
- 策略/归因口径：数据闸门负例审计，不创建规则，不运行 true engine，不触发 A/B，不连接 CTP，不调用订单 API。

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：`36.0902%`
- 其他关键指标：
  - decision：`stage155_authoritative_minute_ohlcv_negative_delivery_shapes_blocked_no_rule`
  - next_best_action：`deliver_real_authoritative_minute_ohlcv_package_or_build_stage156_operator_release_verdict`
  - case_count：`6`
  - request_case_audit_count：`1,166`
  - case_expectation_pass_count：`6/6`
  - unexpected_ready_count：`0`
  - strategy_rule_allowed_count：`0`
  - proof_schema_valid_request_count：`933`
  - normalized_schema_pass_request_count：`1`
  - forbidden_marker_request_count：`234`
  - negative_drop_written_under_incoming：`0`
  - stage153_request_ready_count：`0`
  - stage153_feature_build_allowed：`0`
  - current_package_promotion_allowed：`0`
  - true_engine_allowed：`0`
  - strategy_feature_usable：`0`
  - side_effect_count：`0`

## 负例覆盖

- `template_proof_only_all_requests`：把 Stage154 模板当 proof 交付，无 raw/parquet，`233/233` 被阻断。
- `schema_valid_proof_only_no_files`：proof schema 有效但无 raw/parquet，`233/233` 被阻断。
- `raw_present_hash_mismatch`：有 raw 和 proof，但 raw_sha256 错，`233/233` 被阻断。
- `raw_hash_match_invalid_parquet`：raw hash 匹配，但 normalized 是坏 parquet 字节，`233/233` 被阻断。
- `raw_hash_match_zero_row_parquet`：raw hash 匹配，parquet 可读但零行，`233/233` 被阻断。
- `local_positive_shape_forbidden_marker`：1 个本地伪正例 raw/proof/一行 parquet 都齐，但 provenance 含 `fixture`，`1/1` 被阻断。

## 视觉观察

- official path failure mode status 图显示资金/回撤/broker10 仍为基准底图；下方状态条里 `unexpected_ready=0`、`expect_pass=6`、`rule=0`、`engine=0`。
- case blocked bar 显示所有负例请求均被阻断，没有出现意外 ready。
- role presence heatmap 显示即使 raw/proof/parquet 三件套看似存在，也会被 hash、parquet row count 或 provenance marker 拦住。
- failure reason heatmap 显示不同负例由不同硬门槛拦截，避免单一条件假通过。

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage155_authoritative_minute_ohlcv_delivery_failure_modes/qmt_roll_stage155_c9_minrisk_authoritative_minute_ohlcv_delivery_failure_modes_report_stage155_authoritative_minute_ohlcv_delivery_failure_modes_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage155_authoritative_minute_ohlcv_delivery_failure_modes/qmt_roll_stage155_c9_minrisk_authoritative_minute_ohlcv_delivery_failure_modes_summary_stage155_authoritative_minute_ohlcv_delivery_failure_modes_v1.csv`
- orders：无
- daily：无新增 daily 账本
- quality：
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage155_authoritative_minute_ohlcv_delivery_failure_modes/qmt_roll_stage155_c9_minrisk_authoritative_minute_ohlcv_delivery_failure_modes_case_summary_stage155_authoritative_minute_ohlcv_delivery_failure_modes_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage155_authoritative_minute_ohlcv_delivery_failure_modes/qmt_roll_stage155_c9_minrisk_authoritative_minute_ohlcv_delivery_failure_modes_request_case_audit_stage155_authoritative_minute_ohlcv_delivery_failure_modes_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage155_authoritative_minute_ohlcv_delivery_failure_modes/qmt_roll_stage155_c9_minrisk_authoritative_minute_ohlcv_delivery_failure_modes_failure_reason_matrix_stage155_authoritative_minute_ohlcv_delivery_failure_modes_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage155_authoritative_minute_ohlcv_delivery_failure_modes/qmt_roll_stage155_c9_minrisk_authoritative_minute_ohlcv_delivery_failure_modes_gate_status_stage155_authoritative_minute_ohlcv_delivery_failure_modes_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage155_authoritative_minute_ohlcv_delivery_failure_modes/negative_drops/`
  - 5 张视觉图：official path failure mode status、case blocked bar、case role presence heatmap、failure reason heatmap、gate status matrix。

## 结论

- 本阶段结论：Stage155 证明 Stage153/154 的数据入口不会被模板、schema-valid proof-only、hash mismatch、坏 parquet、零行 parquet 或本地伪正例绕过。修复后的 marker scanner 不再误伤合法字段名，但仍能拦截模板占位符和本地 fixture provenance。
- 是否进入下一步：否，除非真实授权数据到货；或者继续做 Stage156 operator release verdict，把 Stage153/154/155 串成一个到货后总闸门。
- 下一步：优先等待真实 raw/proof/normalized package；若继续基础设施，则做 Stage156 一键 release verdict，不进入分钟特征构建、true engine、A/B 或正式候选。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段全是数据交付负例，不读取收益结果做阈值，不筛年份/品种/方向，不生成交易特征；其作用是减少未来数据入口的人工自由度。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值。
- 原因：Stage155 补上了“坏交付也不能推动研究”的机械证据，尤其修复了 marker scanner 的误伤风险；这能避免真实到货前或半成品到货时误入策略研究。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：否。
