# Stage144 最小候选包模板生成器

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：2026-06-20 22:45 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：研究基础设施 / 候选包模板与提交纪律
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - Frictionless Data Package spec：https://specs.frictionlessdata.io/data-package/
  - JSON Schema getting started：https://json-schema.org/learn/getting-started-step-by-step
  - W3C PROV-DM：https://www.w3.org/TR/prov-dm/
  - W3C PROV overview：https://www.w3.org/TR/prov-overview/
  - Great Expectations Data Docs：https://docs.greatexpectations.io/docs/0.18/reference/learn/terms/data_docs/
- 我的判断：未来分钟级候选不能临时拼几个 CSV。应有 Data Package 风格的 descriptor/resource list、JSON Schema 风格的必填字段契约、PROV 风格的来源/活动/生成者线索，以及 Data Docs 风格的人工可读提交说明。Stage144 只生成模板并证明模板仍被阻断，不放宽 Stage141/142/143 的任何晋级条件。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage144_candidate_package_template_builder.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：`--candidate-id`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用 Stage045/Stage134/Stage142 已固定 C9 minrisk 账本输入；本阶段不新增策略回测。
- 账户规模：沿用本线 C9 minrisk 研究口径。
- 成本口径：沿用输入账本，`total_slippage=2,730,130`
- 样本过滤：无新增过滤；模板通过 Stage142 内存复验。
- 策略/归因口径：模板生成与安全阻断验证，不创建交易规则，不运行 true engine，不触发 A/B，不改变 official config。

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：`36.0902%`
- 其他关键指标：
  - decision：`stage144_candidate_package_template_ready_template_blocked_no_strategy`
  - template_builder_ready：`1`
  - template_file_count：`22`
  - template_required_resource_count：`8`
  - template_required_resource_present_count：`8`
  - submission_check_count：`8`
  - submission_check_template_pass_count：`4`
  - submission_check_real_required_count：`8`
  - stage142_template_validation_blocked：`1`
  - stage142_template_would_pass_if_real：`0`
  - stage142_template_promotion_allowed：`0`
  - safe_operator_command_count：`4`
  - unsafe_operator_command_count：`0`
  - gate_pass_count：`6/6`
  - current_package_promotion_allowed：`0`

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage144_candidate_package_template_builder/qmt_roll_stage144_c9_minrisk_candidate_package_template_builder_report_stage144_candidate_package_template_builder_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage144_candidate_package_template_builder/qmt_roll_stage144_c9_minrisk_candidate_package_template_builder_summary_stage144_candidate_package_template_builder_v1.csv`
- orders：无
- daily：无新增 daily 账本
- quality：
  - 模板目录：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage144_candidate_package_template_builder/candidate_package_template/`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage144_candidate_package_template_builder/qmt_roll_stage144_c9_minrisk_candidate_package_template_builder_template_resource_manifest_stage144_candidate_package_template_builder_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage144_candidate_package_template_builder/qmt_roll_stage144_c9_minrisk_candidate_package_template_builder_submission_checklist_stage144_candidate_package_template_builder_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage144_candidate_package_template_builder/qmt_roll_stage144_c9_minrisk_candidate_package_template_builder_stage142_template_validation_stage144_candidate_package_template_builder_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage144_candidate_package_template_builder/qmt_roll_stage144_c9_minrisk_candidate_package_template_builder_operator_command_manifest_stage144_candidate_package_template_builder_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage144_candidate_package_template_builder/qmt_roll_stage144_c9_minrisk_candidate_package_template_builder_gate_status_stage144_candidate_package_template_builder_v1.csv`
  - 5 张视觉图：official path template status、resource manifest matrix、Stage142 template validation matrix、submission checklist matrix、gate status matrix。

## 结论

- 本阶段结论：Stage144 已生成最小候选包模板，包含 `manifest.json`、`summary.csv`、`evidence.csv`、`datapackage.json`、`README.md`、`SUBMISSION_CHECKLIST.md`、11 个 evidence 占位说明和 5 张视觉占位图。模板文件完整，但被 Stage142 复验明确阻断：`would_pass_if_real=0`、`promotion_allowed=0`，原因包括收益门、broker10 门、all evidence 和 synthetic/provenance 均未满足。
- 是否进入下一步：是。
- 下一步：继续沿当前研究线推进，优先做真实候选包“提交前 linter / placeholder 扫描器”，确保任何真实候选包在 Stage142 前先被检查出残留 `TEMPLATE_`、placeholder 图片、`synthetic_case=1` 或 evidence `pass_now=0`。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段没有使用收益反推交易规则，没有新增交易参数，没有按年份/品种/方向筛选；模板反而强制未来候选必须提交完整证据与视觉件，并证明模板自身不能晋级。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值。
- 原因：当前真实 W0/分钟候选仍未到货，但模板把未来候选的最低证据结构提前固化，能降低“临时补文件、缺视觉、缺 OOS、伪 provenance”造成的研究污染风险。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：否。
