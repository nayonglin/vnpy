# Stage142 候选结果包合同验证器

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：2026-06-20 22:31 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：研究基础设施 / 晋级证据合同验证
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - JSON Schema validation vocabulary：https://json-schema.org/draft/2020-12/json-schema-validation
  - Frictionless Data Package spec：https://specs.frictionlessdata.io/data-package/
  - W3C PROV overview：https://www.w3.org/TR/prov-overview/
- 我的判断：未来候选不能只交一张收益表，必须像 Data Package 一样有清晰资源清单，像 JSON Schema 一样有字段/类型/必填约束，并保留 provenance 证据链。这里不引入新依赖，先做本线轻量 validator：把 Stage141 的硬阈值、证据项和视觉产物变成可复跑验收入口，同时显式阻断 synthetic / fixture 伪候选。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage142_candidate_package_contract_validator.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：`--candidate-package-dir`、`--case-id`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用 Stage045/Stage134 已固定 C9 minrisk 账本输入；本阶段不新增策略回测。
- 账户规模：沿用本线 C9 minrisk 研究口径。
- 成本口径：沿用输入账本，`total_slippage=2,730,130`
- 样本过滤：无新增过滤；默认只跑 4 个 validator 自测 case。
- 策略/归因口径：候选包结构验证，不创建交易规则，不运行 true engine，不触发 A/B，不改变 official config。

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：`36.0902%`
- 其他关键指标：
  - decision：`stage142_candidate_package_validator_ready_no_real_candidate_promoted`
  - validator_ready：`1`
  - schema_audit_pass_count：`5/5`
  - validation_expectation_pass_count：`4/4`
  - selftest_pass：`1`
  - current_package_promotion_allowed：`0`
  - real_candidate_package_supplied：`0`
  - hard thresholds：`candidate_total_return_pct >= 20814.1001%`、`abs(max_drawdown_pct) <= 40.0827%`、`max_broker10 <= 111.7365%`

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage142_candidate_package_contract_validator/qmt_roll_stage142_c9_minrisk_candidate_package_contract_validator_report_stage142_candidate_package_contract_validator_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage142_candidate_package_contract_validator/qmt_roll_stage142_c9_minrisk_candidate_package_contract_validator_summary_stage142_candidate_package_contract_validator_v1.csv`
- orders：无
- daily：无新增 daily 账本
- quality：
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage142_candidate_package_contract_validator/qmt_roll_stage142_c9_minrisk_candidate_package_contract_validator_candidate_package_schema_stage142_candidate_package_contract_validator_v1.json`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage142_candidate_package_contract_validator/qmt_roll_stage142_c9_minrisk_candidate_package_contract_validator_package_schema_audit_stage142_candidate_package_contract_validator_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage142_candidate_package_contract_validator/qmt_roll_stage142_c9_minrisk_candidate_package_contract_validator_validation_audit_stage142_candidate_package_contract_validator_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage142_candidate_package_contract_validator/qmt_roll_stage142_c9_minrisk_candidate_package_contract_validator_selftest_cases_stage142_candidate_package_contract_validator_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage142_candidate_package_contract_validator/qmt_roll_stage142_c9_minrisk_candidate_package_contract_validator_gate_status_stage142_candidate_package_contract_validator_v1.csv`
  - 5 张视觉图：official path validator status、schema matrix、validation matrix、selftest matrix、gate status matrix。

## 结论

- 本阶段结论：Stage142 validator 已可用。默认无真实候选包时不允许 promotion；`missing_evidence_fixture` 因证据/视觉缺失被拦；`synthetic_good_fixture` 即使指标和证据都满足，也因 synthetic 被拦；`fake_real_fixture_marker` 即使标记为非 synthetic，也因 fixture marker 被拦。
- 是否进入下一步：是。
- 下一步：继续沿当前研究线做真实候选前的证据入口加固，优先补一个候选包 operator runbook / CLI 示例和失败原因摘要，确保未来真实候选到来时只需要交包验证，不再临时解释证据格式。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段没有用收益结果反推规则、没有新增交易参数、没有按样本筛选候选，只把 Stage141 预先固定的晋级合同变成机械验收入口；synthetic positive 只验证合同逻辑，不能 promotion。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值。
- 原因：当前真实 W0/分钟候选仍未到货，但晋级口径已经被固定。继续做候选包验收和 operator 入口能降低未来伪候选、残缺证据、fixture 混入和临时改口径的风险，属于可穿越周期的研究基础设施。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：否。
