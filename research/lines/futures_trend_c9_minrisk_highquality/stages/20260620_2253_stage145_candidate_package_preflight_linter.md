# Stage145 候选包提交前 linter / placeholder 扫描器

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：2026-06-20 22:53 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：研究基础设施 / 候选包提交前阻断
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - pre-commit：https://pre-commit.com/
  - Frictionless Framework report guide：https://v4.framework.frictionlessdata.io/docs/guides/framework/report-guide
  - jsonschema validation errors：https://python-jsonschema.readthedocs.io/en/latest/errors/
  - JSON Schema validation vocabulary：https://json-schema.org/draft/2020-12/json-schema-validation
  - Great Expectations Data Docs：https://docs.greatexpectations.io/docs/0.18/reference/learn/terms/data_docs/
- 我的判断：真实候选包不应该直接进 Stage142；应先做 pre-commit 风格的本地硬检查，把模板残留、伪 provenance、未通过 evidence、占位图 hash 这类低级污染提前挡掉。Frictionless/jsonschema 的经验是输出可机器读取的 issue catalog，Data Docs 的经验是同时给人工可读报告。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage145_candidate_package_preflight_linter.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：`--candidate-package-dir`、`--case-id`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用 Stage045/Stage134/Stage142 已固定 C9 minrisk 账本输入；本阶段不新增策略回测。
- 账户规模：沿用本线 C9 minrisk 研究口径。
- 成本口径：沿用输入账本，`total_slippage=2,730,130`
- 样本过滤：无新增过滤；默认扫描 Stage144 模板目录作为阻断自测。
- 策略/归因口径：候选包提交前 linter，不创建交易规则，不运行 true engine，不触发 A/B，不改变 official config。

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：`36.0902%`
- 其他关键指标：
  - decision：`stage145_preflight_linter_ready_template_blocked_no_strategy`
  - linter_ready：`1`
  - default_template_mode：`1`
  - default_template_blocked：`1`
  - preflight_pass：`0`
  - issue_count：`41`
  - hard_stop_count：`41`
  - check_pass_count：`4/9`
  - file_audit_count：`22`
  - placeholder_text_file_count：`16`
  - visual_placeholder_hash_match_count：`5/5`
  - safe_operator_command_count：`3`
  - unsafe_operator_command_count：`0`
  - gate_pass_count：`5/5`
  - current_package_promotion_allowed：`0`

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage145_candidate_package_preflight_linter/qmt_roll_stage145_c9_minrisk_candidate_package_preflight_linter_report_stage145_candidate_package_preflight_linter_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage145_candidate_package_preflight_linter/qmt_roll_stage145_c9_minrisk_candidate_package_preflight_linter_summary_stage145_candidate_package_preflight_linter_v1.csv`
- orders：无
- daily：无新增 daily 账本
- quality：
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage145_candidate_package_preflight_linter/qmt_roll_stage145_c9_minrisk_candidate_package_preflight_linter_issue_catalog_stage145_candidate_package_preflight_linter_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage145_candidate_package_preflight_linter/qmt_roll_stage145_c9_minrisk_candidate_package_preflight_linter_file_audit_stage145_candidate_package_preflight_linter_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage145_candidate_package_preflight_linter/qmt_roll_stage145_c9_minrisk_candidate_package_preflight_linter_visual_audit_stage145_candidate_package_preflight_linter_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage145_candidate_package_preflight_linter/qmt_roll_stage145_c9_minrisk_candidate_package_preflight_linter_preflight_checklist_stage145_candidate_package_preflight_linter_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage145_candidate_package_preflight_linter/qmt_roll_stage145_c9_minrisk_candidate_package_preflight_linter_operator_command_manifest_stage145_candidate_package_preflight_linter_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage145_candidate_package_preflight_linter/qmt_roll_stage145_c9_minrisk_candidate_package_preflight_linter_gate_status_stage145_candidate_package_preflight_linter_v1.csv`
  - 5 张视觉图：official path linter status、issue matrix、visual audit matrix、preflight checklist matrix、gate status matrix。

## 结论

- 本阶段结论：Stage145 已完成候选包提交前 linter。默认扫描 Stage144 模板时，结构存在但被硬阻断：`synthetic_case=1`、forbidden provenance marker、`TEMPLATE_` 残留、summary 占位指标、11 项 evidence `pass_now=0`、16 个文本文件含 placeholder token、5 张视觉图 hash 命中 Stage144 占位图。该结果证明 linter 能在 Stage142 前阻断模板/伪候选。
- 是否进入下一步：是。
- 下一步：继续沿当前研究线推进。若真实 W0/候选包仍未到货，下一步只允许做 linter 与 Stage142/143 的一键串联 smoke；若真实候选包到货，则先跑 Stage145 preflight，只有 `preflight_pass=1` 才允许进入 Stage142 validator。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段没有交易规则、参数、样本筛选或收益优化；它是提交前质量闸门，专门阻断模板残留和伪证据，反而降低后续过拟合/伪候选风险。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值。
- 原因：当前真实 W0/分钟候选仍未到货，但 Stage145 让未来候选在 Stage142 之前先过“真包”检查，避免把占位模板、synthetic 包或未完成 evidence 当成研究结果。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：否。
