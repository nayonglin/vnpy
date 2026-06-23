# Stage133 W0 总接入下游闸门审计

- line_id：futures_trend_c9_minrisk_highquality
- 当前模式：day
- 记录时间：2026-06-20 21:05 CST
- 工作区/分支：/Users/bytedance/Desktop/person/vnpy / master
- 阶段性质：Stage128 -> Stage112 -> Stage113 总闸门/防误用审计；不做策略 alpha，不做 true engine，不做 A/B
- 是否重要突破：否；这是 Stage132 后的流程闭环加固
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - Great Expectations Checkpoints：https://docs.greatexpectations.io/docs/0.18/oss/guides/validation/validate_data_overview
  - OpenLineage Dataset Facets：https://openlineage.io/docs/spec/facets/dataset-facets/
  - OpenLineage Object Model：https://openlineage.io/docs/spec/object-model/
  - OpenLineage GitHub spec：https://github.com/OpenLineage/OpenLineage/blob/main/spec/OpenLineage.md
  - Dagster Asset Checks：https://docs.dagster.io/guides/test/asset-checks
  - Data Provenance Initiative GitHub：https://github.com/Data-Provenance-Initiative/Data-Provenance-Collection
- 我的判断：数据质量检查必须作为下游资产/策略前的阻断条件，而不是事后报表。Stage128 证明接收链路是否结构完整，但它不负责判定“是否真实授权来源、是否可进入分钟信号研究”；因此真实释放必须继续通过 Stage112/113 的 provenance 与 coverage gate。

## 本次变更

- 新增脚本：
  - `research/lines/futures_trend_c9_minrisk_highquality/tools/stage133_wave0_total_intake_downstream_gate_audit.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - 默认审计 case：`empty_drop_total_gate`
  - 默认审计 case：`stage131_positive_fixture_total_gate`
  - shadow intake root：`outputs/stage133_wave0_total_intake_downstream_gate_audit/shadow_authorized_microstructure_intake_cases/`
  - Stage128 默认恢复检查：`stage128_default_restored`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用 Stage131/Stage045 官方背景曲线 2018-2026；Stage133 本身不新增交易
- 账户规模：沿用当前 C9 min-risk 线背景口径
- 成本口径：沿用 Stage131 背景统计，总滑点 `2,730,130`
- 样本过滤：`empty_drop` 与 Stage131 `contract_positive_fixture_drop`
- 策略/归因口径：总闸门审计；Stage128 ready 之后仍必须过 Stage112/113，非真实授权数据一律不能 release 到分钟规则

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26,017.63%`
- 最大回撤：`-45.08%`
- Sharpe：`1.633`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：`36.09%`
- 其他关键指标：
  - decision：`stage133_total_intake_downstream_gate_blocks_non_real_data_no_strategy`
  - case_count：`2`
  - stage128_ready_case_count：`1`
  - stage112_checked_case_count：`1`
  - stage112_fixture_marker_count：`41`
  - stage112_rule_ready_count：`0`
  - stage113_fixture_marker_count：`41`
  - stage113_indexed_file_count：`0`
  - downstream_release_allowed_count：`0`
  - expectation_pass_count：`9/9`
  - stage128_default_restored：`1`
  - real_w0_data_delivered：`0`
  - real_stage112_intake_allowed_now：`0`
  - true_engine_allowed：`0`
  - strategy_feature_usable：`0`

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage133_wave0_total_intake_downstream_gate_audit/qmt_roll_stage133_c9_minrisk_wave0_total_intake_downstream_gate_audit_report_stage133_wave0_total_intake_downstream_gate_audit_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage133_wave0_total_intake_downstream_gate_audit/qmt_roll_stage133_c9_minrisk_wave0_total_intake_downstream_gate_audit_summary_stage133_wave0_total_intake_downstream_gate_audit_v1.csv`
- orders：无；本阶段不生成订单
- daily：无新增交易 daily；资金曲线沿用背景审计序列
- quality：
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage133_wave0_total_intake_downstream_gate_audit/qmt_roll_stage133_c9_minrisk_wave0_total_intake_downstream_gate_audit_case_downstream_audit_stage133_wave0_total_intake_downstream_gate_audit_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage133_wave0_total_intake_downstream_gate_audit/qmt_roll_stage133_c9_minrisk_wave0_total_intake_downstream_gate_audit_expectation_audit_stage133_wave0_total_intake_downstream_gate_audit_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage133_wave0_total_intake_downstream_gate_audit/qmt_roll_stage133_c9_minrisk_wave0_total_intake_downstream_gate_audit_stage112_shadow_file_audit_stage133_wave0_total_intake_downstream_gate_audit_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage133_wave0_total_intake_downstream_gate_audit/qmt_roll_stage133_c9_minrisk_wave0_total_intake_downstream_gate_audit_stage113_shadow_file_index_stage133_wave0_total_intake_downstream_gate_audit_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage133_wave0_total_intake_downstream_gate_audit/qmt_roll_stage133_c9_minrisk_wave0_total_intake_downstream_gate_audit_official_path_total_gate_status_stage133_wave0_total_intake_downstream_gate_audit_v1.png`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage133_wave0_total_intake_downstream_gate_audit/qmt_roll_stage133_c9_minrisk_wave0_total_intake_downstream_gate_audit_expectation_matrix_stage133_wave0_total_intake_downstream_gate_audit_v1.png`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage133_wave0_total_intake_downstream_gate_audit/qmt_roll_stage133_c9_minrisk_wave0_total_intake_downstream_gate_audit_case_downstream_matrix_stage133_wave0_total_intake_downstream_gate_audit_v1.png`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage133_wave0_total_intake_downstream_gate_audit/qmt_roll_stage133_c9_minrisk_wave0_total_intake_downstream_gate_audit_stage112_113_shadow_gate_chart_stage133_wave0_total_intake_downstream_gate_audit_v1.png`

## 视觉检查

- 官方路径图：资金、回撤、broker10 曲线非空；Stage131 fixture 红点只是“被总闸门阻断的请求位置”，不是可交易收益来源。底部 case release path 显示 Stage128 ready 为 `1`，但 Stage112 ready、Stage113 indexed、downstream release 都是 `0`。
- 预期矩阵：`9/9` 全绿，分别覆盖空 drop 阻断、fixture Stage128 正向、Stage112/113 marker 检出、Stage113 index 阻断、最终 release 为 0 和 Stage128 默认恢复。
- case downstream 矩阵：Stage131 fixture 只在 Stage128 ready、Stage112 marker、Stage113 marker 上为 `1`；Stage112 rule ready、Stage113 indexed、downstream release 均为 `0`。
- Stage112/113 shadow gate 图：shadow root 与 manifest 存在为绿，其余 release 条件均为红，说明“有完整文件”不是充分条件。

## 结论

- 本阶段结论：Stage128 是真实 W0 接收链路的必要条件，但不是分钟研究/策略下游可用的充分条件；Stage128 ready 后必须继续通过 Stage112/113。Stage131 本地 fixture 即使让 Stage128 ready，也会在 Stage112/113 被阻断，最终 `downstream_release_allowed_count=0`。
- 是否进入下一步：是，但仍只能做真实 W0 到货前的闸门/流程准备，或等待真实 W0 drop 后按 Stage133 总闸门复验。
- 下一步：把 Stage133 的总闸门做成真实到货 CLI 入口：`--drop-dir <real_w0_drop>`，输出一份“可进入 Stage112/113/分钟研究”的单一 release verdict；真实 W0 未到货前继续禁止分钟规则和 true engine。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段没有调交易参数、没有挑收益窗口、没有从 fixture 中提取信号，只是把数据质量和 provenance gate 放在策略下游之前。这是普世工程约束，跨周期、跨品种都成立，不依赖样本内收益表现。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值。
- 原因：Stage128 ready 若被人工误解为“可做分钟策略”，会污染整条研究线。Stage133 明确把 Stage128 和 Stage112/113 串成 release discipline，让未来真实 W0 到货后可以一次性判断是否能进入高质量分钟信号研究。

## 合入建议

- 是否更新本线 `LINE.md`：是
- 是否更新 `research/registry.md`：否；这不是新增研究线或跨线合入
- 是否追加根目录 `memory.md/back_log.md`：否；这不是正式候选、重大突破或跨线合并
