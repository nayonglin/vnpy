# Stage132 Stage131 fixture 防误用闸门审计

- line_id：futures_trend_c9_minrisk_highquality
- 当前模式：day
- 记录时间：2026-06-20 20:51 CST
- 工作区/分支：/Users/bytedance/Desktop/person/vnpy / master
- 阶段性质：数据来源/provenance 防误用审计；不做策略 alpha，不做 true engine，不做 A/B
- 是否重要突破：否；这是 Stage131 正向 fixture 后的必要边界加固
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - OpenLineage Dataset Facets：https://openlineage.io/docs/spec/facets/dataset-facets/
  - OpenLineage Object Model：https://openlineage.io/docs/spec/object-model/
  - DataHub Lineage：https://docs.datahub.com/docs/features/feature-guides/lineage
  - Great Expectations schema validation：https://docs.greatexpectations.io/docs/reference/learn/data_quality_use_cases/schema/
  - PyArrow Parquet：https://arrow.apache.org/docs/python/parquet.html
  - Apache Parquet metadata：https://parquet.apache.org/docs/file-format/metadata/
- 我的判断：权威数据接入不能只看 schema、字段、时间覆盖和文件可读性，还必须把来源血缘、manifest 元数据、文件路径和 proof 描述一起作为硬闸门。Stage131 的本地正向 fixture 能证明接收链路正确，但绝不能被 Stage112/113 当作真实 vendor W0；因此本阶段只做 provenance 防误用，不从 fixture 中提取任何交易信号。

## 本次变更

- 新增脚本：
  - `research/lines/futures_trend_c9_minrisk_highquality/tools/stage132_stage131_fixture_misuse_guard_audit.py`
- 修改脚本：
  - `research/lines/futures_trend_c9_minrisk_highquality/tools/stage112_authorized_microstructure_data_drop_validator.py`
  - `research/lines/futures_trend_c9_minrisk_highquality/tools/stage113_microstructure_required_window_coverage.py`
- 删除脚本：无
- 新增参数：
  - Stage112 增加本地 fixture 来源标记：`stage131`、`positive_drop`、`contract_positive`、`local_contract_positive`
  - Stage113 增加 `LOCAL_FIXTURE_MARKERS`
  - Stage132 增加 shadow manifest 伪投递审计，故意用授权样式字段指向 Stage131 positive fixture
- 修改参数：
  - Stage112 来源标记检测范围从旧 marker 扩展到 manifest path、data/raw path、schema、license、vendor、dataset_id、notes/comment/description、proof_file/proof_path 等字段
  - Stage113 在读 parquet 前先扫描 manifest/data/raw/dataset/vendor/notes/proof 中的 fixture 标记，命中即写入 `blocked_local_fixture_marker:*`
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用 Stage131 官方背景曲线 2018-2026；Stage132 本身不新增交易
- 账户规模：沿用当前 C9 min-risk 线背景口径
- 成本口径：沿用 Stage131 背景统计，总滑点 `2,730,130`
- 样本过滤：只审计 1 条 shadow manifest，指向 Stage131 本地 `contract_positive_fixture_drop`
- 策略/归因口径：防误用闸门；不允许进入策略层，不允许 minute signal research，不允许 true engine

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26,017.63%`
- 最大回撤：`-45.08%`
- Sharpe：`1.633`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：`36.09%`
- 其他关键指标：
  - decision：`stage132_stage131_fixture_blocked_from_stage112_113_no_strategy`
  - shadow_manifest_row_count：`1`
  - stage112_fixture_marker_blocked_count：`1`
  - stage112_basic_intake_pass_count：`0`
  - stage112_rule_ready_count：`0`
  - stage113_fixture_marker_blocked_count：`1`
  - stage113_indexed_file_count：`0`
  - stage113_coverage_gate_pass_count：`0`
  - expectation_pass_count：`7/7`
  - real_w0_data_delivered：`0`
  - real_stage112_intake_allowed_now：`0`
  - true_engine_allowed：`0`
  - strategy_feature_usable：`0`

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage132_stage131_fixture_misuse_guard_audit/qmt_roll_stage132_c9_minrisk_stage131_fixture_misuse_guard_audit_report_stage132_stage131_fixture_misuse_guard_audit_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage132_stage131_fixture_misuse_guard_audit/qmt_roll_stage132_c9_minrisk_stage131_fixture_misuse_guard_audit_summary_stage132_stage131_fixture_misuse_guard_audit_v1.csv`
- orders：无；本阶段不生成订单
- daily：无新增交易 daily；资金曲线沿用 Stage131 背景审计序列
- quality：
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage132_stage131_fixture_misuse_guard_audit/qmt_roll_stage132_c9_minrisk_stage131_fixture_misuse_guard_audit_misuse_expectation_audit_stage132_stage131_fixture_misuse_guard_audit_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage132_stage131_fixture_misuse_guard_audit/qmt_roll_stage132_c9_minrisk_stage131_fixture_misuse_guard_audit_stage112_shadow_file_audit_stage132_stage131_fixture_misuse_guard_audit_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage132_stage131_fixture_misuse_guard_audit/qmt_roll_stage132_c9_minrisk_stage131_fixture_misuse_guard_audit_stage113_shadow_file_index_stage132_stage131_fixture_misuse_guard_audit_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage132_stage131_fixture_misuse_guard_audit/qmt_roll_stage132_c9_minrisk_stage131_fixture_misuse_guard_audit_official_path_fixture_block_status_stage132_stage131_fixture_misuse_guard_audit_v1.png`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage132_stage131_fixture_misuse_guard_audit/qmt_roll_stage132_c9_minrisk_stage131_fixture_misuse_guard_audit_misuse_guard_matrix_stage132_stage131_fixture_misuse_guard_audit_v1.png`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage132_stage131_fixture_misuse_guard_audit/qmt_roll_stage132_c9_minrisk_stage131_fixture_misuse_guard_audit_fixture_boundary_chart_stage132_stage131_fixture_misuse_guard_audit_v1.png`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage132_stage131_fixture_misuse_guard_audit/qmt_roll_stage132_c9_minrisk_stage131_fixture_misuse_guard_audit_shadow_intake_gate_chart_stage132_stage131_fixture_misuse_guard_audit_v1.png`

## 视觉检查

- 官方路径图：资金、回撤、broker10 曲线非空，红点只标记被封堵的 Stage131 fixture 请求位置；没有把 fixture 画成可交易收益来源。
- 预期矩阵：`7/7` 全绿，说明 fixture marker、Stage112 阻断、Stage113 阻断、固定根目录边界都按预期工作。
- 边界图：Stage131 parquet/raw 均在授权 intake 固定根目录之外；Stage112/Stage113 marker guard 均包含 `stage131`。
- shadow intake 图：shadow root 和 manifest 存在为绿，但从 raw/schema/source/coverage 到 Stage113 downstream gate 全红，说明伪装投递被切断在策略层之前。

## 结论

- 本阶段结论：Stage131 的本地正向 fixture 即便通过 shadow manifest 伪装成授权数据，也会被 Stage112 和 Stage113 双重阻断；不会进入覆盖索引、不会进入策略特征、不会触发 true engine。
- 是否进入下一步：是，但只能继续数据接入防线或等待真实 W0 drop；不能用 Stage131 fixture 做任何分钟信号研究。
- 下一步：优先做真实 W0 到货后的只读流程准备：Stage128 supergate -> Stage112 -> Stage113 的 provenance/coverage 总闸门一键化；如真实 W0 仍未到货，则继续做防误用负例，不做交易规则。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段没有调交易参数、没有根据收益曲线挑规则、没有从 Stage131 fixture 归纳信号，只是在数据血缘边界上增加普世约束。来源标记、路径根目录、manifest/proof 元数据审计是跨周期、跨品种都成立的工程约束，不是样本内收益拟合。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值。
- 原因：Stage131 让正向接收链路可通过，但也带来“本地正例被误当真实数据”的风险；Stage132 证明这条风险路径已经被阻断。继续价值在于让真实 W0 到货前后的所有后续研究都可审计、可复验，不会因 fixture 泄漏污染策略结论。

## 合入建议

- 是否更新本线 `LINE.md`：是
- 是否更新 `research/registry.md`：否；这不是新增研究线或跨线合入
- 是否追加根目录 `memory.md/back_log.md`：否；这不是正式候选、重大突破或跨线合并
