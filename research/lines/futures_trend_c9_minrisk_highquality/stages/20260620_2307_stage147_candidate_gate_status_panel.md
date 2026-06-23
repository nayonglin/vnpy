# Stage147 候选包门禁链路只读状态面板

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：2026-06-20 23:07 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：研究基础设施 / 候选包门禁链路只读状态面板
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - Great Expectations Data Docs：https://docs.greatexpectations.io/docs/0.18/reference/learn/terms/data_docs/
  - Frictionless validating data：https://framework.frictionlessdata.io/docs/guides/validating-data.html
  - pre-commit：https://pre-commit.com/
  - pre-commit.ci：https://pre-commit.ci/
- 我的判断：当前阶段不应该继续重复确认正式版，也不应该重新跑 Stage145/142/143；应该读取 Stage146 已保存的门禁链路结果，像验证报告/Data Docs 一样把当前状态、阻断原因、下一步动作和安全锁统一展示。这样既满足真实候选包到来前的可读性，又避免把模板、fixture 或无候选状态误当策略进展。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage147_candidate_gate_status_panel.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用 Stage045/Stage134/Stage142/Stage146 已固定 C9 minrisk 账本输入；本阶段不新增策略回测。
- 账户规模：沿用本线 C9 minrisk 研究口径。
- 成本口径：沿用输入账本，`total_slippage=2,730,130`
- 样本过滤：无新增过滤；只读读取 Stage142/143/145/146 已保存 summary/gate/detail 产物。
- 策略/归因口径：候选包门禁状态面板，不创建交易规则，不运行 true engine，不触发 A/B，不改变 official config，不连接 CTP，不调用 order API。

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：`36.0902%`
- 其他关键指标：
  - decision：`stage147_gate_status_panel_ready_no_candidate_no_strategy`
  - recommended_action：`wait_real_candidate_or_keep_readonly_status_panel`
  - status_panel_ready：`1`
  - latest_chain_smoke_ready：`1`
  - stage145_linter_ready：`1`
  - stage145_template_blocked：`1`
  - stage145_preflight_pass：`0`
  - stage142_validator_ready：`1`
  - stage142_validation_expectation_pass_count：`4`
  - stage143_explainer_ready：`1`
  - upstream_ready_count：`4/4`
  - upstream_gate_all_pass_count：`4/4`
  - readiness_check_pass_count：`16/16`
  - artifact_present_count：`14/14`
  - fresh_24h_count：`14/14`
  - real_candidate_package_supplied：`0`
  - current_package_promotion_allowed：`0`
  - side_effect_count：`0`

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage147_candidate_gate_status_panel/qmt_roll_stage147_c9_minrisk_candidate_gate_status_panel_report_stage147_candidate_gate_status_panel_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage147_candidate_gate_status_panel/qmt_roll_stage147_c9_minrisk_candidate_gate_status_panel_summary_stage147_candidate_gate_status_panel_v1.csv`
- orders：无
- daily：无新增 daily 账本
- quality：
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage147_candidate_gate_status_panel/qmt_roll_stage147_c9_minrisk_candidate_gate_status_panel_upstream_status_stage147_candidate_gate_status_panel_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage147_candidate_gate_status_panel/qmt_roll_stage147_c9_minrisk_candidate_gate_status_panel_readiness_checklist_stage147_candidate_gate_status_panel_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage147_candidate_gate_status_panel/qmt_roll_stage147_c9_minrisk_candidate_gate_status_panel_artifact_freshness_audit_stage147_candidate_gate_status_panel_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage147_candidate_gate_status_panel/qmt_roll_stage147_c9_minrisk_candidate_gate_status_panel_operator_action_panel_stage147_candidate_gate_status_panel_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage147_candidate_gate_status_panel/qmt_roll_stage147_c9_minrisk_candidate_gate_status_panel_gate_status_stage147_candidate_gate_status_panel_v1.csv`
  - 5 张视觉图：official path status、upstream readiness matrix、readiness checklist matrix、artifact freshness matrix、gate status matrix。

## 结论

- 本阶段结论：Stage147 已把 Stage142/143/145/146 的当前门禁状态汇总成只读 operator panel。当前链路 ready，但没有真实候选包；Stage145 仍只是在模板上证明能阻断，`preflight_pass=0` 是正确状态；`current_package_promotion_allowed=0`，且没有 true engine、A/B、order API、CTP 或 official config 变更。
- 是否进入下一步：是。
- 下一步：真实候选包未到货前，只保留只读状态面板和等待；真实候选包到货后，先跑 Stage145 preflight，只有 `preflight_pass=1` 才允许同一包进入 Stage142/143。若继续自动化，只能做候选包到货事件的只读提醒，不得安装/加载执行链路或触发策略候选。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段没有收益优化、参数扫描、样本筛选或交易规则；只读取已保存门禁产物并把状态可视化。它的作用是防止伪候选误入，不会提高历史收益指标。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值。
- 原因：当前研究线卡在“真实候选包未到、必须严控晋级流程”的阶段。只读状态面板让门禁状态、阻断原因和下一步动作变成可复验资产，后续真实候选包到来时能减少人工误判。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：否。
