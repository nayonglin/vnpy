# Stage146 候选包闸门链路一键 smoke

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：2026-06-20 22:59 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：研究基础设施 / Stage145 -> Stage142 -> Stage143 串联 smoke
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - Great Expectations Checkpoint：https://docs.greatexpectations.io/docs/reference/api/Checkpoint_class
  - Great Expectations Validation Result：https://docs.greatexpectations.io/docs/0.18/reference/learn/terms/validation_result
  - pre-commit 手动运行：https://pre-commit.com/
  - Frictionless CLI overview：https://framework.frictionlessdata.io/docs/console/overview.html
  - Frictionless validation guide：https://v4.framework.frictionlessdata.io/docs/guides/validation-guide
- 我的判断：未来真实候选包需要一个可复跑的一键门禁链路，而不是人工分别运行三个脚本。Stage146 借鉴 Checkpoint/Smoke 的思想，把 Stage145 preflight、Stage142 contract validator、Stage143 failure explainer 串成一次确定性 smoke，并保留每步命令、stdout JSON、决策与安全锁。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage146_candidate_gate_chain_smoke.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：`--candidate-package-dir`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用 Stage045/Stage134/Stage142 已固定 C9 minrisk 账本输入；本阶段不新增策略回测。
- 账户规模：沿用本线 C9 minrisk 研究口径。
- 成本口径：沿用输入账本，`total_slippage=2,730,130`
- 样本过滤：无新增过滤；默认用 Stage144 模板目录做阻断自测。
- 策略/归因口径：候选包门禁链路 smoke，不创建交易规则，不运行 true engine，不触发 A/B，不改变 official config。

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：`36.0902%`
- 其他关键指标：
  - decision：`stage146_gate_chain_smoke_ready_no_candidate_no_strategy`
  - chain_smoke_ready：`1`
  - command_count：`3`
  - command_returncode_zero_count：`3/3`
  - stdout_json_parsed_count：`3/3`
  - step_expected_behavior_pass_count：`3/3`
  - step_safety_lock_pass_count：`3/3`
  - gate_pass_count：`6/6`
  - stage145_default_template_blocked：`1`
  - stage145_preflight_pass：`0`
  - stage142_validator_ready：`1`
  - stage142_validation_expectation_pass_count：`4`
  - stage143_explainer_ready：`1`
  - any_promotion_allowed：`0`
  - true_engine_run_count：`0`
  - official_config_changed：`0`

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage146_candidate_gate_chain_smoke/qmt_roll_stage146_c9_minrisk_candidate_gate_chain_smoke_report_stage146_candidate_gate_chain_smoke_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage146_candidate_gate_chain_smoke/qmt_roll_stage146_c9_minrisk_candidate_gate_chain_smoke_summary_stage146_candidate_gate_chain_smoke_v1.csv`
- orders：无
- daily：无新增 daily 账本
- quality：
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage146_candidate_gate_chain_smoke/qmt_roll_stage146_c9_minrisk_candidate_gate_chain_smoke_command_audit_stage146_candidate_gate_chain_smoke_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage146_candidate_gate_chain_smoke/qmt_roll_stage146_c9_minrisk_candidate_gate_chain_smoke_step_summary_stage146_candidate_gate_chain_smoke_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage146_candidate_gate_chain_smoke/qmt_roll_stage146_c9_minrisk_candidate_gate_chain_smoke_gate_status_stage146_candidate_gate_chain_smoke_v1.csv`
  - 5 张视觉图：official path chain status、step status matrix、command safety matrix、lock status matrix、gate status matrix。

## 结论

- 本阶段结论：Stage146 已把 Stage145 -> Stage142 -> Stage143 串成一键 smoke。三步均返回 `0`，stdout JSON 全部解析，Stage145 正确阻断 Stage144 模板，Stage142 默认合同自测通过且不 promotion，Stage143 operator explainer 就绪且不 promotion。全链路没有 true engine、A/B、order API、CTP 或 official config 变更。
- 是否进入下一步：是。
- 下一步：若真实 W0/候选包仍未到货，继续只做门禁链路的只读扩展，例如增加真实候选包到货前的链路状态面板；若真实候选包到货，先跑 Stage145 preflight，只有 `preflight_pass=1` 才允许把同一包交给 Stage142/143 链路。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段没有交易规则、参数、样本筛选或收益优化；它只验证门禁链路可复跑并保持所有安全锁为 0，作用是减少伪候选和流程断点。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值。
- 原因：本目标最终需要严格、可复验、可视觉审计的候选晋级流程。Stage146 让提交前 linter、合同 validator 和失败解释器形成一个可复跑链路，后续真实候选包到来时能更快发现证据缺口。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：否。
