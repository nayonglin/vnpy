# Stage159 权威分钟数据 release runbook

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-21 00:45-00:47`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：真实授权 1m OHLCV + real volume/OI 到货后的 operator release checklist / runbook
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - RFC 8493 BagIt：`https://datatracker.ietf.org/doc/rfc8493/`
  - JSON Schema 官方文档：`https://json-schema.org/docs`
  - W3C PROV-DM：`https://www.w3.org/TR/prov-dm/`
- 我的判断：Stage159 不应继续制造策略规则，而应把真实数据到货后的放行顺序固定为“完整性 -> 有效性 -> 来源责任链”。BagIt/RFC8493 区分 complete 和 valid，JSON Schema 只管结构约束，PROV 负责来源链；所以真实数据到货后必须先确认 raw/proof/normalized 三件套完整，再跑 proof/schema/hash/window coverage，再跑 feature readiness 和 feature row lineage，最后才允许只读 feature atlas。这个判断避免把缺数据、模板 proof 或局部样本视觉印象误当作 alpha。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage159_authoritative_minute_release_runbook.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无策略参数；新增固定 release checklist、operator command manifest、failure triage、readiness matrix、gate status。
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用 Stage045/Stage153 官方路径资金曲线作视觉跟踪；本阶段不运行新回测。
- 账户规模：沿用当前研究线官方路径口径。
- 成本口径：沿用 Stage153 官方路径总滑点口径。
- 样本过滤：无新增过滤；真实数据仍未到货，所有 Stage153/156/157/158 data gates 维持阻断。
- 策略/归因口径：release discipline / data infrastructure；不创建策略规则、不运行 true engine、不触发 A/B、不改变 official config、不连接 CTP、不调用 order API。

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：`36.0902%`
- 其他关键指标：
  - `decision=stage159_authoritative_minute_release_runbook_ready_blocked_wait_real_data_no_rule`
  - `stage152_request_template_count=233`
  - `stage153_request_count=233`
  - `stage153_request_ready_count=0`
  - `stage153_required_window_count=657`
  - `stage153_window_coverage_pass_count=0`
  - `stage156_feature_ready_window_count=0`
  - `stage157_feature_table_row_written_count=0`
  - `stage158_lineage_pass_window_count=0`
  - `release_checklist_step_count=7`
  - `operator_command_count=6`
  - `safe_operator_command_count=6`
  - `commands_with_ctp_or_order_api=0`
  - `commands_change_official_config=0`
  - `failure_triage_count=15`
  - `release_readiness_pass_count=0/6`
  - `feature_atlas_allowed_now=0`
  - `current_package_promotion_allowed=0`
  - `true_engine_allowed=0`
  - `strategy_feature_usable=0`
  - `objective_completion_proven=0`
  - `max_broker10_margin_to_equity_pct=111.7365%`

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage159_authoritative_minute_release_runbook/qmt_roll_stage159_c9_minrisk_authoritative_minute_release_runbook_report_stage159_authoritative_minute_release_runbook_v1.md`
- runbook：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage159_authoritative_minute_release_runbook/qmt_roll_stage159_c9_minrisk_authoritative_minute_release_runbook_REAL_DATA_RELEASE_RUNBOOK_stage159_authoritative_minute_release_runbook_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage159_authoritative_minute_release_runbook/qmt_roll_stage159_c9_minrisk_authoritative_minute_release_runbook_summary_stage159_authoritative_minute_release_runbook_v1.csv`
- release checklist：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage159_authoritative_minute_release_runbook/qmt_roll_stage159_c9_minrisk_authoritative_minute_release_runbook_release_checklist_stage159_authoritative_minute_release_runbook_v1.csv`
- operator command manifest：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage159_authoritative_minute_release_runbook/qmt_roll_stage159_c9_minrisk_authoritative_minute_release_runbook_operator_command_manifest_stage159_authoritative_minute_release_runbook_v1.csv`
- readiness matrix：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage159_authoritative_minute_release_runbook/qmt_roll_stage159_c9_minrisk_authoritative_minute_release_runbook_readiness_matrix_stage159_authoritative_minute_release_runbook_v1.csv`
- failure triage：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage159_authoritative_minute_release_runbook/qmt_roll_stage159_c9_minrisk_authoritative_minute_release_runbook_failure_triage_stage159_authoritative_minute_release_runbook_v1.csv`
- gate status：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage159_authoritative_minute_release_runbook/qmt_roll_stage159_c9_minrisk_authoritative_minute_release_runbook_gate_status_stage159_authoritative_minute_release_runbook_v1.csv`
- decision：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage159_authoritative_minute_release_runbook/qmt_roll_stage159_c9_minrisk_authoritative_minute_release_runbook_decision_stage159_authoritative_minute_release_runbook_v1.json`
- orders：无；本阶段禁止报单和 true engine。
- daily：无新增回测 daily；使用官方路径资金曲线图跟踪。
- quality：5 张 PNG 视觉产物均非空：
  - `qmt_roll_stage159_c9_minrisk_authoritative_minute_release_runbook_official_path_release_status_stage159_authoritative_minute_release_runbook_v1.png`
  - `qmt_roll_stage159_c9_minrisk_authoritative_minute_release_runbook_release_checklist_matrix_stage159_authoritative_minute_release_runbook_v1.png`
  - `qmt_roll_stage159_c9_minrisk_authoritative_minute_release_runbook_readiness_matrix_stage159_authoritative_minute_release_runbook_v1.png`
  - `qmt_roll_stage159_c9_minrisk_authoritative_minute_release_runbook_failure_triage_bar_stage159_authoritative_minute_release_runbook_v1.png`
  - `qmt_roll_stage159_c9_minrisk_authoritative_minute_release_runbook_gate_status_matrix_stage159_authoritative_minute_release_runbook_v1.png`

## 视觉分析

- 官方路径资金曲线仍保持长右尾，但 Stage159 没有改善收益/回撤，只用于确认当前研究没有偏离原始目标。
- release checklist matrix 显示 7 个步骤全部 `allowed_now=0`，其中前 5 个是 data hard gate；这说明现在不能直接进入 feature atlas 或候选。
- readiness matrix 显示 6 个硬门槛全部未过：Stage153 intake `0/233`、Stage153 coverage `0/657`、Stage156 feature readiness `0/657`、Stage156 OI `0/657`、Stage157 feature rows `0/657`、Stage158 lineage `0/657`。
- failure triage bar 的主阻断集中在交付层：raw/proof/normalized 各 `233`，window coverage `657`，feature/lineage 后续阻断也都是上游缺数据传导，不是策略失败。
- gate status matrix 显示安全闸门通过：命令清单 6 条都是 safe command，`commands_with_ctp_or_order_api=0`、`commands_change_official_config=0`。

## 结论

- 本阶段结论：Stage159 把真实授权分钟数据到货后的操作顺序固定住了，但不证明目标完成，也不产生任何候选。当前唯一正确状态仍是等待真实 raw/proof/normalized 授权包，到货后按 runbook 顺序重跑 Stage153/156/157/158。
- 是否进入下一步：可以继续，但不能继续围绕 0 ready windows 做策略规则。
- 下一步：若真实数据到货，按 runbook 执行 Stage153 -> Stage156 -> Stage157 -> Stage158；若真实数据仍未到，最多做轻量到货监控或暂停该数据工程分支，不应继续制造规则。

## 过拟合反思

- 运行前判断：否。Stage159 的目标是 release discipline，不使用历史收益切分、不调阈值、不选择品种/年份/月度。
- 运行后判断：否。所有 data gates 仍在缺真实数据处阻断，脚本没有把任何缺失状态、right-tail/bottom-loss 标签或资金曲线形态变成交易规则。
- 原因：本阶段只固化完整性、有效性、来源责任链和命令顺序；没有 true engine，没有 A/B，没有新增交易参数。

## 继续价值反思

- 运行前判断：有，但价值边界很窄。继续价值来自防止真实数据到货后被手工误放行，而不是继续提升收益指标。
- 运行后判断：仍有价值，但不宜再加厚 no-data 工程。Stage159 已把 checklist/runbook 补齐；没有真实分钟数据时，再继续做策略层研究会偏离“高质量信号 + 最小风险”的目标。
- 原因：当前最大瓶颈不是模型，而是真实可审计分钟 OHLCV+volume+OI 的缺失。继续做数据到货监控有价值；继续造规则没有价值。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage159 摘要。
- 是否更新 `research/registry.md`：否，未新增研究线。
- 是否追加根目录 `memory.md/back_log.md`：否，非重要突破、非正式候选、非路线废弃。
