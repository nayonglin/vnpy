# Stage143 候选包 operator runbook 与失败原因解释器

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：2026-06-20 22:38 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：研究基础设施 / 候选包验收可解释性
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - Frictionless Framework report guide：https://v4.framework.frictionlessdata.io/docs/guides/framework/report-guide
  - Frictionless validation guide：https://v4.framework.frictionlessdata.io/docs/guides/validation-guide
  - JSON Schema validation vocabulary：https://json-schema.org/draft/2020-12/json-schema-validation
  - Great Expectations Data Docs：https://docs.greatexpectations.io/docs/0.18/reference/learn/terms/data_docs/
  - GitHub frictionless-py discussion on human/machine readable reports：https://github.com/frictionlessdata/frictionless-py/discussions/1723
- 我的判断：验证入口不能只有一个布尔值；必须同时给机器可读 CSV、人工可读 runbook、失败 reason code 和下一步动作。Frictionless/Great Expectations 的共同经验是把验证结果变成可解释报告，JSON Schema 的核心价值是结构化断言。Stage143 只做解释层，不替代 Stage142 合同、不放宽任何晋级阈值。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage143_candidate_package_operator_failure_explainer.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：`--candidate-placeholder`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用 Stage045/Stage134/Stage142 已固定 C9 minrisk 账本输入；本阶段不新增策略回测。
- 账户规模：沿用本线 C9 minrisk 研究口径。
- 成本口径：沿用输入账本，`total_slippage=2,730,130`
- 样本过滤：无新增过滤；解释 Stage142 默认 4 个 validator case。
- 策略/归因口径：候选包失败原因解释器，不创建交易规则，不运行 true engine，不触发 A/B，不改变 official config。

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：`36.0902%`
- 其他关键指标：
  - decision：`stage143_operator_failure_explainer_ready_no_candidate_no_strategy`
  - operator_runbook_ready：`1`
  - stage142_validator_ready：`1`
  - failure_reason_count：`16`
  - unique_failure_reason_count：`11`
  - triage_case_count：`4`
  - safe_operator_command_count：`5`
  - unsafe_operator_command_count：`0`
  - gate_pass_count：`5/5`
  - current_package_promotion_allowed：`0`
  - real_candidate_package_supplied：`0`

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage143_candidate_package_operator_failure_explainer/qmt_roll_stage143_c9_minrisk_candidate_package_operator_failure_explainer_operator_runbook_stage143_candidate_package_operator_failure_explainer_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage143_candidate_package_operator_failure_explainer/qmt_roll_stage143_c9_minrisk_candidate_package_operator_failure_explainer_summary_stage143_candidate_package_operator_failure_explainer_v1.csv`
- orders：无
- daily：无新增 daily 账本
- quality：
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage143_candidate_package_operator_failure_explainer/qmt_roll_stage143_c9_minrisk_candidate_package_operator_failure_explainer_operator_command_manifest_stage143_candidate_package_operator_failure_explainer_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage143_candidate_package_operator_failure_explainer/qmt_roll_stage143_c9_minrisk_candidate_package_operator_failure_explainer_failure_reason_catalog_stage143_candidate_package_operator_failure_explainer_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage143_candidate_package_operator_failure_explainer/qmt_roll_stage143_c9_minrisk_candidate_package_operator_failure_explainer_sample_triage_cases_stage143_candidate_package_operator_failure_explainer_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage143_candidate_package_operator_failure_explainer/qmt_roll_stage143_c9_minrisk_candidate_package_operator_failure_explainer_gate_status_stage143_candidate_package_operator_failure_explainer_v1.csv`
  - 5 张视觉图：official path operator status、failure reason matrix、operator command safety matrix、sample triage matrix、gate status matrix。

## 结论

- 本阶段结论：Stage143 已把 Stage142 的 validator 输出转成 operator 可执行 runbook 和失败原因目录。`no_package` 的主失败原因是 `MISSING_PACKAGE`；`missing_evidence_fixture` 的主失败原因是 `VISUAL_ARTIFACTS_INCOMPLETE`；`synthetic_good_fixture` 与 `fake_real_fixture_marker` 即使指标通过也因 fixture/provenance 标记被拦。5 条 operator 命令均为只读/本线输出范围，`true_engine_run=0`、`ab_triggered=0`、`order_api_called=0`、`ctp_connected=0`。
- 是否进入下一步：是。
- 下一步：继续沿当前研究线推进，优先做真实候选包到来前的“最小合格包模板/空包生成器”，让未来分钟规则候选必须先按 Stage141/142/143 的结构提交完整证据，而不是临时拼 CSV 或图。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段不使用历史收益改规则，不新增交易参数，不筛年份/品种/方向，只把固定合同的失败原因机械映射为 reason code 和 operator action。它不会让任何候选更容易通过，只让拒绝原因更清楚。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值。
- 原因：当前真实 W0/分钟候选仍未到货，但未来若没有统一验收入口，很容易把 fixture、自测包、缺视觉证据或缺 OOS 的结果误读成候选。Stage143 降低的是研究流程风险，对长期穿越周期更重要。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：否。
