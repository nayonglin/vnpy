# Stage135 真实 W0 到货 operator pack 与目录预检

- line_id：futures_trend_c9_minrisk_highquality
- 当前模式：day
- 记录时间：2026-06-20 21:30 CST
- 工作区/分支：/Users/bytedance/Desktop/person/vnpy / master
- 阶段性质：真实 W0 到货后的操作手册、候选目录预检和防误用执行包；不做策略 alpha，不做 true engine，不做 A/B
- 是否重要突破：否；这是 Stage124/125/133/134 的实操包装和误跑防线
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - SLSA Provenance：https://slsa.dev/spec/draft/build-provenance
  - SLSA Levels：https://slsa.dev/spec/v1.1/levels
  - Great Expectations validation/checkpoints：https://docs.greatexpectations.io/docs/0.18/oss/guides/validation/validate_data_overview
  - Dagster blocking asset checks：https://docs.dagster.io/api/dagster/asset-checks
  - OpenLineage facets：https://openlineage.io/docs/spec/facets/
- 我的判断：真实数据到货前，最容易出错的不是策略逻辑，而是把 fixture、空目录、半交付包或格式正确但不完整的 proof 当成可研究数据。Stage135 借鉴 provenance、checkpoint 和 blocking asset check 的思路，把真实到货路径写成 operator runbook + command manifest + candidate dir audit；缺真实文件时必须稳定阻断，不允许为了“继续研究”伪造入口。

## 本次变更

- 新增脚本：
  - `research/lines/futures_trend_c9_minrisk_highquality/tools/stage135_wave0_real_drop_operator_pack.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数/约束：
  - 候选真实 W0 drop 目录：
    - `research/lines/futures_trend_c9_minrisk_highquality/inputs/w0_real_drop`
    - `research/lines/futures_trend_c9_minrisk_highquality/inputs/authorized_w0_real_drop`
    - `research/lines/futures_trend_c9_minrisk_highquality/data/w0_real_drop`
    - `research/lines/futures_trend_c9_minrisk_highquality/data/authorized_w0_real_drop`
    - `research/lines/futures_trend_c9_minrisk_highquality/incoming/w0_real_drop`
  - 显式禁用 Stage131 fixture 路径作为真实候选。
  - 固定 operator 命令顺序：Stage125 receipt preflight -> Stage133 total release verdict -> Stage134 CLI selftest（仅命令变化时）-> Stage131 fixture 禁用提示。
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用 Stage131/Stage045 官方背景曲线 2018-2026；Stage135 本身不新增交易
- 账户规模：沿用当前 C9 min-risk 线背景口径
- 成本口径：沿用 Stage131 背景统计，总滑点 `2,730,130`
- 样本过滤：无交易样本过滤；只扫描候选真实 drop 目录和 Stage131 禁用 fixture 标记
- 策略/归因口径：operator pack readiness；不允许进入分钟规则，不允许 true engine

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26,017.63%`
- 最大回撤：`-45.08%`
- Sharpe：`1.633`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：`36.09%`
- 其他关键指标：
  - decision：`stage135_real_drop_operator_pack_ready_waiting_for_real_w0_no_strategy`
  - candidate_dir_count：`5`
  - existing_candidate_dir_count：`0`
  - best_known_file_count：`0`
  - expected_file_count：`123`
  - candidate_ready_count：`0`
  - operator_command_count：`4`
  - operator_pack_ready：`1`
  - planning_gate_pass_count：`6/6`
  - data_gate_pass_count：`0/2`
  - stage133_release_allowed_now：`0`
  - real_w0_data_delivered：`0`
  - real_stage112_intake_allowed_now：`0`
  - true_engine_allowed：`0`
  - strategy_feature_usable：`0`
  - max_broker10_margin_to_equity_pct：`111.7365`

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage135_wave0_real_drop_operator_pack/qmt_roll_stage135_c9_minrisk_wave0_real_drop_operator_pack_report_stage135_wave0_real_drop_operator_pack_v1.md`
- runbook：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage135_wave0_real_drop_operator_pack/qmt_roll_stage135_c9_minrisk_wave0_real_drop_operator_pack_REAL_W0_OPERATOR_RUNBOOK_stage135_wave0_real_drop_operator_pack_v1.md`
- decision：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage135_wave0_real_drop_operator_pack/qmt_roll_stage135_c9_minrisk_wave0_real_drop_operator_pack_decision_stage135_wave0_real_drop_operator_pack_v1.json`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage135_wave0_real_drop_operator_pack/qmt_roll_stage135_c9_minrisk_wave0_real_drop_operator_pack_summary_stage135_wave0_real_drop_operator_pack_v1.csv`
- orders：无；本阶段不生成订单
- daily：无新增交易 daily；资金曲线沿用背景审计序列
- quality：
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage135_wave0_real_drop_operator_pack/qmt_roll_stage135_c9_minrisk_wave0_real_drop_operator_pack_candidate_drop_dir_audit_stage135_wave0_real_drop_operator_pack_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage135_wave0_real_drop_operator_pack/qmt_roll_stage135_c9_minrisk_wave0_real_drop_operator_pack_candidate_role_audit_stage135_wave0_real_drop_operator_pack_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage135_wave0_real_drop_operator_pack/qmt_roll_stage135_c9_minrisk_wave0_real_drop_operator_pack_operator_command_manifest_stage135_wave0_real_drop_operator_pack_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage135_wave0_real_drop_operator_pack/qmt_roll_stage135_c9_minrisk_wave0_real_drop_operator_pack_operator_pack_gate_status_stage135_wave0_real_drop_operator_pack_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage135_wave0_real_drop_operator_pack/qmt_roll_stage135_c9_minrisk_wave0_real_drop_operator_pack_official_path_operator_pack_status_stage135_wave0_real_drop_operator_pack_v1.png`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage135_wave0_real_drop_operator_pack/qmt_roll_stage135_c9_minrisk_wave0_real_drop_operator_pack_candidate_drop_dir_matrix_stage135_wave0_real_drop_operator_pack_v1.png`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage135_wave0_real_drop_operator_pack/qmt_roll_stage135_c9_minrisk_wave0_real_drop_operator_pack_operator_command_matrix_stage135_wave0_real_drop_operator_pack_v1.png`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage135_wave0_real_drop_operator_pack/qmt_roll_stage135_c9_minrisk_wave0_real_drop_operator_pack_operator_gate_chart_stage135_wave0_real_drop_operator_pack_v1.png`

## 视觉检查

- 官方路径/operator pack 状态图：资金、回撤、broker10 曲线非空；底部状态显示 `operator_pack_ready=1`，但 `existing_candidate_dir_count=0`、`candidate_ready_count=0`、`stage133_release_allowed_now=0`。
- 候选目录矩阵：5 个候选真实 drop 目录均为 `exists=0`，`candidate_ready_for_stage133=0`，且 `under_forbidden_fixture_root=0`。
- 命令矩阵：Stage125 receipt preflight、Stage133 total release verdict、Stage131 fixture 禁用命令均为 `required_before_next=1` 且会阻断下游；Stage134 selftest 只在命令变更时需要，但也标记为未满足则阻断下游。
- operator gate 图：planning/orchestration/anti-selection 全通过，data hard gate 两项红色：`real_drop_candidate_present=0`、`real_drop_candidate_complete=0/123`。

## 结论

- 本阶段结论：真实 W0 operator pack 已准备好，但真实 W0 数据尚未交付。当前只能等待或接收真实 drop，不能进入分钟盘口研究。
- 真实到货后的固定命令：
  - `.py311/bin/python research/lines/futures_trend_c9_minrisk_highquality/tools/stage125_wave0_receipt_preflight_audit.py --drop-dir <real_w0_drop> --case-id real_w0_receipt_preflight`
  - `.py311/bin/python research/lines/futures_trend_c9_minrisk_highquality/tools/stage133_wave0_total_intake_downstream_gate_audit.py --drop-dir <real_w0_drop> --case-id real_w0_total_gate --expected-stage112-intake 1 --expected-downstream-release 1`
- 是否进入下一步：是，但下一步仍是数据到货/验收层；没有真实 W0 时，不允许绕回 Stage131 fixture 或旧分钟 OHLC 继续造规则。
- 下一步：把真实 W0 放入一个明确候选目录后，按 Stage125 -> Stage133 顺序运行；若仍没有真实数据，可继续做 watched inbox/到货 digest/验收报告自动化，但不得写策略条件。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段没有新增收益参数、没有筛品种/年份/方向、没有看交易盈亏去调规则，只把真实数据到货的机械验收路径显性化。它降低的是流程误用风险，不是历史回测指标。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值。
- 原因：当前真正的瓶颈是授权盘口/执行数据未到，不是缺一个新的历史规则。Stage135 把“数据到了怎么不误跑”固化下来，能避免把空目录、fixture 或半交付包误送入 Stage112/113；这比继续从旧分钟源里挖规则更符合穿越周期的约束。

## 合入建议

- 是否更新本线 `LINE.md`：是
- 是否更新 `research/registry.md`：否；这不是新增研究线或跨线合入
- 是否追加根目录 `memory.md/back_log.md`：否；这不是正式候选、重大突破或跨线合并
